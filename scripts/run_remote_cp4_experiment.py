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
from gdu.builder_v0.types import (
    CandidateValidationError,
    SourceRequest,
    TechnicalFailure,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE_SHA256 = "fbb9875c7eca1f921ca0635cabbe53727b7ff57658750fa0eeefd92402730c59"
TEXT_SHA256 = "d3258943647ba57408471fd43ece8d52415e75ec4f39df16c63861d4af450c9a"
CP3_RESULT_SHA256 = "8957412dcc9ac4e7e151eb3f65bdca0c9b4e824b5ddacfc6f9e320804dacd148"
DOCUMENT_ID = "litong-2025-annual-report"
ASSERTION_IDS = {f"A-{value:03d}" for value in range(1, 9)}
EVIDENCE_IDS = {f"E-{value:03d}" for value in range(2, 7)}
EXPECTED_EDGES = {
    ("A-003", "A-001", "composes"),
    ("A-005", "A-006", "supports"),
    ("A-005", "A-007", "supports"),
    ("A-008", "A-006", "limits"),
    ("A-008", "A-007", "limits"),
}


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def sub_schema(full: Mapping[str, Any], name: str) -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$defs": copy.deepcopy(full["$defs"]),
        "$ref": f"#/$defs/{name}",
    }


def validate(value: Mapping[str, Any], schema: Mapping[str, Any], label: str) -> None:
    errors = sorted(
        jsonschema.Draft202012Validator(schema).iter_errors(value),
        key=lambda error: list(error.path),
    )
    if errors:
        first = errors[0]
        location = ".".join(str(part) for part in first.absolute_path) or "$"
        raise TechnicalFailure(
            "remote_cp4_experiment",
            f"invalid {label} at {location}: {first.message}",
        )


def load_accepted_cp3(path: Path) -> dict[str, Any]:
    if file_sha256(path) != CP3_RESULT_SHA256:
        raise TechnicalFailure(
            "remote_cp4_experiment", "accepted CP3 result SHA-256 mismatch"
        )
    value = load_json(path)
    canonical = value.get("canonical_objects", [])
    observed_ids = {
        item.get("fields", {}).get("id")
        for item in canonical
        if item.get("kind") == "assertion"
    }
    if observed_ids != {"A-005", "A-006", "A-007", "A-008"}:
        raise TechnicalFailure(
            "remote_cp4_experiment", "CP3 prerequisite object set is unexpected"
        )
    groups = [
        item["fields"]
        for item in canonical
        if item.get("kind") == "interpretation_group"
    ]
    if (
        len(groups) != 1
        or groups[0].get("mode") != "parallel"
        or set(groups[0].get("member_refs", [])) != {"A-006", "A-007"}
        or "preferred_ref" in groups[0]
    ):
        raise TechnicalFailure(
            "remote_cp4_experiment", "CP3 parallel interpretation prerequisite failed"
        )
    return {
        "accepted_cp3_objects": copy.deepcopy(canonical),
        "source_result_sha256": CP3_RESULT_SHA256,
    }


