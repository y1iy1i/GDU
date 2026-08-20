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
TARGET_FACTS = {
    "292,589,095.99": "E-003",
    "235,942,443.22": "E-003",
    "56,646,652.77": "E-005",
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
            "remote_cp2_experiment",
            f"invalid {label} at {location}: {first.message}",
        )


def accepted_cp1_view(packet: Any) -> dict[str, Any]:
    evidence = []
    evidence_refs = []
    for fragment in packet.pdf_fragments:
        evidence_id = f"E-{fragment.page - 6:03d}"
        evidence_refs.append(evidence_id)
        evidence.append(
            {
                "id": evidence_id,
                "modality": "text",
                "fragments": [fragment.as_evidence_fragment()],
            }
        )
    return {
        "physical_structure": [
            {
                "id": "PS-002",
                "parent_ref": "PS-001",
                "node_type": "section",
                "original_label": "第二节 公司简介和主要财务指标",
                "order": 2,
                "page_range": {"start": 8, "end": 12},
                "evidence_refs": evidence_refs,
                "observation_note": "CP1 已通过边界实验。",
            }
        ],
        "evidence": evidence,
    }


def cp2_guidance() -> dict[str, Any]:
    return {
        "experiment_scope": (
            "CP2 only. Build one minimal semantic unit about the relationship among "
            "2025 net profit attributable to shareholders, the corresponding profit "
            "after non-recurring items, and total non-recurring gains or losses."
        ),
        "allowed_candidate_kinds": ["semantic_unit", "assertion"],
        "reference_rule": (
            "Use existing PS-002 and E-002 through E-006 directly. EVERY reference "
            "to a new object in this response MUST be @ followed by that candidate's "
            "exact handle. Never invent SU-, CA-, FA-, U-, or A- identifiers. The "
            "Builder alone assigns canonical IDs. Do not create evidence or structure."
        ),
        "exact_handle_example": {
            "candidate_handles": [
                "profit_unit",
                "net_profit_fact",
                "nonrecurring_fact",
                "profit_function",
            ],
            "semantic_unit_primary_function_ref": "@profit_function",
            "assertion_semantic_unit_refs": ["@profit_unit"],
            "function_basis_assertion_refs": [
                "@net_profit_fact",
                "@nonrecurring_fact",
            ],
            "invalid_examples": [
                "SU-2025-profit",
                "FA-2025-profit",
                "U-001",
                "A-001",
            ],
        },
        "semantic_unit_shape": {
            "physical_structure_refs": ["PS-002"],
            "evidence_refs": ["E-003", "E-005"],
            "summary": "A concise evidence-grounded description of what the unit combines.",
            "primary_function_ref": "@function_assertion_handle",
            "secondary_function_refs": [],
        },
        "source_attributed_assertion_shape": {
            "kind": "content",
            "statement": "Copy a fact accurately from the supplied pages.",
            "semantic_unit_refs": ["@semantic_unit_handle"],
            "epistemic_origin": "source_attributed",
            "assessment_complete": True,
            "evidence_status": "supported",
            "evidence_refs": ["E-003"],
            "rationale": "State which supplied passage directly supports the fact.",
            "actor": "江苏利通电子股份有限公司",
            "attribution_mode": "explicit",
        },
        "function_assertion_shape": {
            "kind": "function",
            "statement": "Explain the role this semantic unit serves for a reader.",
            "semantic_unit_refs": ["@semantic_unit_handle"],
            "epistemic_origin": "analytic_interpretation",
            "assessment_complete": True,
            "evidence_status": "supported",
            "evidence_refs": ["E-003", "E-005"],
            "rationale": "Explain how the visible combination supports this function.",
            "basis_assertion_refs": ["@content_assertion_handle"],
            "function_tag": "evidence",
        },
        "function_assertion_mandatory_checklist": {
            "instruction": (
                "Before returning, locate the one candidate whose fields.kind is "
                "function. Its fields MUST include every key below. Omitting "
                "function_tag or basis_assertion_refs is a failed response."
            ),
            "required_field_keys": [
                "kind",
                "statement",
                "semantic_unit_refs",
                "epistemic_origin",
                "assessment_complete",
                "evidence_status",
                "evidence_refs",
                "rationale",
                "basis_assertion_refs",
                "function_tag",
            ],
            "required_values": {
                "kind": "function",
                "epistemic_origin": "analytic_interpretation",
                "function_tag": "evidence",
            },
            "basis_rule": (
                "basis_assertion_refs must contain the exact @handles of all three "
                "new source-attributed content assertions."
            ),
        },
        "response_rules": [
            "contract_version must be gdu-adapter-v1",
            "mode must be propose and stage must be cp2",
            "manifest, generative_plan, and stop_gate must be absent",
            "mutations and revisions must be empty arrays",
            "observed_run_identity must exactly copy request.run_identity",
            "source_authority must be pdf",
            "Return at least one semantic_unit, three source-attributed content assertions, and one function assertion",
            "All new-object references must use exact @handles even when a plain identifier would satisfy the JSON Schema",
            "The function assertion must contain both function_tag and basis_assertion_refs",
            "Preserve all monetary values exactly as printed; do not silently change units",
            "Do not discuss the third section even though its heading is visible on page 12",
            "Use concise Simplified Chinese for summaries, statements, and rationales",
        ],
    }


