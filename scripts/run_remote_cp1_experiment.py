from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import jsonschema

from gdu.adapter_v1 import (
    OpenAICompatibleRemoteTransport,
    StructuredUnderstandingAdapter,
    load_remote_transport_config,
    sha256_file,
)
from gdu.builder_v0.id_allocator import CanonicalIdAllocator
from gdu.builder_v0.source_reader import PypdfBackend, SourceReader
from gdu.builder_v0.types import SourceRequest, TechnicalFailure


ROOT = Path(__file__).resolve().parents[1]
SOURCE_SHA256 = "fbb9875c7eca1f921ca0635cabbe53727b7ff57658750fa0eeefd92402730c59"
TEXT_SHA256 = "d3258943647ba57408471fd43ece8d52415e75ec4f39df16c63861d4af450c9a"
DOCUMENT_ID = "litong-2025-annual-report"


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def validate(value: Mapping[str, Any], schema: Mapping[str, Any], label: str) -> None:
    errors = sorted(
        jsonschema.Draft202012Validator(schema).iter_errors(value),
        key=lambda error: list(error.path),
    )
    if errors:
        first = errors[0]
        location = ".".join(str(part) for part in first.absolute_path) or "$"
        raise TechnicalFailure(
            "remote_cp1_experiment",
            f"invalid {label} at {location}: {first.message}",
        )


def sub_schema(full: Mapping[str, Any], name: str) -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$defs": copy.deepcopy(full["$defs"]),
        "$ref": f"#/$defs/{name}",
    }


def trusted_manifest(
    source_identity: Any,
    extracted_text: Path,
    config_hash: str,
) -> dict[str, Any]:
    return {
        "gdu_identity": {
            "gdu_id": "gdu-remote-cp1-qwen37",
            "schema_version": "gdu-v0",
            "artifact_version": "0.1.0-remote-cp1-experiment",
            "status": "provisional",
            "built_at": "2026-08-20T00:00:00+08:00",
        },
        "source_identity": {
            "document_id": source_identity.document_id,
            "title": "江苏利通电子股份有限公司2025年年度报告",
            "language": "zh-CN",
            "document_type": "上市公司年度报告",
            "original_filename": source_identity.original_filename,
            "source_sha256": source_identity.source_sha256,
            "pdf_page_count": source_identity.pdf_page_count,
            "extracted_text_sha256": file_sha256(extracted_text),
            "extraction_system": source_identity.extraction_system,
        },
        "build_identity": {
            "protocol_name": "gdu-builder-protocol",
            "protocol_version": "v2",
            "protocol_sha256": sha256_file(ROOT / "BUILDER_PROTOCOL_V2.md"),
            "model_id": "qwen3.7-plus",
            "reasoning_effort": "provider-default",
            "config_or_prompt_sha256": config_hash,
            "build_log_ref": "remote-cp1-experiment-not-published",
        },
    }


def guidance(manifest: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "experiment_scope": (
            "CP1 only. Identify only document physical structure and its PDF "
            "evidence from the authorized page fragments. Do not infer semantic "
            "claims, relations, or interpretations."
        ),
        "trusted_manifest": copy.deepcopy(dict(manifest)),
        "manifest_rule": "Copy trusted_manifest exactly into response.manifest.",
        "allowed_candidate_kinds": ["evidence", "physical_structure"],
        "evidence_fields": {
            "required": ["modality", "fragments"],
            "rule": (
                "Each fragment must copy page, locator, excerpt, and fragment_sha256 "
                "exactly from one authorized source_packet.pdf_fragments item."
            ),
            "exact_shape_example": {
                "modality": "text",
                "fragments": [
                    {
                        "page": 1,
                        "locator": "physical-page:1",
                        "excerpt": "COPY THE COMPLETE AUTHORIZED EXCERPT",
                        "fragment_sha256": "COPY THE AUTHORIZED 64-CHAR SHA256",
                    }
                ],
            },
        },
        "physical_structure_fields": {
            "required": [
                "parent_ref",
                "node_type",
                "original_label",
                "order",
                "page_range",
                "evidence_refs",
            ],
            "rule": (
                "Do not include canonical id. Use @handle references for parent_ref "
                "and evidence_refs. Create a document node and only clearly visible "
                "section nodes from the supplied pages."
            ),
            "exact_shape_example": {
                "parent_ref": None,
                "node_type": "document",
                "original_label": "COPY A VISIBLE LABEL",
                "order": 1,
                "page_range": {"start": 1, "end": 237},
                "evidence_refs": ["@evidence_handle"],
                "observation_note": "Optional non-empty note.",
            },
            "shape_warning": (
                "page_range MUST be an object with integer start and end keys; "
                "never return an array such as [1, 237]."
            ),
        },
        "response_rules": [
            "contract_version must be gdu-adapter-v1",
            "mode must be propose and stage must be cp1",
            "mutations and revisions must be empty arrays",
            "observed_run_identity must exactly copy request.run_identity",
            "source_authority must be pdf for evidence and physical_structure",
            "Use concise Chinese labels and summaries grounded only in supplied PDF text",
        ],
    }


