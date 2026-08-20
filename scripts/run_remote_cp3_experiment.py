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
    CandidateBundle,
    CandidateObject,
    CandidateValidationError,
    SourceRequest,
    TechnicalFailure,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE_SHA256 = "fbb9875c7eca1f921ca0635cabbe53727b7ff57658750fa0eeefd92402730c59"
TEXT_SHA256 = "d3258943647ba57408471fd43ece8d52415e75ec4f39df16c63861d4af450c9a"
CP2_RESULT_SHA256 = "e7362cd825c59653332a6d9eea78fb469f5ac48437b615046433bad8918f03e9"
DOCUMENT_ID = "litong-2025-annual-report"
EXISTING_ASSERTIONS = {"A-001", "A-002", "A-003", "A-004"}
EXISTING_EVIDENCE = {f"E-{value:03d}" for value in range(2, 7)}


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
            "remote_cp3_experiment",
            f"invalid {label} at {location}: {first.message}",
        )


def load_accepted_cp2(path: Path) -> dict[str, Any]:
    if file_sha256(path) != CP2_RESULT_SHA256:
        raise TechnicalFailure(
            "remote_cp3_experiment", "accepted CP2 result SHA-256 mismatch"
        )
    value = load_json(path)
    validation = value.get("validation", {})
    if validation.get("cp2_semantic_acceptance") != "passed":
        raise TechnicalFailure(
            "remote_cp3_experiment", "CP2 prerequisite was not accepted"
        )
    return {
        "accepted_cp1": copy.deepcopy(value["accepted_cp1"]),
        "accepted_cp2_objects": copy.deepcopy(value["canonical_objects"]),
        "source_result_sha256": CP2_RESULT_SHA256,
    }


def cp3_guidance() -> dict[str, Any]:
    return {
        "experiment_scope": (
            "CP3 only. Examine why 2025 profit increased. Preserve two parallel, "
            "evidence-backed explanatory aspects: operating improvement and positive "
            "fair-value change from external investment. Also state the uncertainty "
            "boundary that the supplied pages do not quantify each driver's relative contribution."
        ),
        "allowed_candidate_kinds": ["assertion", "interpretation_group"],
        "existing_refs": {
            "semantic_unit": ["U-001"],
            "assertions": ["A-001", "A-002", "A-003", "A-004"],
            "evidence": ["E-002", "E-003", "E-004", "E-005", "E-006"],
        },
        "required_candidates": [
            "One source-attributed content assertion copying the report's stated profit-growth drivers from page 9",
            "One analytic interpretation for the operating-improvement aspect",
            "One analytic interpretation for the external-investment fair-value aspect",
            "One analytic constraint stating that relative contributions cannot be ranked from the supplied disclosure",
            "One parallel interpretation_group containing the two analytic explanatory aspects",
        ],
        "source_assertion_shape": {
            "kind": "content",
            "statement": "准确表述第9页列出的利润增长原因。",
            "semantic_unit_refs": ["U-001"],
            "epistemic_origin": "source_attributed",
            "assessment_complete": True,
            "evidence_status": "supported",
            "evidence_refs": ["E-003"],
            "rationale": "第9页直接列示原因。",
            "actor": "江苏利通电子股份有限公司",
            "attribution_mode": "explicit",
        },
        "analytic_assertion_shape": {
            "kind": "content",
            "statement": "只表达一个有证据支持的解释方面。",
            "semantic_unit_refs": ["U-001"],
            "epistemic_origin": "analytic_interpretation",
            "assessment_complete": True,
            "evidence_status": "supported",
            "evidence_refs": ["E-003"],
            "rationale": "说明该解释如何由来源断言和对应页面支持。",
            "basis_assertion_refs": ["@profit_driver_source"],
        },
        "uncertainty_constraint_shape": {
            "kind": "constraint",
            "statement": "现有披露未量化各因素的相对贡献，不能判断哪一项贡献最大。",
            "semantic_unit_refs": ["U-001"],
            "epistemic_origin": "analytic_interpretation",
            "assessment_complete": True,
            "evidence_status": "undetermined",
            "evidence_refs": ["E-003", "E-005", "E-006"],
            "rationale": "页面列出多个原因及部分金额，但没有完整贡献分解。",
            "basis_assertion_refs": [
                "@profit_driver_source",
                "@operating_aspect",
                "@investment_aspect",
            ],
        },
        "parallel_group_shape": {
            "issue": "2025年利润改善应从哪些方面理解？",
            "mode": "parallel",
            "member_refs": ["@operating_aspect", "@investment_aspect"],
            "rationale": "两个方面都有来源支持，并非互相排斥。",
            "unresolved_reason": "披露没有量化各因素的相对贡献，不能进行可靠排序。",
            "impact_scope": "仅影响对2025年利润改善来源及质量的解释。",
        },
        "reference_rule": (
            "References to existing objects use their canonical IDs directly. EVERY "
            "reference to a new object MUST use @ followed by the exact candidate "
            "handle. Never invent new canonical A- or IG- identifiers. Candidate "
            "fields MUST NOT contain an id key; only the candidate wrapper has handle."
        ),
        "response_checklist": [
            "Return exactly four assertions and one interpretation_group",
            "No candidate fields object may contain id; the Builder assigns every new canonical ID",
            "The interpretation_group mode must be parallel and preferred_ref must be absent",
            "The parallel group must contain only the two analytic explanatory aspects",
            "Every analytic_interpretation must include non-empty basis_assertion_refs",
            "The uncertainty constraint must use evidence_status undetermined",
            "Do not claim that any one driver is largest, dominant, primary, or fully causal",
            "Do not create evidence, structure, semantic units, relations, or a generative plan",
            "Use concise Simplified Chinese throughout",
            "contract_version must be gdu-adapter-v1, mode propose, stage cp3",
            "mutations and revisions must be empty arrays",
            "observed_run_identity must exactly copy request.run_identity",
        ],
    }


