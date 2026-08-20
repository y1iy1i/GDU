"""Promotion rules for the GB 45438-2025 normative compliance case."""

from __future__ import annotations

import re
from copy import deepcopy
from decimal import Decimal
from typing import Any, Mapping

from .promotion_v01 import (
    merge_validation_results,
    promote_candidate_transaction,
    validate_candidate_envelope,
)


REQUIRED_GATES = {
    "context_matches_gb45438_video",
    "normative_force_preserved",
    "mandatory_and_optional_language_distinguished",
    "numeric_thresholds_preserved",
    "normative_appendix_traced",
}


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()


def validate_ai_labeling_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    envelope = validate_candidate_envelope(
        candidate,
        required_gates=REQUIRED_GATES,
        expected_document_id="gb-45438-2025",
    )
    errors: list[str] = []
    evidence = {str(item["id"]): item for item in candidate.get("candidate_evidence", [])}
    if {item.get("physical_page") for item in evidence.values()} != {7, 8, 17}:
        errors.append("required_pages_missing")
    if {item.get("section") for item in evidence.values()} != {"5.4", "6.1", "appendix-e"}:
        errors.append("required_sections_missing")

    video_text = _compact(str(evidence.get("CE-GB-P7-VIDEO", {}).get("text", "")))
    for term, code in (
        ("不应少于2s", "duration_threshold_missing"),
        ("不应低于画面最短边长度的5%", "height_threshold_missing"),
        ("可位于视频末尾和中间适当位置", "optional_position_language_missing"),
    ):
        if term not in video_text:
            errors.append(code)

    appendix_text = _compact(
        str(evidence.get("CE-GB-P17-APPENDIX-E", {}).get("text", ""))
    )
    for field in ("aigc", "label", "contentproducer", "produceid", "contentpropagator", "propagateid"):
        if field not in appendix_text:
            errors.append(f"appendix_field_missing:{field}")

    claims = {str(item["id"]): item for item in candidate.get("candidate_claims", [])}
    required_claims = {
        "CC-GB-VIDEO-DURATION-OBLIGATION",
        "CC-GB-VIDEO-HEIGHT-OBLIGATION",
        "CC-GB-METADATA-OBLIGATION",
    }
    if set(claims) != required_claims:
        errors.append("candidate_claim_set_mismatch")
    for claim in claims.values():
        if claim.get("normative_force") != "obligation" or not claim.get("bearer"):
            errors.append(f"normative_annotation_missing:{claim.get('id')}")
    if any(
        "末尾" in str(claim.get("statement", "")) or "中间" in str(claim.get("statement", ""))
        for claim in claims.values()
    ):
        errors.append("optional_position_promoted_as_obligation")

    duration = str(claims.get("CC-GB-VIDEO-DURATION-OBLIGATION", {}).get("statement", ""))
    height = str(claims.get("CC-GB-VIDEO-HEIGHT-OBLIGATION", {}).get("statement", ""))
    if not all(term in duration for term in ("不应少于", "2秒")):
        errors.append("duration_obligation_changed")
    if not all(term in height for term in ("不应低于", "5%")):
        errors.append("height_obligation_changed")

    return merge_validation_results(envelope, {"errors": errors})


