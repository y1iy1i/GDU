"""Promotion gate for the non-numeric PGKD source-conflict growth case."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from hashlib import sha256
from typing import Any, Mapping

from .logic_v01 import validate_aif_interface


REQUIRED_GATES = {
    "context_matches_pgkd_methods",
    "cross_carrier_conflict_preserved",
    "literal_algorithm_indices_preserved",
    "ambiguity_not_silently_resolved",
    "alternative_interpretations_retained",
}


def _hash(value: Mapping[str, Any]) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(payload.encode("utf-8")).hexdigest()


def _compact(text: str) -> str:
    return re.sub(r"[^0-9a-z]+", "", text.lower())


def validate_pgkd_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if candidate.get("document_id") != "pgkd-emnlp-2024":
        errors.append("wrong_document")
    if candidate.get("planner_result", {}).get("growth_policy") != "quarantine_before_validation":
        errors.append("candidate_not_quarantined")
    if set(candidate.get("promotion_gate", [])) != REQUIRED_GATES:
        errors.append("promotion_gate_mismatch")

    evidence = {str(item["id"]): item for item in candidate.get("candidate_evidence", [])}
    if {item.get("carrier") for item in evidence.values()} != {"prose", "figure", "algorithm"}:
        errors.append("cross_carrier_evidence_missing")
    if {item.get("physical_page") for item in evidence.values()} != {3, 4}:
        errors.append("required_pages_missing")
    if any(item.get("status") != "visually_verified_candidate" for item in evidence.values()):
        errors.append("evidence_not_visually_verified")
    if any(not item.get("source_locator") for item in evidence.values()):
        errors.append("source_locator_missing")

    algorithm = _compact(str(evidence.get("CE-PGKD-P4-ALGORITHM", {}).get("text", "")))
    for pattern, code in (
        ("modeli1trainmodelonhistory", "next_model_training_index_missing"),
        ("evaluatemodelidval", "old_model_evaluation_index_missing"),
        ("modelbestmodeli", "old_model_best_index_missing"),
    ):
        if pattern not in algorithm:
            errors.append(code)

    claims = {str(item["id"]): item for item in candidate.get("candidate_claims", [])}
    required_claims = {
        "CC-PGKD-FLOW-UPDATED",
        "CC-PGKD-ALGORITHM-OLD",
        "CC-PGKD-IDENTITY-UNRESOLVED",
        "CC-PGKD-NOT-RESOLVED",
    }
    if set(claims) != required_claims:
        errors.append("candidate_claim_set_mismatch")
    for claim in claims.values():
        if claim.get("status") != "candidate_pending_logic_validation":
            errors.append(f"candidate_status_invalid:{claim.get('id')}")
        refs = set(claim.get("evidence_refs", []))
        if not refs or not refs <= set(evidence):
            errors.append(f"candidate_evidence_invalid:{claim.get('id')}")

    ambiguity = str(claims.get("CC-PGKD-IDENTITY-UNRESOLVED", {}).get("statement", ""))
    limitation = str(claims.get("CC-PGKD-NOT-RESOLVED", {}).get("statement", ""))
    if not all(term in ambiguity for term in ("未消解歧义", "更新后模型", "旧模型")):
        errors.append("ambiguity_not_preserved")
    if not all(term in limitation for term in ("无法确定", "不能静默改写")):
        errors.append("silent_correction_not_blocked")
    if any(term in ambiguity + limitation for term in ("必然是排版错误", "确定是排版错误")):
        errors.append("unsupported_typo_resolution")

    return {"valid": not errors, "errors": sorted(set(errors)), "candidate_hash": _hash(candidate)}


def promote_pgkd_candidate(
    graph: Mapping[str, Any],
    candidate: Mapping[str, Any],
    *,
    event_id: str,
    recorded_at: str,
) -> dict[str, Any]:
    validation = validate_pgkd_candidate(candidate)
    if not validation["valid"]:
        raise ValueError(validation["errors"])
    if validate_aif_interface(graph):
        raise ValueError("base graph does not pass the logic interface")

    grown = deepcopy(graph)
    context = {"document_scope": "pgkd-emnlp-2024", "section_scope": "methods"}
    source_hash = str(candidate["source_pdf_sha256"])
    candidate_evidence = {item["id"]: item for item in candidate["candidate_evidence"]}
    evidence_nodes = [
        {
            "id": "E-GROW-PGKD-P3-METHOD", "kind": "evidence",
            "text": candidate_evidence["CE-PGKD-P3-METHOD"]["text"],
            "provenance": {"source_locator": candidate_evidence["CE-PGKD-P3-METHOD"]["source_locator"], "source_hash": source_hash, "growth_event": event_id},
        },
        {
            "id": "E-GROW-PGKD-P4-FIGURE", "kind": "evidence",
            "text": candidate_evidence["CE-PGKD-P4-FIGURE"]["text"],
            "provenance": {"source_locator": candidate_evidence["CE-PGKD-P4-FIGURE"]["source_locator"], "source_hash": source_hash, "growth_event": event_id},
        },
        {
            "id": "E-GROW-PGKD-P4-ALGORITHM", "kind": "evidence",
            "text": candidate_evidence["CE-PGKD-P4-ALGORITHM"]["text"],
            "provenance": {"source_locator": candidate_evidence["CE-PGKD-P4-ALGORITHM"]["source_locator"], "source_hash": source_hash, "growth_event": event_id},
        },
    ]

    def asserted(node_id, atom, polarity, statement, refs):
        return {
            "id": node_id, "kind": "claim", "atom": atom, "polarity": polarity,
            "asserted": True, "active": True, "statement": statement,
            "context": deepcopy(context),
            "provenance": {"quoted_from": refs, "growth_event": event_id},
        }

    def derived(node_id, atom, polarity, statement, inference_id):
        return {
            "id": node_id, "kind": "claim", "atom": atom, "polarity": polarity,
            "asserted": False, "active": True, "statement": statement,
            "context": deepcopy(context),
            "provenance": {"generated_by": inference_id, "growth_event": event_id},
        }

    claims = [
        asserted("C-PGKD-FLOW-SUGGESTS-UPDATED", "pgkd_flow_suggests_updated_model_evaluation", "positive", "方法叙述和循环流程更自然地支持训练下一轮学生后评估更新后的学生模型。", ["E-GROW-PGKD-P3-METHOD", "E-GROW-PGKD-P4-FIGURE"]),
        asserted("C-PGKD-ALGORITHM-LITERAL-OLD", "pgkd_algorithm_literally_evaluates_old_model", "positive", "Algorithm 1字面上先训练model^{i+1}，随后评估model^i，并把model^i记为最佳模型。", ["E-GROW-PGKD-P4-ALGORITHM"]),
        derived("C-PGKD-EVAL-UPDATED-INTERPRETATION", "pgkd_evaluates_updated_model", "positive", "按方法流程解释，每轮应评估更新后的学生模型。", "I-PGKD-INTERPRET-FLOW"),
        derived("C-PGKD-EVAL-OLD-LITERAL", "pgkd_evaluates_updated_model", "negative", "按Algorithm 1字面索引，每轮评估的是更新前的model^i。", "I-PGKD-READ-ALGORITHM-LITERALLY"),
        derived("C-PGKD-IDENTITY-UNRESOLVED", "pgkd_evaluated_model_identity", "positive", "来源对每轮被评估模型的身份存在未消解歧义：正文与流程图倾向更新后模型，Algorithm 1字面索引则是旧模型。", "I-PGKD-DETECT-SOURCE-CONFLICT"),
        derived("C-PGKD-NOT-RESOLVED", "pgkd_identity_source_resolved", "negative", "仅凭论文来源无法确定Algorithm 1是排版错误还是作者有意评估旧模型，不能静默改写索引。", "I-PGKD-PRESERVE-UNRESOLVED"),
        derived("C-PGKD-SILENT-CORRECTION", "pgkd_identity_source_resolved", "positive", "流程意图足以证明Algorithm 1只是排版错误，可以直接改成评估model^{i+1}。", "I-PGKD-SILENT-CORRECTION-HEURISTIC"),
    ]
    schemes = [
        {"id": "I-PGKD-INTERPRET-FLOW", "kind": "inference", "premises": ["C-PGKD-FLOW-SUGGESTS-UPDATED"], "conclusion": "C-PGKD-EVAL-UPDATED-INTERPRETATION", "rule_kind": "defeasible", "rule_id": "workflow-intent-interpretation-v1"},
        {"id": "I-PGKD-READ-ALGORITHM-LITERALLY", "kind": "inference", "premises": ["C-PGKD-ALGORITHM-LITERAL-OLD"], "conclusion": "C-PGKD-EVAL-OLD-LITERAL", "rule_kind": "strict", "rule_id": "literal-index-reading-v1"},
        {"id": "I-PGKD-DETECT-SOURCE-CONFLICT", "kind": "inference", "premises": ["C-PGKD-FLOW-SUGGESTS-UPDATED", "C-PGKD-ALGORITHM-LITERAL-OLD"], "conclusion": "C-PGKD-IDENTITY-UNRESOLVED", "rule_kind": "strict", "rule_id": "cross-carrier-conflict-detection-v1"},
        {"id": "I-PGKD-PRESERVE-UNRESOLVED", "kind": "inference", "premises": ["C-PGKD-IDENTITY-UNRESOLVED"], "conclusion": "C-PGKD-NOT-RESOLVED", "rule_kind": "strict", "rule_id": "source-underdetermination-v1"},
        {"id": "I-PGKD-SILENT-CORRECTION-HEURISTIC", "kind": "inference", "premises": ["C-PGKD-FLOW-SUGGESTS-UPDATED"], "conclusion": "C-PGKD-SILENT-CORRECTION", "rule_kind": "defeasible", "rule_id": "intent-overrides-literal-source-heuristic-v1"},
        {"id": "CA-PGKD-UPDATED-REBUTS-OLD", "kind": "conflict", "attack_kind": "rebut", "source": "C-PGKD-EVAL-UPDATED-INTERPRETATION", "target_type": "claim", "target": "C-PGKD-EVAL-OLD-LITERAL"},
        {"id": "CA-PGKD-OLD-REBUTS-UPDATED", "kind": "conflict", "attack_kind": "rebut", "source": "C-PGKD-EVAL-OLD-LITERAL", "target_type": "claim", "target": "C-PGKD-EVAL-UPDATED-INTERPRETATION"},
        {"id": "CA-PGKD-NOT-RESOLVED-REBUT", "kind": "conflict", "attack_kind": "rebut", "source": "C-PGKD-NOT-RESOLVED", "target_type": "claim", "target": "C-PGKD-SILENT-CORRECTION"},
        {"id": "CA-PGKD-NOT-RESOLVED-UNDERCUT", "kind": "conflict", "attack_kind": "undercut", "source": "C-PGKD-NOT-RESOLVED", "target_type": "inference", "target": "I-PGKD-SILENT-CORRECTION-HEURISTIC"}
    ]
    grown["information_nodes"].extend(evidence_nodes + claims)
    grown["scheme_nodes"].extend(schemes)
    grown["format"] = "gdu-logic-method-slice-v0.2"
    grown.setdefault("revision_history", []).append(
        {
            "event_id": event_id,
            "recorded_at": recorded_at,
            "operation": "promote_pgkd_source_conflict_candidate",
            "parent_format": graph.get("format"),
            "candidate_hash": validation["candidate_hash"],
            "added_information_node_ids": [node["id"] for node in evidence_nodes + claims],
            "added_scheme_node_ids": [node["id"] for node in schemes],
        }
    )
    issues = validate_aif_interface(grown)
    if issues:
        raise ValueError([issue.to_dict() for issue in issues])
    return grown
