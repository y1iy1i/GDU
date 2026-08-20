from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

import jsonschema

from gdu.adapter_v1 import (
    OpenAICompatibleRemoteTransport,
    StructuredUnderstandingAdapter,
    load_remote_transport_config,
    sha256_file,
)
from gdu.builder_v0.source_reader import PypdfBackend, SourceReader
from gdu.builder_v0.types import SourceRequest, TechnicalFailure


ROOT = Path(__file__).resolve().parents[1]
SOURCE_SHA256 = "fbb9875c7eca1f921ca0635cabbe53727b7ff57658750fa0eeefd92402730c59"
TEXT_SHA256 = "d3258943647ba57408471fd43ece8d52415e75ec4f39df16c63861d4af450c9a"
CP2_RESULT_SHA256 = "e7362cd825c59653332a6d9eea78fb469f5ac48437b615046433bad8918f03e9"
CP3_RESULT_SHA256 = "8957412dcc9ac4e7e151eb3f65bdca0c9b4e824b5ddacfc6f9e320804dacd148"
CP4_RESULT_SHA256 = "89bf0d5a6457bd35afd4d603871e2a04bf1e6d1d101bc021b6b449054cc9796d"
DOCUMENT_ID = "litong-2025-annual-report"
ASSERTION_IDS = {f"A-{value:03d}" for value in range(1, 9)}
RELATION_IDS = {f"R-{value:03d}" for value in range(1, 6)}
UNIT_IDS = {"U-001"}
GROUP_IDS = {"IG-001"}
PLAN_SECTIONS = (
    "purpose",
    "core_meaning",
    "content_selection",
    "organization",
    "constraints",
)


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
            "remote_cp5_experiment",
            f"invalid {label} at {location}: {first.message}",
        )


def load_prerequisites(cp2_path: Path, cp3_path: Path, cp4_path: Path) -> dict[str, Any]:
    expected = (
        (cp2_path, CP2_RESULT_SHA256, "CP2"),
        (cp3_path, CP3_RESULT_SHA256, "CP3"),
        (cp4_path, CP4_RESULT_SHA256, "CP4"),
    )
    values: dict[str, dict[str, Any]] = {}
    for path, digest, label in expected:
        if file_sha256(path) != digest:
            raise TechnicalFailure(
                "remote_cp5_experiment", f"accepted {label} result SHA-256 mismatch"
            )
        values[label] = load_json(path)

    cp2_objects = values["CP2"].get("canonical_objects", [])
    cp3_objects = values["CP3"].get("canonical_objects", [])
    cp4_objects = values["CP4"].get("canonical_objects", [])
    observed_assertions = {
        item["fields"]["id"]
        for item in cp2_objects + cp3_objects
        if item.get("kind") == "assertion"
    }
    observed_relations = {
        item["fields"]["id"]
        for item in cp4_objects
        if item.get("kind") == "relation"
    }
    if observed_assertions != ASSERTION_IDS or observed_relations != RELATION_IDS:
        raise TechnicalFailure(
            "remote_cp5_experiment", "prerequisite object IDs are incomplete"
        )
    return {
        "semantic_units_and_cp2_assertions": copy.deepcopy(cp2_objects),
        "cp3_assertions_and_interpretation_group": copy.deepcopy(cp3_objects),
        "cp4_relations": copy.deepcopy(cp4_objects),
        "prerequisite_hashes": {
            "cp2": CP2_RESULT_SHA256,
            "cp3": CP3_RESULT_SHA256,
            "cp4": CP4_RESULT_SHA256,
        },
    }


def empty_refs() -> dict[str, list[str]]:
    return {
        "assertion_refs": [],
        "semantic_unit_refs": [],
        "relation_refs": [],
        "interpretation_group_refs": [],
    }