def _scenario_values(graph: Mapping[str, Any]) -> tuple[Decimal, Decimal]:
    claims = {str(item["id"]): item for item in graph.get("information_nodes", [])}
    try:
        duration = Decimal(str(claims["C-SCENARIO-VIDEO-DURATION"]["value"]["amount"]))
        height = Decimal(str(claims["C-SCENARIO-VIDEO-HEIGHT"]["value"]["amount"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("scenario_values_missing") from exc
    if duration != Decimal("1") or height != Decimal("0.05"):
        raise ValueError("scenario_values_changed")
    if not claims.get("C-SCENARIO-METADATA-COMPLETE", {}).get("active", True):
        raise ValueError("scenario_metadata_fact_inactive")
    return duration, height


def promote_ai_labeling_candidate(
    graph: Mapping[str, Any],
    candidate: Mapping[str, Any],
    *,
    event_id: str,
    recorded_at: str,
) -> dict[str, Any]:
    validation = validate_ai_labeling_candidate(candidate)
    if not validation["valid"]:
        raise ValueError(validation["errors"])
    duration, height = _scenario_values(graph)
    if not duration < Decimal("2") or not height >= Decimal("0.05"):
        raise ValueError("scenario_does_not_exercise_mixed_compliance")

    context = {
        "document_scope": "gb-45438-2025",
        "scenario_scope": "ai-video-labeling-001",
    }
    source_hash = str(candidate["source_pdf_sha256"])
    candidate_evidence = {item["id"]: item for item in candidate["candidate_evidence"]}
    evidence_nodes = [
        {
            "id": "E-GROW-GB-P7-VIDEO",
            "kind": "evidence",
            "text": candidate_evidence["CE-GB-P7-VIDEO"]["text"],
            "provenance": {
                "source_locator": candidate_evidence["CE-GB-P7-VIDEO"]["source_locator"],
                "source_hash": source_hash,
                "growth_event": event_id,
            },
        },
        {
            "id": "E-GROW-GB-P8-METADATA",
            "kind": "evidence",
            "text": candidate_evidence["CE-GB-P8-METADATA"]["text"],
            "provenance": {
                "source_locator": candidate_evidence["CE-GB-P8-METADATA"]["source_locator"],
                "source_hash": source_hash,
                "growth_event": event_id,
            },
        },
        {
            "id": "E-GROW-GB-P17-APPENDIX-E",
            "kind": "evidence",
            "text": candidate_evidence["CE-GB-P17-APPENDIX-E"]["text"],
            "provenance": {
                "source_locator": candidate_evidence["CE-GB-P17-APPENDIX-E"]["source_locator"],
                "source_hash": source_hash,
                "growth_event": event_id,
            },
        },
    ]

    def asserted(node_id, atom, statement, refs, *, bearer, constraint):
        return {
            "id": node_id,
            "kind": "claim",
            "atom": atom,
            "polarity": "positive",
            "asserted": True,
            "active": True,
            "statement": statement,
            "normative_force": "obligation",
            "bearer": bearer,
            "constraint": constraint,
            "context": deepcopy(context),
            "provenance": {"quoted_from": refs, "growth_event": event_id},
        }

    def derived(node_id, atom, polarity, statement, inference_id, *, status):
        return {
            "id": node_id,
            "kind": "claim",
            "atom": atom,
            "polarity": polarity,
            "asserted": False,
            "active": True,
            "statement": statement,
            "compliance_status": status,
            "context": deepcopy(context),
            "provenance": {"generated_by": inference_id, "growth_event": event_id},
        }

    claims = [
        asserted(
            "C-GB-VIDEO-DURATION-OBLIGATION",
            "gb45438_video_minimum_label_duration",
            "在正常播放速度下，视频内容显式标识持续时间不应少于2秒。",
            ["E-GROW-GB-P7-VIDEO"],
            bearer="video_content_provider",
            constraint={"operator": ">=", "value": "2", "unit": "second"},
        ),
        asserted(
            "C-GB-VIDEO-HEIGHT-OBLIGATION",
            "gb45438_video_minimum_label_height",
            "视频内容显式标识的文字高度不应低于画面最短边长度的5%。",
            ["E-GROW-GB-P7-VIDEO"],
            bearer="video_content_provider",
            constraint={"operator": ">=", "value": "0.05", "unit": "ratio"},
        ),
        asserted(
            "C-GB-METADATA-OBLIGATION",
            "gb45438_metadata_appendix_e_requirement",
            "文件元数据隐式标识应包含规定要素并符合规范性附录E的格式。",
            ["E-GROW-GB-P8-METADATA", "E-GROW-GB-P17-APPENDIX-E"],
            bearer="content_provider",
            constraint={"operator": "conforms_to", "value": "appendix-e"},
        ),
        derived(
            "C-GB-DURATION-VIOLATION",
            "gb45438_video_duration_violation",
            "positive",
            "1秒小于标准要求的2秒，因此视频显式标识持续时间违规。",
            "I-GB-CHECK-DURATION",
            status="violation",
        ),
        derived(
            "C-GB-HEIGHT-COMPLIANT",
            "gb45438_video_height_compliance",
            "positive",
            "文字高度等于画面最短边的5%，满足不低于5%的要求。",
            "I-GB-CHECK-HEIGHT",
            status="satisfied",
        ),
        derived(
            "C-GB-METADATA-COMPLIANT",
            "gb45438_metadata_compliance",
            "positive",
            "场景已按附录E完整填写元数据，因此该部分要求已满足。",
            "I-GB-CHECK-METADATA",
            status="satisfied",
        ),
        derived(
            "C-GB-OVERALL-NONCOMPLIANT",
            "gb45438_video_overall_compliance",
            "negative",
            "该视频不完全符合GB 45438-2025：显式标识只持续1秒，违反第5.4条不应少于2秒的要求。",
            "I-GB-DERIVE-OVERALL-NONCOMPLIANCE",
            status="noncompliant",
        ),
        derived(
            "C-GB-PARTIAL-NOT-OVERALL",
            "gb45438_partial_pass_not_overall_pass",
            "positive",
            "文字高度和元数据合格只能证明局部满足，不能抵消显式标识持续时间的违规。",
            "I-GB-DERIVE-PARTIAL-LIMITATION",
            status="limitation",
        ),
        derived(
            "C-GB-OVERALL-COMPLIANT-HEURISTIC",
            "gb45438_video_overall_compliance",
            "positive",
            "视频已有显式标识且元数据完整，因此可视为完全符合标准。",
            "I-GB-OVERALL-COMPLIANCE-HEURISTIC",
            status="heuristic",
        ),
    ]
    schemes = [
        {"id": "I-GB-CHECK-DURATION", "kind": "inference", "premises": ["C-GB-VIDEO-DURATION-OBLIGATION", "C-SCENARIO-VIDEO-DURATION"], "conclusion": "C-GB-DURATION-VIOLATION", "rule_kind": "strict", "rule_id": "obligation-threshold-violation-v1"},
        {"id": "I-GB-CHECK-HEIGHT", "kind": "inference", "premises": ["C-GB-VIDEO-HEIGHT-OBLIGATION", "C-SCENARIO-VIDEO-HEIGHT"], "conclusion": "C-GB-HEIGHT-COMPLIANT", "rule_kind": "strict", "rule_id": "obligation-threshold-satisfaction-v1"},
        {"id": "I-GB-CHECK-METADATA", "kind": "inference", "premises": ["C-GB-METADATA-OBLIGATION", "C-SCENARIO-METADATA-COMPLETE"], "conclusion": "C-GB-METADATA-COMPLIANT", "rule_kind": "strict", "rule_id": "normative-format-satisfaction-v1"},
        {"id": "I-GB-DERIVE-OVERALL-NONCOMPLIANCE", "kind": "inference", "premises": ["C-GB-STANDARD-APPLIES", "C-GB-DURATION-VIOLATION"], "conclusion": "C-GB-OVERALL-NONCOMPLIANT", "rule_kind": "strict", "rule_id": "mandatory-requirement-violation-v1"},
        {"id": "I-GB-DERIVE-PARTIAL-LIMITATION", "kind": "inference", "premises": ["C-GB-DURATION-VIOLATION", "C-GB-HEIGHT-COMPLIANT", "C-GB-METADATA-COMPLIANT"], "conclusion": "C-GB-PARTIAL-NOT-OVERALL", "rule_kind": "strict", "rule_id": "partial-compliance-does-not-cure-violation-v1"},
        {"id": "I-GB-OVERALL-COMPLIANCE-HEURISTIC", "kind": "inference", "premises": ["C-GB-HEIGHT-COMPLIANT", "C-GB-METADATA-COMPLIANT"], "conclusion": "C-GB-OVERALL-COMPLIANT-HEURISTIC", "rule_kind": "defeasible", "rule_id": "visible-label-plus-metadata-heuristic-v1"},
        {"id": "CA-GB-NONCOMPLIANCE-REBUT", "kind": "conflict", "attack_kind": "rebut", "source": "C-GB-OVERALL-NONCOMPLIANT", "target_type": "claim", "target": "C-GB-OVERALL-COMPLIANT-HEURISTIC"},
        {"id": "CA-GB-DURATION-UNDERCUT", "kind": "conflict", "attack_kind": "undercut", "source": "C-GB-DURATION-VIOLATION", "target_type": "inference", "target": "I-GB-OVERALL-COMPLIANCE-HEURISTIC"}
    ]
    return promote_candidate_transaction(
        graph,
        candidate,
        validation=validation,
        event_id=event_id,
        recorded_at=recorded_at,
        output_format="gdu-logic-normative-slice-v0.2",
        operation="promote_normative_compliance_candidate",
        build_additions=lambda _candidate, _event_id: (evidence_nodes + claims, schemes),
    )