def seeded_allocator() -> CanonicalIdAllocator:
    allocator = CanonicalIdAllocator()
    seeds = [
        CandidateObject("semantic_unit", "prior_unit", {}),
        *[
            CandidateObject("assertion", f"prior_assertion_{index}", {})
            for index in range(1, 5)
        ],
    ]
    allocator.canonicalize(CandidateBundle(stage="cp2", objects=tuple(seeds)))
    return allocator


def verify_cp3_semantics(canonical: list[tuple[str, dict[str, Any]]]) -> None:
    assertions = [fields for kind, fields in canonical if kind == "assertion"]
    groups = [fields for kind, fields in canonical if kind == "interpretation_group"]
    if len(assertions) != 4 or len(groups) != 1:
        raise TechnicalFailure(
            "remote_cp3_experiment", "expected four assertions and one group"
        )

    new_assertion_ids = {item["id"] for item in assertions}
    all_assertion_ids = EXISTING_ASSERTIONS | new_assertion_ids
    for item in assertions:
        if set(item.get("semantic_unit_refs", [])) != {"U-001"}:
            raise TechnicalFailure(
                "remote_cp3_experiment", "assertion escaped semantic unit U-001"
            )
        if not set(item["evidence_refs"]).issubset(EXISTING_EVIDENCE):
            raise TechnicalFailure(
                "remote_cp3_experiment", "assertion used unknown evidence"
            )
        if not set(item.get("basis_assertion_refs", [])).issubset(all_assertion_ids):
            raise TechnicalFailure(
                "remote_cp3_experiment", "assertion used unknown basis"
            )

    source_items = [
        item
        for item in assertions
        if item.get("epistemic_origin") == "source_attributed"
    ]
    if len(source_items) != 1:
        raise TechnicalFailure(
            "remote_cp3_experiment", "expected one source-attributed driver assertion"
        )
    source_text = source_items[0]["statement"]
    for phrase in ("算力", "制造", "公允价值"):
        if phrase not in source_text:
            raise TechnicalFailure(
                "remote_cp3_experiment", f"source driver assertion omitted {phrase}"
            )
    if "E-003" not in source_items[0]["evidence_refs"]:
        raise TechnicalFailure(
            "remote_cp3_experiment", "driver assertion is not linked to page 9"
        )

    analytic = [
        item
        for item in assertions
        if item.get("epistemic_origin") == "analytic_interpretation"
    ]
    operating = [
        item
        for item in analytic
        if "算力" in item["statement"] or "制造" in item["statement"]
    ]
    investment = [
        item
        for item in analytic
        if "投资" in item["statement"] or "公允价值" in item["statement"]
    ]
    uncertainty = [
        item
        for item in analytic
        if item.get("kind") == "constraint"
        and item.get("evidence_status") == "undetermined"
        and any(term in item["statement"] for term in ("不能", "无法", "未量化"))
    ]
    if not operating or not investment or len(uncertainty) != 1:
        raise TechnicalFailure(
            "remote_cp3_experiment",
            "required operating, investment, or uncertainty assertion is missing",
        )

    group = groups[0]
    if group["mode"] != "parallel" or "preferred_ref" in group:
        raise TechnicalFailure(
            "remote_cp3_experiment", "interpretation group is not unbiased parallel"
        )
    group_members = set(group["member_refs"])
    if len(group_members) != 2 or not group_members.issubset(new_assertion_ids):
        raise TechnicalFailure(
            "remote_cp3_experiment", "parallel group has invalid members"
        )
    if not any(item["id"] in group_members for item in operating):
        raise TechnicalFailure(
            "remote_cp3_experiment", "parallel group omitted operating aspect"
        )
    if not any(item["id"] in group_members for item in investment):
        raise TechnicalFailure(
            "remote_cp3_experiment", "parallel group omitted investment aspect"
        )
    explanatory_members = [
        item for item in analytic if item["id"] in group_members
    ]
    forbidden = ("最大", "主导", "首要", "唯一原因", "完全由")
    if any(
        term in item["statement"]
        for item in explanatory_members
        for term in forbidden
    ):
        raise TechnicalFailure(
            "remote_cp3_experiment", "interpretation over-ranked unquantified drivers"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--text", type=Path, required=True)
    parser.add_argument("--cp2-result", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if file_sha256(args.text) != TEXT_SHA256:
        raise TechnicalFailure(
            "remote_cp3_experiment", "extracted text SHA-256 mismatch"
        )
    accepted_state = load_accepted_cp2(args.cp2_result)
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
                "Assess parallel explanations and the uncertainty boundary for "
                "2025 profit improvement within the accepted local semantic unit."
            ),
            page_ranges=((9, 12),),
            modalities=("text",),
            locator_hints=(
                "利润总额、归母净利润较上年同期大幅增长",
                "算力业务端盈利增加",
                "制造端业务亏损收窄",
                "对外投资公允价值正向变动",
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
        **accepted_state,
        "cp3_experiment_guidance": cp3_guidance(),
    }
    result = adapter.propose("cp3", packet, public_view)
    if result.bundle is None:
        raise TechnicalFailure("remote_cp3_experiment", "CP3 returned no bundle")

    output: dict[str, Any] = {
        "experiment": f"remote-cp3-{remote.model}-v1",
        "result_summary": result.result_summary,
        "calls_made": transport.calls_made,
        "source_pages": [fragment.page for fragment in packet.pdf_fragments],
        "cp2_result_sha256": CP2_RESULT_SHA256,
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
        canonical = seeded_allocator().canonicalize(result.bundle)
    except CandidateValidationError as exc:
        output["validation"]["candidate_id_allocation"] = "failed"
        output["validation"]["failure_component"] = "remote_cp3_experiment"
        output["validation"]["failure_summary"] = str(exc)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(output, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print("REMOTE_CP3_REJECTED")
        print(f"CALLS_MADE {transport.calls_made}")
        print(f"OUTPUT {args.output}")
        raise TechnicalFailure("remote_cp3_experiment", str(exc)) from exc

    output.update({
        "canonical_objects": [
            {"kind": kind, "fields": fields} for kind, fields in canonical
        ],
    })
    output["validation"]["candidate_id_allocation"] = "passed"
    try:
        gdu_schema = load_json(ROOT / "gdu.schema.json")
        for kind, fields in canonical:
            schema_name = {
                "assertion": "assertion",
                "interpretation_group": "interpretationGroup",
            }.get(kind)
            if schema_name is None:
                raise TechnicalFailure(
                    "remote_cp3_experiment", f"unexpected CP3 object kind: {kind}"
                )
            validate(fields, sub_schema(gdu_schema, schema_name), kind)
        output["validation"]["gdu_field_schemas"] = "passed"
        verify_cp3_semantics(canonical)
        output["validation"]["cp3_semantic_acceptance"] = "passed"
    except TechnicalFailure as exc:
        output["validation"]["cp3_semantic_acceptance"] = "failed"
        output["validation"]["failure_component"] = exc.component
        output["validation"]["failure_summary"] = exc.summary
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(output, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print("REMOTE_CP3_REJECTED")
        print(f"CALLS_MADE {transport.calls_made}")
        print(f"OUTPUT {args.output}")
        raise

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("REMOTE_CP3_OK")
    print(f"CALLS_MADE {transport.calls_made}")
    print(f"OBJECTS {len(canonical)}")
    print(f"OUTPUT {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