def cp5_guidance() -> dict[str, Any]:
    return {
        "experiment_scope": (
            "CP5 local generative-plan prototype only. Reorganize the accepted "
            "objects for the second-section sample. Never present it as a plan for "
            "the complete 237-page annual report."
        ),
        "allowed_refs": {
            "assertions": sorted(ASSERTION_IDS),
            "semantic_units": sorted(UNIT_IDS),
            "relations": sorted(RELATION_IDS),
            "interpretation_groups": sorted(GROUP_IDS),
        },
        "required_plan": {
            "purpose": {
                "summary_requirement": "说明局部单元帮助读者理解利润口径、构成与改善原因。",
                **empty_refs(),
                "assertion_refs": ["A-004"],
                "semantic_unit_refs": ["U-001"],
            },
            "core_meaning": {
                "summary_requirement": "同时保留利润口径差异、经营改善、投资公允价值影响和不能排序的边界。",
                **empty_refs(),
                "assertion_refs": [
                    "A-001", "A-002", "A-003", "A-005",
                    "A-006", "A-007", "A-008",
                ],
                "relation_refs": ["R-001", "R-002", "R-003", "R-004", "R-005"],
                "interpretation_group_refs": ["IG-001"],
            },
            "content_selection": {
                "summary_requirement": "选择三项利润口径和原文列出的改善原因，形成最小充分材料。",
                **empty_refs(),
                "assertion_refs": ["A-001", "A-002", "A-003", "A-005"],
            },
            "organization": {
                "summary_requirement": "先讲利润口径，再讲两个并行解释，最后讲不确定性约束。",
                **empty_refs(),
                "relation_refs": ["R-001", "R-002", "R-003", "R-004", "R-005"],
                "interpretation_group_refs": ["IG-001"],
            },
            "constraints": {
                "summary_requirement": "明确仅覆盖第二节局部样本，不代表整份年报，且不能给因素排序。",
                **empty_refs(),
                "assertion_refs": ["A-008"],
                "relation_refs": ["R-004", "R-005"],
                "interpretation_group_refs": ["IG-001"],
            },
        },
        "plan_section_shape": {
            "summary": "只压缩和组织已引用对象，不新增事实。",
            **empty_refs(),
            "assertion_refs": ["A-001"],
        },
        "response_checklist": [
            "generative_plan must contain exactly purpose, core_meaning, content_selection, organization, constraints",
            "Every section must contain summary and all four reference arrays, including empty arrays",
            "Use the exact required references for every section; do not add or omit references",
            "objects, mutations, and revisions must all be empty arrays",
            "manifest and stop_gate must be absent",
            "No summary may introduce a number, cause, ranking, or company-wide claim absent from accepted assertions",
            "constraints must explicitly say this is limited to the second-section local sample and not the complete annual report",
            "constraints must explicitly preserve the inability to rank the disclosed profit drivers",
            "organization must state the order: profit measures, parallel explanations, uncertainty boundary",
            "Use concise Simplified Chinese throughout",
            "contract_version gdu-adapter-v1, mode propose, stage cp5",
            "observed_run_identity must exactly copy request.run_identity",
        ],
    }