def verify_cp2_semantics(canonical: list[tuple[str, dict[str, Any]]]) -> None:
    units = [fields for kind, fields in canonical if kind == "semantic_unit"]
    assertions = [fields for kind, fields in canonical if kind == "assertion"]
    if not units:
        raise TechnicalFailure("remote_cp2_experiment", "no semantic unit returned")

    unit_ids = {item["id"] for item in units}
    assertion_ids = {item["id"] for item in assertions}
    function_ids = {
        item["id"] for item in assertions if item.get("kind") == "function"
    }
    if not function_ids:
        raise TechnicalFailure("remote_cp2_experiment", "no function assertion returned")

    allowed_evidence = {f"E-{page - 6:03d}" for page in range(8, 13)}
    for unit in units:
        if set(unit["physical_structure_refs"]) != {"PS-002"}:
            raise TechnicalFailure(
                "remote_cp2_experiment", "semantic unit escaped PS-002"
            )
        if not set(unit["evidence_refs"]).issubset(allowed_evidence):
            raise TechnicalFailure(
                "remote_cp2_experiment", "semantic unit used unknown evidence"
            )
        if unit["primary_function_ref"] not in function_ids:
            raise TechnicalFailure(
                "remote_cp2_experiment", "primary function is not a function assertion"
            )

    source_assertions = [
        item
        for item in assertions
        if item.get("kind") == "content"
        and item.get("epistemic_origin") == "source_attributed"
    ]
    for item in assertions:
        if not set(item.get("semantic_unit_refs", [])).issubset(unit_ids):
            raise TechnicalFailure(
                "remote_cp2_experiment", "assertion references an unknown semantic unit"
            )
        if not set(item["evidence_refs"]).issubset(allowed_evidence):
            raise TechnicalFailure(
                "remote_cp2_experiment", "assertion used unknown evidence"
            )
        if not set(item.get("basis_assertion_refs", [])).issubset(assertion_ids):
            raise TechnicalFailure(
                "remote_cp2_experiment", "assertion has an unknown basis reference"
            )

    target_assertion_ids = set()
    for amount, expected_evidence in TARGET_FACTS.items():
        matches = [item for item in source_assertions if amount in item["statement"]]
        if not matches:
            raise TechnicalFailure(
                "remote_cp2_experiment", f"missing preregistered fact {amount}"
            )
        if not any(expected_evidence in item["evidence_refs"] for item in matches):
            raise TechnicalFailure(
                "remote_cp2_experiment",
                f"fact {amount} is not linked to {expected_evidence}",
            )
        target_assertion_ids.update(item["id"] for item in matches)

    primary_function_ids = {unit["primary_function_ref"] for unit in units}
    primary_functions = [
        item for item in assertions if item["id"] in primary_function_ids
    ]
    if not any(
        target_assertion_ids.issubset(set(item.get("basis_assertion_refs", [])))
        for item in primary_functions
    ):
        raise TechnicalFailure(
            "remote_cp2_experiment",
            "primary function does not use all preregistered facts as its basis",
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--text", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if file_sha256(args.text) != TEXT_SHA256:
        raise TechnicalFailure(
            "remote_cp2_experiment", "extracted text SHA-256 mismatch"
        )
    reader = SourceReader(
        args.pdf,
        DOCUMENT_ID,
        PypdfBackend(),
        expected_source_sha256=SOURCE_SHA256,
    )
    reader.inspect()
    packet = reader.read(
        SourceRequest(
            purpose=(
                "Build a local semantic unit from the accepted second-section "
                "physical structure without using the visible third-section content."
            ),
            page_ranges=((8, 12),),
            modalities=("text",),
            locator_hints=(
                "归属于上市公司股东的净利润",
                "扣除非经常性损益后的净利润",
                "非经常性损益合计",
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
    response_contract = load_json(ROOT / "adapter-response-v1.schema.json")
    transport = OpenAICompatibleRemoteTransport(
        remote,
        explicit_authorization=True,
        response_contract=response_contract,
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
        "accepted_cp1": accepted_cp1_view(packet),
        "cp2_experiment_guidance": cp2_guidance(),
    }
    result = adapter.propose("cp2", packet, public_view)
    if result.bundle is None:
        raise TechnicalFailure("remote_cp2_experiment", "CP2 returned no bundle")

    canonical = CanonicalIdAllocator().canonicalize(result.bundle)
    output = {
        "experiment": f"remote-cp2-{remote.model}-v1",
        "result_summary": result.result_summary,
        "calls_made": transport.calls_made,
        "source_pages": [fragment.page for fragment in packet.pdf_fragments],
        "accepted_cp1": public_view["accepted_cp1"],
        "canonical_objects": [
            {"kind": kind, "fields": fields} for kind, fields in canonical
        ],
        "validation": {"adapter_response_schema": "passed"},
    }
    try:
        gdu_schema = load_json(ROOT / "gdu.schema.json")
        for kind, fields in canonical:
            schema_name = {
                "semantic_unit": "semanticUnit",
                "assertion": "assertion",
            }.get(kind)
            if schema_name is None:
                raise TechnicalFailure(
                    "remote_cp2_experiment", f"unexpected CP2 object kind: {kind}"
                )
            validate(fields, sub_schema(gdu_schema, schema_name), kind)
        output["validation"]["gdu_field_schemas"] = "passed"
        verify_cp2_semantics(canonical)
        output["validation"]["cp2_semantic_acceptance"] = "passed"
    except TechnicalFailure as exc:
        output["validation"]["cp2_semantic_acceptance"] = "failed"
        output["validation"]["failure_component"] = exc.component
        output["validation"]["failure_summary"] = exc.summary
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(output, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print("REMOTE_CP2_REJECTED")
        print(f"CALLS_MADE {transport.calls_made}")
        print(f"OUTPUT {args.output}")
        raise

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("REMOTE_CP2_OK")
    print(f"CALLS_MADE {transport.calls_made}")
    print(f"OBJECTS {len(canonical)}")
    print(f"OUTPUT {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