def cp4_guidance() -> dict[str, Any]:
    return {
        "experiment_scope": (
            "CP4 only. Connect the accepted assertions into a minimal verified "
            "relation network. Do not add facts, interpretations, or evidence."
        ),
        "allowed_candidate_kinds": ["relation"],
        "existing_assertion_refs": sorted(ASSERTION_IDS),
        "existing_evidence_refs": sorted(EVIDENCE_IDS),
        "required_edges": [
            {
                "from_ref": "A-003",
                "to_ref": "A-001",
                "relation_type": "composes",
                "meaning": "非经常性损益参与构成归母净利润与扣非净利润的差额。",
                "origin": "source_attributed",
            },
            {
                "from_ref": "A-005",
                "to_ref": "A-006",
                "relation_type": "supports",
                "meaning": "原文列出的经营原因支持经营改善解释。",
                "origin": "analytic_interpretation",
            },
            {
                "from_ref": "A-005",
                "to_ref": "A-007",
                "relation_type": "supports",
                "meaning": "原文列出的投资原因支持投资公允价值解释。",
                "origin": "analytic_interpretation",
            },
            {
                "from_ref": "A-008",
                "to_ref": "A-006",
                "relation_type": "limits",
                "meaning": "未量化贡献的约束限制经营解释被扩大为主导解释。",
                "origin": "analytic_interpretation",
            },
            {
                "from_ref": "A-008",
                "to_ref": "A-007",
                "relation_type": "limits",
                "meaning": "未量化贡献的约束限制投资解释被扩大为主导解释。",
                "origin": "analytic_interpretation",
            },
        ],
        "source_relation_shape": {
            "endpoint_level": "assertion",
            "from_ref": "A-003",
            "to_ref": "A-001",
            "relation_type": "composes",
            "description": "准确说明两个断言之间的组成关系。",
            "epistemic_origin": "source_attributed",
            "assessment_complete": True,
            "evidence_status": "supported",
            "evidence_refs": ["E-003", "E-005"],
            "rationale": "说明同一报告口径和金额如何支持该关系。",
            "actor": "江苏利通电子股份有限公司",
            "attribution_mode": "entailed",
        },
        "analytic_relation_shape": {
            "endpoint_level": "assertion",
            "from_ref": "A-005",
            "to_ref": "A-006",
            "relation_type": "supports",
            "description": "准确说明支持或限定关系。",
            "epistemic_origin": "analytic_interpretation",
            "assessment_complete": True,
            "evidence_status": "supported",
            "evidence_refs": ["E-003"],
            "rationale": "说明关系为什么成立。",
            "basis_assertion_refs": ["A-005", "A-006"],
        },
        "response_checklist": [
            "Return exactly five relation candidates matching required_edges exactly",
            "Every objects item MUST have exactly the wrapper keys kind, handle, fields, and source_authority; kind is relation and source_authority is pdf",
            "Candidate fields MUST NOT contain id; only the wrapper has a temporary handle",
            "All endpoint_level values must be assertion",
            "Do not reverse any required edge",
            "Do not use alternative_to between A-006 and A-007 because they are parallel, not mutually exclusive",
            "Every analytic relation must contain both endpoint assertions in basis_assertion_refs",
            "The one source_attributed relation MUST contain actor and attribution_mode, and MUST NOT contain basis_assertion_refs",
            "The four analytic_interpretation relations MUST contain basis_assertion_refs, and MUST NOT contain actor or attribution_mode",
            "Every relation must be assessment_complete true and evidence_status supported",
            "Do not mention a physical page in description or rationale unless the corresponding E-reference is included",
            "Use concise Simplified Chinese throughout",
            "contract_version gdu-adapter-v1, mode propose, stage cp4",
            "mutations and revisions must be empty arrays",
            "observed_run_identity must exactly copy request.run_identity",
        ],
    }