def verify_cp5_semantics(plan: Mapping[str, Any]) -> None:
    if set(plan) != set(PLAN_SECTIONS):
        raise TechnicalFailure(
            "remote_cp5_experiment", "generative plan section set is incorrect"
        )
    guidance = cp5_guidance()["required_plan"]
    for name in PLAN_SECTIONS:
        section = plan[name]
        expected = guidance[name]
        for field, allowed in (
            ("assertion_refs", ASSERTION_IDS),
            ("semantic_unit_refs", UNIT_IDS),
            ("relation_refs", RELATION_IDS),
            ("interpretation_group_refs", GROUP_IDS),
        ):
            if not set(section[field]).issubset(allowed):
                raise TechnicalFailure(
                    "remote_cp5_experiment", f"{name} uses unknown {field}"
                )
            if section[field] != expected[field]:
                raise TechnicalFailure(
                    "remote_cp5_experiment", f"{name} reference set differs from preregistration"
                )

    core = plan["core_meaning"]["summary"]
    if "扣非" not in core and "利润口径" not in core:
        raise TechnicalFailure(
            "remote_cp5_experiment", "core meaning omitted the profit-measure distinction"
        )
    for concept in ("经营", "投资", "不能"):
        if concept not in core:
            raise TechnicalFailure(
                "remote_cp5_experiment", f"core meaning omitted {concept}"
            )
    organization = plan["organization"]["summary"]
    if not all(term in organization for term in ("先", "再", "最后")):
        raise TechnicalFailure(
            "remote_cp5_experiment", "organization does not state the required order"
        )
    constraints = plan["constraints"]["summary"]
    if not (
        ("第二节" in constraints or "局部" in constraints)
        and ("整份" in constraints or "全文" in constraints)
        and ("不能" in constraints or "不得" in constraints)
        and ("排序" in constraints or "贡献最大" in constraints)
    ):
        raise TechnicalFailure(
            "remote_cp5_experiment", "constraints do not preserve scope and uncertainty"
        )
    forbidden_claims = ("整份年报表明", "公司全年主要由", "唯一原因", "主导因素")
    summaries = "\n".join(plan[name]["summary"] for name in PLAN_SECTIONS)
    if any(term in summaries for term in forbidden_claims):
        raise TechnicalFailure(
            "remote_cp5_experiment", "plan overgeneralizes the local sample"
        )
    allowed_numbers = {
        "2025", "292,589,095.99", "235,942,443.22", "56,646,652.77",
    }
    observed_numbers = set(re.findall(r"\d[\d,.]*", summaries))
    if not observed_numbers.issubset(allowed_numbers):
        raise TechnicalFailure(
            "remote_cp5_experiment", "plan introduced an unregistered number"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--text", type=Path, required=True)
    parser.add_argument("--cp2-result", type=Path, required=True)
    parser.add_argument("--cp3-result", type=Path, required=True)
    parser.add_argument("--cp4-result", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if file_sha256(args.text) != TEXT_SHA256:
        raise TechnicalFailure(
            "remote_cp5_experiment", "extracted text SHA-256 mismatch"
        )
    accepted_state = load_prerequisites(
        args.cp2_result, args.cp3_result, args.cp4_result
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
            purpose="Organize the accepted local objects into a bounded CP5 plan prototype.",
            page_ranges=((9, 12),),
            modalities=("text",),
            locator_hints=("利润口径", "利润增长原因", "非经常性损益"),
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
        "cp5_experiment_guidance": cp5_guidance(),
    }
    result = adapter.propose("cp5", packet, public_view)
    if result.bundle is None or result.bundle.generative_plan is None:
        raise TechnicalFailure("remote_cp5_experiment", "CP5 returned no plan")

    plan = copy.deepcopy(dict(result.bundle.generative_plan))
    output: dict[str, Any] = {
        "experiment": f"remote-cp5-{remote.model}-v1",
        "result_summary": result.result_summary,
        "calls_made": transport.calls_made,
        "source_pages": [fragment.page for fragment in packet.pdf_fragments],
        "prerequisite_hashes": accepted_state["prerequisite_hashes"],
        "generative_plan": plan,
        "validation": {"adapter_response_schema": "passed"},
    }
    try:
        if result.bundle.objects:
            raise TechnicalFailure(
                "remote_cp5_experiment", "CP5 returned unauthorized objects"
            )
        gdu_schema = load_json(ROOT / "gdu.schema.json")
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$defs": copy.deepcopy(gdu_schema["$defs"]),
            "$ref": "#/$defs/generativePlan",
        }
        validate(plan, schema, "generative_plan")
        output["validation"]["gdu_plan_schema"] = "passed"
        verify_cp5_semantics(plan)
        output["validation"]["cp5_semantic_acceptance"] = "passed"
    except TechnicalFailure as exc:
        output["validation"]["cp5_semantic_acceptance"] = "failed"
        output["validation"]["failure_component"] = exc.component
        output["validation"]["failure_summary"] = exc.summary
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(output, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print("REMOTE_CP5_REJECTED")
        print(f"CALLS_MADE {transport.calls_made}")
        print(f"OUTPUT {args.output}")
        raise

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("REMOTE_CP5_OK")
    print(f"CALLS_MADE {transport.calls_made}")
    print(f"OUTPUT {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
