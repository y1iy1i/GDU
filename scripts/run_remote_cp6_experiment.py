from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from gdu.adapter_v1 import (
    OpenAICompatibleRemoteTransport,
    StructuredUnderstandingAdapter,
    load_remote_transport_config,
    sha256_file,
)
from gdu.builder_v0.source_reader import PypdfBackend, SourceReader
from gdu.builder_v0.types import SourceRequest, StopGateResult, TechnicalFailure


ROOT = Path(__file__).resolve().parents[1]
SOURCE_SHA256 = "fbb9875c7eca1f921ca0635cabbe53727b7ff57658750fa0eeefd92402730c59"
TEXT_SHA256 = "d3258943647ba57408471fd43ece8d52415e75ec4f39df16c63861d4af450c9a"
CP5_RESULT_SHA256 = "938a5c0b080af3890db87e4ac8a85293e609286c4106bbd5a09949698152d751"
DOCUMENT_ID = "litong-2025-annual-report"
EXPECTED_STATUSES = {
    "coverage": "failed",
    "evidence": "passed",
    "stability": "passed",
    "cross_carrier": "failed",
    "cross_section": "failed",
    "negative_boundary": "passed",
}


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def gate_json(gate: StopGateResult) -> dict[str, Any]:
    return {
        "coverage": gate.coverage,
        "evidence": gate.evidence,
        "stability": gate.stability,
        "cross_carrier": gate.cross_carrier,
        "cross_section": gate.cross_section,
        "negative_boundary": gate.negative_boundary,
        "gaps": [
            {
                "gap_id": gap.gap_id,
                "gate_dimension": gap.gate_dimension,
                "check_kind": gap.check_kind,
                "affected_refs": list(gap.affected_refs),
                "source_scope": [
                    {"start": start, "end": end}
                    for start, end in gap.source_scope
                ],
                "reason": gap.reason,
                "earliest_checkpoint": gap.earliest_checkpoint,
                "requested_action": gap.requested_action,
            }
            for gap in gate.gaps
        ],
        "summary": gate.summary,
    }


def verify_cp6_gate(gate: Mapping[str, Any]) -> None:
    for field, expected in EXPECTED_STATUSES.items():
        if gate.get(field) != expected:
            raise TechnicalFailure(
                "remote_cp6_experiment", f"unexpected {field} status"
            )
    gaps = gate.get("gaps", [])
    if len(gaps) != 3:
        raise TechnicalFailure(
            "remote_cp6_experiment", "expected exactly three blocking gaps"
        )
    by_kind = {item["check_kind"]: item for item in gaps}
    if set(by_kind) != {"ordinary", "cross_carrier", "cross_section"}:
        raise TechnicalFailure(
            "remote_cp6_experiment", "required gap kinds are incomplete"
        )
    coverage_ranges = {
        (item["start"], item["end"])
        for item in by_kind["ordinary"]["source_scope"]
    }
    if coverage_ranges != {(2, 7), (13, 237)}:
        raise TechnicalFailure(
            "remote_cp6_experiment", "coverage gap does not identify unmodeled pages"
        )
    if by_kind["ordinary"]["earliest_checkpoint"] != "cp1":
        raise TechnicalFailure(
            "remote_cp6_experiment", "coverage gap must return to CP1"
        )
    if by_kind["cross_carrier"]["earliest_checkpoint"] != "cp1":
        raise TechnicalFailure(
            "remote_cp6_experiment", "carrier gap must return to CP1"
        )
    if by_kind["cross_section"]["earliest_checkpoint"] != "cp2":
        raise TechnicalFailure(
            "remote_cp6_experiment", "cross-section gap must return to CP2"
        )
    summary = gate.get("summary", "")
    if not (
        "局部" in summary
        and ("不能冻结" in summary or "不得冻结" in summary or "拒绝冻结" in summary)
    ):
        raise TechnicalFailure(
            "remote_cp6_experiment", "summary does not explicitly refuse full freeze"
        )


