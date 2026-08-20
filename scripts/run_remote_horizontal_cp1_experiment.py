from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from gdu.adapter_v1 import (
    OpenAICompatibleRemoteTransport,
    StructuredUnderstandingAdapter,
    load_remote_transport_config,
    sha256_file,
)
from gdu.builder_v0.id_allocator import CanonicalIdAllocator
from gdu.builder_v0.source_reader import PypdfBackend, SourceReader
from gdu.builder_v0.types import (
    CandidateBundle,
    CandidateObject,
    SourceRequest,
    TechnicalFailure,
)
from scripts.run_remote_cp1_experiment import (
    DOCUMENT_ID,
    ROOT,
    SOURCE_SHA256,
    TEXT_SHA256,
    file_sha256,
    load_json,
    sub_schema,
    trusted_manifest,
    validate,
    verify_grounding,
)


EXPECTED_SECTIONS = {
    "第三节 管理层讨论与分析": (12, 36),
    "第四节 公司治理、环境和社会": (36, 57),
}


def bind_deterministic_evidence(
    bundle: CandidateBundle, packet: Any
) -> CandidateBundle:
    """Keep model structure decisions while binding exact PDF evidence in code."""
    fragments = {fragment.page: fragment for fragment in packet.pdf_fragments}
    required_pages = (12, 36, 57)
    if any(page not in fragments for page in required_pages):
        raise TechnicalFailure(
            "remote_horizontal_cp1_experiment", "required boundary fragment is missing"
        )
    evidence = tuple(
        CandidateObject(
            kind="evidence",
            handle=f"boundary_page_{page}",
            fields={
                "modality": "text",
                "fragments": [fragments[page].as_evidence_fragment()],
            },
            source_authority="pdf",
        )
        for page in required_pages
    )
    structures: list[CandidateObject] = []
    for item in bundle.objects:
        if item.kind != "physical_structure":
            continue
        fields = dict(item.fields)
        title = fields.get("original_label")
        refs = {
            "第三节 管理层讨论与分析": ["@boundary_page_12", "@boundary_page_36"],
            "第四节 公司治理、环境和社会": ["@boundary_page_36", "@boundary_page_57"],
        }.get(title)
        if refs is None:
            raise TechnicalFailure(
                "remote_horizontal_cp1_experiment", f"unexpected section label: {title}"
            )
        fields.pop("id", None)
        fields["evidence_refs"] = refs
        structures.append(
            CandidateObject(
                kind="physical_structure",
                handle=f"model_section_{fields['order']}",
                fields=fields,
                source_authority="pdf",
            )
        )
    return CandidateBundle(
        stage="cp1",
        objects=evidence + tuple(structures),
        manifest=bundle.manifest,
    )


def load_rejected_bundle(path: Path) -> tuple[CandidateBundle, str]:
    value = load_json(path)
    objects = []
    for index, item in enumerate(value["canonical_objects"]):
        if item["kind"] != "physical_structure":
            continue
        fields = dict(item["fields"])
        fields.pop("id", None)
        objects.append(
            CandidateObject(
                kind="physical_structure",
                handle=f"replayed_section_{index}",
                fields=fields,
                source_authority="pdf",
            )
        )
    return (
        CandidateBundle(stage="cp1", objects=tuple(objects), manifest=value["manifest"]),
        str(value["result_summary"]),
    )