def verify_grounding(canonical: list[tuple[str, dict[str, Any]]], packet: Any) -> None:
    authorized = {
        (
            fragment.page,
            fragment.locator,
            fragment.excerpt,
            fragment.fragment_sha256,
        )
        for fragment in packet.pdf_fragments
    }
    for kind, fields in canonical:
        if kind != "evidence":
            continue
        for fragment in fields["fragments"]:
            observed = (
                fragment["page"],
                fragment["locator"],
                fragment["excerpt"],
                fragment["fragment_sha256"],
            )
            if observed not in authorized:
                raise TechnicalFailure(
                    "remote_cp1_experiment",
                    "model evidence is not an exact authorized PDF fragment",
                )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--text", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if file_sha256(args.text) != TEXT_SHA256:
        raise TechnicalFailure(
            "remote_cp1_experiment", "extracted text SHA-256 mismatch"
        )
    backend = PypdfBackend()
    reader = SourceReader(
        args.pdf,
        DOCUMENT_ID,
        backend,
        expected_source_sha256=SOURCE_SHA256,
    )
    source_identity = reader.inspect()
    packet = reader.read(
        SourceRequest(
            purpose="Ground cover and visible section structure for CP1.",
            page_ranges=((1, 1), (8, 8)),
            modalities=("text",),
            locator_hints=("cover title", "second section heading"),
        )
    )

    config_path = (
        ROOT / "configs/api/aliyun-token-plan-qwen3.7-plus.example.json"
    )
    config_hash = sha256_file(config_path)
    remote = load_remote_transport_config(
        config_path,
        ROOT / "configs/api/remote-adapter-v1.schema.json",
        config_hash,
    )
    response_contract = load_json(ROOT / "adapter-response-v1.schema.json")
    transport = OpenAICompatibleRemoteTransport(
        remote,
        explicit_authorization=True,
        response_contract=response_contract,
    )
    adapter = StructuredUnderstandingAdapter(
        transport,
        ("qwen3.7-plus", "provider-default", config_hash),
        ROOT / "adapter-request-v1.schema.json",
        ROOT / "adapter-response-v1.schema.json",
        paid_remote_calls_allowed=True,
        max_remote_calls=1,
    )
    manifest = trusted_manifest(source_identity, args.text, config_hash)
    result = adapter.propose("cp1", packet, guidance(manifest))
    if result.bundle is None:
        raise TechnicalFailure("remote_cp1_experiment", "CP1 returned no bundle")

    allocator = CanonicalIdAllocator()
    canonical = allocator.canonicalize(result.bundle)
    gdu_schema = load_json(ROOT / "gdu.schema.json")
    output = {
        "experiment": "remote-cp1-qwen3.7-plus-v1",
        "result_summary": result.result_summary,
        "calls_made": transport.calls_made,
        "source_pages": [fragment.page for fragment in packet.pdf_fragments],
        "manifest": result.bundle.manifest,
        "canonical_objects": [
            {"kind": kind, "fields": fields} for kind, fields in canonical
        ],
        "validation": {"adapter_response_schema": "passed"},
    }
    try:
        validate(
            result.bundle.manifest or {},
            sub_schema(gdu_schema, "manifest"),
            "manifest",
        )
        for kind, fields in canonical:
            schema_name = {
                "evidence": "evidence",
                "physical_structure": "physicalNode",
            }.get(kind)
            if schema_name is None:
                raise TechnicalFailure(
                    "remote_cp1_experiment", f"unexpected CP1 object kind: {kind}"
                )
            validate(fields, sub_schema(gdu_schema, schema_name), kind)
        output["validation"]["gdu_field_schemas"] = "passed"
        verify_grounding(canonical, packet)
        output["validation"]["exact_source_fragment_grounding"] = "passed"
    except TechnicalFailure as exc:
        output["validation"]["gdu_field_schemas"] = "failed"
        output["validation"]["failure_component"] = exc.component
        output["validation"]["failure_summary"] = exc.summary
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(output, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print("REMOTE_CP1_REJECTED")
        print(f"CALLS_MADE {transport.calls_made}")
        print(f"OUTPUT {args.output}")
        raise

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("REMOTE_CP1_OK")
    print(f"CALLS_MADE {transport.calls_made}")
    print(f"OBJECTS {len(canonical)}")
    print(f"OUTPUT {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