def cp6_guidance() -> dict[str, Any]:
    return {
        "experiment_scope": (
            "CP6 stop-gate audit. The current work is only a local prototype for "
            "the second section. The correct outcome must refuse freezing a complete-document GDU."
        ),
        "scope_ledger": {
            "document_physical_pages": 237,
            "pages_observed_for_structure": [1, 8, 9, 10, 11, 12],
            "pages_with_semantic_modeling": [8, 9, 10, 11, 12],
            "modeled_section": "第二节 公司简介和主要财务指标",
            "unmodeled_page_ranges": [
                {"start": 2, "end": 7},
                {"start": 13, "end": 237},
            ],
            "source_modality_verified": "PDF text layer only",
            "visual_tables_images_formulas_verified": False,
            "cross_section_relations_verified": False,
            "negative_boundary_for_local_unit_verified": True,
        },
        "required_stop_gate": {
            **EXPECTED_STATUSES,
            "gaps": [
                {
                    "gap_id": "gap-full-document-coverage",
                    "gate_dimension": "coverage",
                    "check_kind": "ordinary",
                    "affected_refs": ["PS-001"],
                    "source_scope": [
                        {"start": 2, "end": 7},
                        {"start": 13, "end": 237},
                    ],
                    "reason": "除封面和第二节局部样本外，其余页面尚未建立结构与语义覆盖。",
                    "earliest_checkpoint": "cp1",
                    "requested_action": "扩展结构读取，并按章节建立后续语义单元。",
                },
                {
                    "gap_id": "gap-cross-carrier-verification",
                    "gate_dimension": "evidence",
                    "check_kind": "cross_carrier",
                    "affected_refs": ["E-003", "E-004", "E-005", "E-006"],
                    "source_scope": [{"start": 9, "end": 12}],
                    "reason": "当前只核验PDF文本层，尚未核验表格视觉结构及其他载体。",
                    "earliest_checkpoint": "cp1",
                    "requested_action": "读取并核验表格或其他视觉载体，再确认对应证据。",
                },
                {
                    "gap_id": "gap-cross-section-relations",
                    "gate_dimension": "coverage",
                    "check_kind": "cross_section",
                    "affected_refs": ["U-001"],
                    "source_scope": [{"start": 13, "end": 237}],
                    "reason": "只建立第二节局部单元，无法检查与其他章节的功能和关系。",
                    "earliest_checkpoint": "cp2",
                    "requested_action": "建立其他主要章节语义单元后再执行跨章节关系检查。",
                },
            ],
            "summary_requirement": "明确说明局部样本通过不等于完整文档通过，当前不能冻结完整GDU。",
        },
        "response_checklist": [
            "Return the required stop_gate statuses and exactly three gaps",
            "Do not change any source_scope, earliest_checkpoint, check_kind, or affected_refs",
            "objects, mutations, and revisions must be empty arrays",
            "manifest and generative_plan must be absent",
            "The summary must explicitly refuse freezing a complete-document GDU",
            "Use concise Simplified Chinese throughout",
            "contract_version gdu-adapter-v1, mode propose, stage cp6",
            "observed_run_identity must exactly copy request.run_identity",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--text", type=Path, required=True)
    parser.add_argument("--cp5-result", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if file_sha256(args.text) != TEXT_SHA256:
        raise TechnicalFailure(
            "remote_cp6_experiment", "extracted text SHA-256 mismatch"
        )
    if file_sha256(args.cp5_result) != CP5_RESULT_SHA256:
        raise TechnicalFailure(
            "remote_cp6_experiment", "accepted CP5 result SHA-256 mismatch"
        )
    cp5 = load_json(args.cp5_result)
    reader = SourceReader(
        args.pdf,
        DOCUMENT_ID,
        PypdfBackend(),
        expected_source_sha256=SOURCE_SHA256,
    )
    reader.inspect()
    packet = reader.read(
        SourceRequest(
            purpose="Audit whether the local prototype may freeze as a complete GDU.",
            page_ranges=((1, 1), (8, 12)),
            modalities=("text",),
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
    result = adapter.propose(
        "cp6",
        packet,
        {
            "accepted_local_generative_plan": cp5["generative_plan"],
            "cp5_result_sha256": CP5_RESULT_SHA256,
            "cp6_experiment_guidance": cp6_guidance(),
        },
    )
    if result.bundle is not None or result.stop_gate is None:
        raise TechnicalFailure(
            "remote_cp6_experiment", "CP6 returned objects or omitted stop gate"
        )
    gate = gate_json(result.stop_gate)
    output = {
        "experiment": f"remote-cp6-{remote.model}-v1",
        "result_summary": result.result_summary,
        "calls_made": transport.calls_made,
        "cp5_result_sha256": CP5_RESULT_SHA256,
        "stop_gate": gate,
        "validation": {"adapter_response_schema": "passed"},
    }
    try:
        verify_cp6_gate(gate)
        output["validation"]["cp6_stop_gate_acceptance"] = "passed"
        output["publication_decision"] = "provisional_only_do_not_freeze"
    except TechnicalFailure as exc:
        output["validation"]["cp6_stop_gate_acceptance"] = "failed"
        output["validation"]["failure_summary"] = exc.summary
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(output, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        raise
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("REMOTE_CP6_OK_PROVISIONAL_ONLY")
    print(f"CALLS_MADE {transport.calls_made}")
    print(f"OUTPUT {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