def horizontal_guidance(manifest: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "experiment_scope": (
            "Horizontal CP1 expansion only. The document node and first two sections "
            "already exist. Identify exactly the third and fourth top-level sections "
            "from the supplied boundary pages. Do not create semantic claims."
        ),
        "trusted_manifest": dict(manifest),
        "manifest_rule": "Copy trusted_manifest exactly into response.manifest.",
        "expected_boundaries": [
            {
                "original_label": title,
                "page_range": {"start": bounds[0], "end": bounds[1]},
            }
            for title, bounds in EXPECTED_SECTIONS.items()
        ],
        "boundary_rule": (
            "A boundary page may contain the end of one section and the heading of "
            "the next, so adjacent top-level ranges may share page 36. Page 57 is "
            "the observed start of section five and therefore the end boundary of "
            "section four."
        ),
        "object_rules": [
            "Return exactly two physical_structure objects and sufficient evidence objects",
            "Do not return a document node or sections one, two, or five",
            "physical_structure parent_ref must be null because the existing document node is outside this standalone bundle",
            "Use order 3 for the third section and order 4 for the fourth section",
            "Every physical_structure evidence_refs item must use a local @evidence handle",
            "Evidence fragments must exactly copy authorized source fragments",
            "Do not include canonical IDs in fields",
            "source_authority must be pdf",
        ],
        "candidate_shape_rule": (
            "Every objects item has exactly four top-level keys: kind, handle, fields, "
            "source_authority. All domain properties including evidence_refs, page_range, "
            "fragments, modality, parent_ref, node_type, original_label, and order belong "
            "inside fields; never place them beside fields."
        ),
        "physical_structure_shape_example": {
            "kind": "physical_structure",
            "handle": "section_three",
            "fields": {
                "parent_ref": None,
                "node_type": "section",
                "original_label": "第三节 管理层讨论与分析",
                "order": 3,
                "page_range": {"start": 12, "end": 36},
                "evidence_refs": ["@evidence_page_12"],
            },
            "source_authority": "pdf",
        },
        "evidence_shape_example": {
            "kind": "evidence",
            "handle": "evidence_page_12",
            "fields": {
                "modality": "text",
                "fragments": [
                    {
                        "page": 12,
                        "locator": "COPY AUTHORIZED LOCATOR",
                        "excerpt": "COPY COMPLETE AUTHORIZED EXCERPT",
                        "fragment_sha256": "COPY AUTHORIZED SHA256",
                    }
                ],
            },
            "source_authority": "pdf",
        },
        "response_rules": [
            "contract_version gdu-adapter-v1, mode propose, stage cp1",
            "mutations and revisions must be empty arrays",
            "observed_run_identity must exactly copy request.run_identity",
            "Use concise Simplified Chinese",
        ],
    }