def verify_cp4_semantics(canonical: list[tuple[str, dict[str, Any]]]) -> None:
    if len(canonical) != 5 or any(kind != "relation" for kind, _ in canonical):
        raise TechnicalFailure(
            "remote_cp4_experiment", "expected exactly five relations"
        )
    relations = [fields for _, fields in canonical]
    observed_edges = {
        (item["from_ref"], item["to_ref"], item["relation_type"])
        for item in relations
    }
    if observed_edges != EXPECTED_EDGES:
        raise TechnicalFailure(
            "remote_cp4_experiment", "relation edge set differs from preregistration"
        )
    for item in relations:
        if item["endpoint_level"] != "assertion":
            raise TechnicalFailure(
                "remote_cp4_experiment", "relation endpoint level is not assertion"
            )
        if item["from_ref"] not in ASSERTION_IDS or item["to_ref"] not in ASSERTION_IDS:
            raise TechnicalFailure(
                "remote_cp4_experiment", "relation used unknown assertion"
            )
        if item["from_ref"] == item["to_ref"]:
            raise TechnicalFailure("remote_cp4_experiment", "self relation returned")
        if not set(item["evidence_refs"]).issubset(EVIDENCE_IDS):
            raise TechnicalFailure(
                "remote_cp4_experiment", "relation used unknown evidence"
            )
        if item.get("assessment_complete") is not True or item.get("evidence_status") != "supported":
            raise TechnicalFailure(
                "remote_cp4_experiment", "relation assessment is incomplete"
            )
        if item["epistemic_origin"] == "analytic_interpretation":
            endpoints = {item["from_ref"], item["to_ref"]}
            if not endpoints.issubset(set(item.get("basis_assertion_refs", []))):
                raise TechnicalFailure(
                    "remote_cp4_experiment",
                    "analytic relation basis does not include both endpoints",
                )
    compose = next(item for item in relations if item["relation_type"] == "composes")
    if (
        compose["epistemic_origin"] != "source_attributed"
        or compose.get("attribution_mode") != "entailed"
        or not {"E-003", "E-005"}.issubset(set(compose["evidence_refs"]))
    ):
        raise TechnicalFailure(
            "remote_cp4_experiment", "composition relation lacks source grounding"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--text", type=Path, required=True)
    parser.add_argument("--cp3-result", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if file_sha256(args.text) != TEXT_SHA256:
        raise TechnicalFailure(
            "remote_cp4_experiment", "extracted text SHA-256 mismatch"
        )
    accepted_cp3 = load_accepted_cp3(args.cp3_result)
    reader = SourceReader(
        args.pdf,
        DOCUMENT_ID,
        PypdfBackend(),
        expected_source_sha256=SOURCE_SHA256,
    )
    reader.inspect()
    packet = reader.read(
        SourceRequest(
            purpose="Verify assertion-level relations for the accepted local unit.",
            page_ranges=((9, 12),),
            modalities=("text",),
            locator_hints=(
                "归母净利润",
                "扣除非经常性损益",
                "利润增长原因",
                "公允价值变动",
            ),
        )
    )

    config_path = ROOT / (
        "configs/api/"
        "aliyun-token-plan-deepseek-v4-flash-0731.example.json"
    )
    config_hash = sha256_file(config_path)
    remote = load_remote_transport_config(
        config_path,
        ROOT / "configs/api/remote-adapter-v1.schema.json",
        config_hash,
    )
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
    public_view = {
        **accepted_cp3,
        "accepted_prior_assertion_ids": sorted(ASSERTION_IDS),
        "cp4_experiment_guidance": cp4_guidance(),
    }
    result = adapter.propose("cp4", packet, public_view)
    if result.bundle is None:
        raise TechnicalFailure("remote_cp4_experiment", "CP4 returned no bundle")

    output: dict[str, Any] = {
        "experiment": f"remote-cp4-{remote.model}-v1",
        "result_summary": result.result_summary,
        "calls_made": transport.calls_made,
        "source_pages": [fragment.page for fragment in packet.pdf_fragments],
        "cp3_result_sha256": CP3_RESULT_SHA256,
        "raw_candidates": [
            {
                "kind": item.kind,
                "handle": item.handle,
                "fields": copy.deepcopy(dict(item.fields)),
                "source_authority": item.source_authority,
            }
            for item in result.bundle.objects
        ],
        "validation": {"adapter_response_schema": "passed"},
    }
    try:
        canonical = CanonicalIdAllocator().canonicalize(result.bundle)
    except CandidateValidationError as exc:
        output["validation"]["candidate_id_allocation"] = "failed"
        output["validation"]["failure_summary"] = str(exc)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(output, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        raise TechnicalFailure("remote_cp4_experiment", str(exc)) from exc

    output["canonical_objects"] = [
        {"kind": kind, "fields": fields} for kind, fields in canonical
    ]
    output["validation"]["candidate_id_allocation"] = "passed"
    try:
        gdu_schema = load_json(ROOT / "gdu.schema.json")
        for kind, fields in canonical:
            if kind != "relation":
                raise TechnicalFailure(
                    "remote_cp4_experiment", f"unexpected CP4 object kind: {kind}"
                )
            validate(fields, sub_schema(gdu_schema, "relation"), kind)
        output["validation"]["gdu_field_schemas"] = "passed"
        verify_cp4_semantics(canonical)
        output["validation"]["cp4_semantic_acceptance"] = "passed"
    except TechnicalFailure as exc:
        output["validation"]["cp4_semantic_acceptance"] = "failed"
        output["validation"]["failure_component"] = exc.component
        output["validation"]["failure_summary"] = exc.summary
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(output, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print("REMOTE_CP4_REJECTED")
        print(f"CALLS_MADE {transport.calls_made}")
        print(f"OUTPUT {args.output}")
        raise

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("REMOTE_CP4_OK")
    print(f"CALLS_MADE {transport.calls_made}")
    print(f"OBJECTS {len(canonical)}")
    print(f"OUTPUT {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