def verify_horizontal_structure(
    canonical: list[tuple[str, dict[str, Any]]], packet: Any
) -> None:
    verify_grounding(canonical, packet)
    structures = [fields for kind, fields in canonical if kind == "physical_structure"]
    if len(structures) != 2:
        raise TechnicalFailure(
            "remote_horizontal_cp1_experiment",
            "expected exactly two physical section nodes",
        )
    observed: dict[str, tuple[int, int]] = {}
    for fields in structures:
        if fields["node_type"] != "section":
            raise TechnicalFailure(
                "remote_horizontal_cp1_experiment", "top-level node_type must be section"
            )
        if fields["parent_ref"] is not None:
            raise TechnicalFailure(
                "remote_horizontal_cp1_experiment", "standalone parent_ref must be null"
            )
        page_range = fields["page_range"]
        observed[fields["original_label"]] = (
            page_range["start"],
            page_range["end"],
        )
    if observed != EXPECTED_SECTIONS:
        raise TechnicalFailure(
            "remote_horizontal_cp1_experiment",
            f"incorrect horizontal section boundaries: {observed}",
        )
    expected_orders = {
        "第三节 管理层讨论与分析": 3,
        "第四节 公司治理、环境和社会": 4,
    }
    if any(fields["order"] != expected_orders[fields["original_label"]] for fields in structures):
        raise TechnicalFailure(
            "remote_horizontal_cp1_experiment", "incorrect section order"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--text", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--replay-rejected",
        type=Path,
        help="re-evaluate a rejected result with deterministic evidence binding and no API call",
    )
    args = parser.parse_args()

    if file_sha256(args.text) != TEXT_SHA256:
        raise TechnicalFailure(
            "remote_horizontal_cp1_experiment", "extracted text SHA-256 mismatch"
        )
    reader = SourceReader(
        args.pdf,
        DOCUMENT_ID,
        PypdfBackend(),
        expected_source_sha256=SOURCE_SHA256,
    )
    source_identity = reader.inspect()
    packet = reader.read(
        SourceRequest(
            purpose=(
                "Verify third- and fourth-section boundaries for horizontal CP1 expansion."
            ),
            page_ranges=((12, 12), (35, 36), (56, 57)),
            modalities=("text",),
            locator_hints=(
                "third section heading",
                "third-to-fourth boundary",
                "fourth-to-fifth boundary",
            ),
        )
    )
    config_path = ROOT / (
        "configs/api/aliyun-token-plan-deepseek-v4-flash-0731.example.json"
    )
    config_hash = sha256_file(config_path)
    remote = load_remote_transport_config(
        config_path,
        ROOT / "configs/api/remote-adapter-v1.schema.json",
        config_hash,
    )
    if args.replay_rejected:
        model_bundle, result_summary = load_rejected_bundle(args.replay_rejected)
        calls_made = 0
    else:
        transport = OpenAICompatibleRemoteTransport(
            remote,
            explicit_authorization=True,
            response_contract=load_json(ROOT / "adapter-response-v1.schema.json"),
        )
        adapter = StructuredUnderstandingAdapter(
            transport,
            (remote.model, "provider-default", config_hash),
            ROOT / "adapter-request-v1.schema.json",
            ROOT / "adapter-response-v1.schema.json",
            paid_remote_calls_allowed=True,
            max_remote_calls=1,
        )
        manifest = trusted_manifest(source_identity, args.text, config_hash, remote.model)
        result = adapter.propose("cp1", packet, horizontal_guidance(manifest))
        if result.bundle is None:
            raise TechnicalFailure(
                "remote_horizontal_cp1_experiment", "horizontal CP1 returned no bundle"
            )
        model_bundle = result.bundle
        result_summary = result.result_summary
        calls_made = transport.calls_made

    bound_bundle = bind_deterministic_evidence(model_bundle, packet)
    canonical = CanonicalIdAllocator().canonicalize(bound_bundle)
    output = {
        "experiment": f"remote-horizontal-cp1-{remote.model}-v1",
        "result_summary": result_summary,
        "calls_made": calls_made,
        "source_pages": [fragment.page for fragment in packet.pdf_fragments],
        "manifest": bound_bundle.manifest,
        "canonical_objects": [
            {"kind": kind, "fields": fields} for kind, fields in canonical
        ],
        "validation": {"adapter_response_schema": "passed"},
    }
    try:
        gdu_schema = load_json(ROOT / "gdu.schema.json")
        validate(bound_bundle.manifest or {}, sub_schema(gdu_schema, "manifest"), "manifest")
        for kind, fields in canonical:
            schema_name = {"evidence": "evidence", "physical_structure": "physicalNode"}.get(kind)
            if schema_name is None:
                raise TechnicalFailure(
                    "remote_horizontal_cp1_experiment", f"unexpected object kind: {kind}"
                )
            validate(fields, sub_schema(gdu_schema, schema_name), kind)
        output["validation"]["gdu_field_schemas"] = "passed"
        verify_horizontal_structure(canonical, packet)
        output["validation"]["horizontal_boundaries"] = "passed"
    except (TechnicalFailure, KeyError) as exc:
        output["validation"]["horizontal_boundaries"] = "failed"
        output["validation"]["failure_summary"] = str(exc)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("REMOTE_HORIZONTAL_CP1_REJECTED")
        print(f"CALLS_MADE {calls_made}")
        print(f"OUTPUT {args.output}")
        raise

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("REMOTE_HORIZONTAL_CP1_OK")
    print(f"CALLS_MADE {calls_made}")
    print(f"OBJECTS {len(canonical)}")
    print(f"OUTPUT {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
