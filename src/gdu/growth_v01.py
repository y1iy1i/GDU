"""Validated, versioned promotion of query-discovered GDU candidates."""

from __future__ import annotations

import json
from copy import deepcopy
from decimal import Decimal
from hashlib import sha256
from typing import Any, Mapping

from .logic_v01 import validate_aif_interface


REQUIRED_PROMOTION_GATES = {
    "context_matches_consolidated_2025",
    "cross_page_table_reconciles",
    "component_sum_reconciles_to_total_cash_change",
    "causal_wording_preserves_report_scope",
    "limitation_prevents_single-cause_overclaim",
}


def _canonical_hash(value: Mapping[str, Any]) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(payload.encode("utf-8")).hexdigest()


def validate_growth_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the quarantined investment-cash-flow growth candidate."""

    errors: list[str] = []
    if candidate.get("planner_result", {}).get("growth_policy") != "quarantine_before_validation":
        errors.append("candidate_not_quarantined")
    if set(candidate.get("promotion_gate", [])) != REQUIRED_PROMOTION_GATES:
        errors.append("promotion_gate_mismatch")

    evidence = {str(item["id"]): item for item in candidate.get("candidate_evidence", [])}
    if any(item.get("status") != "visually_verified_candidate" for item in evidence.values()):
        errors.append("evidence_not_visually_verified")
    if {item.get("physical_page") for item in evidence.values()} != {15, 72, 73}:
        errors.append("required_pages_missing")
    if any(not item.get("source_locator") for item in evidence.values()):
        errors.append("source_locator_missing")

    claims = candidate.get("candidate_claims", [])
    available_evidence = set(evidence)
    for claim in claims:
        if claim.get("status") != "candidate_pending_logic_validation":
            errors.append(f"candidate_status_invalid:{claim.get('id')}")
        refs = set(claim.get("evidence_refs", []))
        if not refs or not refs <= available_evidence:
            errors.append(f"candidate_evidence_invalid:{claim.get('id')}")

    checks = candidate.get("numeric_checks", {})
    try:
        inflow = Decimal(str(checks["investment_inflow"]))
        outflow = Decimal(str(checks["investment_outflow"]))
        calculated_investment = Decimal(str(checks["calculated_investment_net"]))
        reported_investment = Decimal(str(checks["reported_investment_net"]))
        calculated_cash = Decimal(str(checks["calculated_total_cash_change"]))
        reported_cash = Decimal(str(checks["reported_total_cash_change"]))
        residual = Decimal(str(checks["residual"]))
    except (KeyError, ValueError):
        errors.append("numeric_check_invalid")
    else:
        if inflow - outflow != calculated_investment:
            errors.append("investment_arithmetic_mismatch")
        if calculated_investment != reported_investment:
            errors.append("investment_report_mismatch")
        component_total = sum(
            map(Decimal, ["72545781.16", str(reported_investment), "-23890866.02", "89982.27"])
        )
        if component_total != calculated_cash or calculated_cash != reported_cash:
            errors.append("cash_component_mismatch")
        if reported_cash - calculated_cash != residual or residual != Decimal("0.00"):
            errors.append("residual_not_zero")

        normalized_evidence = " ".join(item.get("text", "") for item in evidence.values()).replace(",", "")
        for name, amount in (
            ("investment_inflow", inflow),
            ("investment_outflow", outflow),
            ("reported_investment_net", reported_investment),
            ("reported_total_cash_change", reported_cash),
        ):
            if f"{amount:.2f}" not in normalized_evidence:
                errors.append(f"amount_not_found_in_evidence:{name}")

    cause_text = str(evidence.get("CE-15-CAUSE", {}).get("text", ""))
    if not all(term in cause_text for term in ("主要系", "对外投资款支出增加")):
        errors.append("causal_scope_not_preserved")
    limitation = next(
        (item for item in claims if item.get("id") == "CC-CASH-DECREASE-COMPOSITION"), {}
    )
    if "不能单独解释全部变化" not in str(limitation.get("statement", "")):
        errors.append("single_cause_limitation_missing")

    return {
        "valid": not errors,
        "errors": sorted(set(errors)),
        "candidate_hash": _canonical_hash(candidate),
    }


def promote_growth_candidate(
    graph: Mapping[str, Any],
    candidate: Mapping[str, Any],
    *,
    event_id: str,
    recorded_at: str,
) -> dict[str, Any]:
    """Promote a valid candidate into a new graph version without mutating inputs."""

    validation = validate_growth_candidate(candidate)
    if not validation["valid"]:
        raise ValueError(validation["errors"])
    if validate_aif_interface(graph):
        raise ValueError("base graph does not pass the logic interface")

    grown = deepcopy(graph)
    context = {
        "company_scope": "consolidated",
        "valid_time": {"type": "interval", "start": "2025-01-01", "end": "2025-12-31"},
    }
    source_hash = str(candidate["source_pdf_sha256"])
    evidence_nodes = [
        {
            "id": "E-GROW-15",
            "kind": "evidence",
            "text": next(item["text"] for item in candidate["candidate_evidence"] if item["id"] == "CE-15-CAUSE"),
            "provenance": {"source_locator": "paper.pdf#physical-page=15", "source_hash": source_hash, "growth_event": event_id},
        },
        {
            "id": "E-GROW-72",
            "kind": "evidence",
            "text": next(item["text"] for item in candidate["candidate_evidence"] if item["id"] == "CE-72-INVEST"),
            "provenance": {"source_locator": "paper.pdf#physical-page=72", "source_hash": source_hash, "growth_event": event_id},
        },
        {
            "id": "E-GROW-73",
            "kind": "evidence",
            "text": " ".join(item["text"] for item in candidate["candidate_evidence"] if item["physical_page"] == 73),
            "provenance": {"source_locator": "paper.pdf#physical-page=73", "source_hash": source_hash, "growth_event": event_id},
        },
    ]

    def asserted(node_id, atom, polarity, statement, amount, refs):
        node = {
            "id": node_id, "kind": "claim", "atom": atom, "polarity": polarity,
            "asserted": True, "active": True, "statement": statement,
            "context": deepcopy(context), "provenance": {"quoted_from": refs, "growth_event": event_id},
        }
        if amount is not None:
            node["value"] = {"amount": amount, "currency": "CNY"}
        return node

    def derived(node_id, atom, polarity, statement, amount, inference_id):
        node = {
            "id": node_id, "kind": "claim", "atom": atom, "polarity": polarity,
            "asserted": False, "active": True, "statement": statement,
            "context": deepcopy(context), "provenance": {"generated_by": inference_id, "growth_event": event_id},
        }
        if amount is not None:
            node["value"] = {"amount": amount, "currency": "CNY"}
        return node

    claim_nodes = [
        asserted("C-INVEST-INFLOW-REPORTED", "investment_cash_inflow_amount", "positive", "2025年投资活动现金流入为69,525,306.42元。", "69525306.42", ["E-GROW-72"]),
        asserted("C-INVEST-OUTFLOW-REPORTED", "investment_cash_outflow_amount", "positive", "2025年投资活动现金流出为306,155,126.21元。", "306155126.21", ["E-GROW-72", "E-GROW-73"]),
        asserted("C-INVEST-NET-REPORTED", "investment_cash_flow_net_amount", "negative", "2025年投资活动现金流量净额为-236,629,819.79元。", "-236629819.79", ["E-GROW-73"]),
        asserted("C-FINANCING-NET-REPORTED", "financing_cash_flow_net_amount", "negative", "2025年筹资活动现金流量净额为-23,890,866.02元。", "-23890866.02", ["E-GROW-73"]),
        asserted("C-FX-EFFECT-REPORTED", "exchange_rate_effect_amount", "positive", "汇率变动对现金及现金等价物的影响为89,982.27元。", "89982.27", ["E-GROW-73"]),
        asserted("C-INVEST-YOY-CAUSE-REPORTED", "investment_cash_flow_yoy_driver", "positive", "报告将投资活动现金流同比变化主要归因为对外投资款支出增加。", None, ["E-GROW-15"]),
        derived("C-INVEST-NET-CALCULATED", "investment_cash_flow_net_amount", "negative", "投资活动流入减流出为-236,629,819.79元。", "-236629819.79", "I-GROW-CALC-INVEST-NET"),
        derived("C-INVEST-NET-MATCH", "investment_cash_flow_reconciliation_matches", "positive", "计算的投资活动净流量与报告金额完全一致。", None, "I-GROW-MATCH-INVEST-NET"),
        derived("C-INVEST-CASH-CONTRIBUTION", "investment_cash_change_driver", "positive", "投资活动净流出236,629,819.79元，是全年现金减少的重要组成部分。", None, "I-GROW-BUILD-INVEST-CONTRIBUTION"),
        derived("C-CASH-CHANGE-CALCULATED", "cash_change_calculated_amount", "negative", "经营、投资、筹资现金流与汇率影响合计为-187,884,922.38元。", "-187884922.38", "I-GROW-CALC-CASH-CHANGE"),
        derived("C-CASH-CLOSURE-MATCH", "cash_change_reconciliation_matches", "positive", "四项现金变动的计算结果与报告的全年现金净变化完全一致。", None, "I-GROW-MATCH-CASH-CHANGE"),
        derived("C-INVEST-NOT-SOLE-CAUSE", "investment_is_sole_cash_decrease_cause", "negative", "投资活动净流出不是全年现金减少的唯一组成部分；经营、筹资现金流和汇率影响也必须计入。", None, "I-GROW-NOT-SOLE-CAUSE"),
        derived("C-INVEST-SOLE-CAUSE-HEURISTIC", "investment_is_sole_cash_decrease_cause", "positive", "投资活动净流出是全年现金减少的唯一原因。", None, "I-GROW-SOLE-CAUSE-HEURISTIC"),
    ]
    schemes = [
        {"id": "I-GROW-CALC-INVEST-NET", "kind": "inference", "premises": ["C-INVEST-INFLOW-REPORTED", "C-INVEST-OUTFLOW-REPORTED"], "conclusion": "C-INVEST-NET-CALCULATED", "rule_kind": "strict", "rule_id": "cash-inflow-minus-outflow-v1"},
        {"id": "I-GROW-MATCH-INVEST-NET", "kind": "inference", "premises": ["C-INVEST-NET-CALCULATED", "C-INVEST-NET-REPORTED"], "conclusion": "C-INVEST-NET-MATCH", "rule_kind": "strict", "rule_id": "exact-decimal-equality-v1"},
        {"id": "I-GROW-BUILD-INVEST-CONTRIBUTION", "kind": "inference", "premises": ["C-INVEST-NET-REPORTED", "C-INVEST-NET-MATCH", "C-INVEST-YOY-CAUSE-REPORTED"], "conclusion": "C-INVEST-CASH-CONTRIBUTION", "rule_kind": "strict", "rule_id": "audited-cash-component-v1"},
        {"id": "I-GROW-CALC-CASH-CHANGE", "kind": "inference", "premises": ["C-OCF-REPORTED", "C-INVEST-NET-REPORTED", "C-FINANCING-NET-REPORTED", "C-FX-EFFECT-REPORTED"], "conclusion": "C-CASH-CHANGE-CALCULATED", "rule_kind": "strict", "rule_id": "cash-flow-component-sum-v1"},
        {"id": "I-GROW-MATCH-CASH-CHANGE", "kind": "inference", "premises": ["C-CASH-CHANGE-CALCULATED", "C-CASH-INCREASE-OBSERVED"], "conclusion": "C-CASH-CLOSURE-MATCH", "rule_kind": "strict", "rule_id": "exact-decimal-equality-v1"},
        {"id": "I-GROW-NOT-SOLE-CAUSE", "kind": "inference", "premises": ["C-OCF-REPORTED", "C-FINANCING-NET-REPORTED", "C-FX-EFFECT-REPORTED", "C-CASH-CLOSURE-MATCH"], "conclusion": "C-INVEST-NOT-SOLE-CAUSE", "rule_kind": "strict", "rule_id": "nonzero-multiple-cash-components-v1"},
        {"id": "I-GROW-SOLE-CAUSE-HEURISTIC", "kind": "inference", "premises": ["C-INVEST-NET-REPORTED"], "conclusion": "C-INVEST-SOLE-CAUSE-HEURISTIC", "rule_kind": "defeasible", "rule_id": "largest-outflow-is-sole-cause-heuristic-v1"},
        {"id": "CA-GROW-NOT-SOLE-REBUT", "kind": "conflict", "attack_kind": "rebut", "source": "C-INVEST-NOT-SOLE-CAUSE", "target_type": "claim", "target": "C-INVEST-SOLE-CAUSE-HEURISTIC"},
        {"id": "CA-GROW-NOT-SOLE-UNDERCUT", "kind": "conflict", "attack_kind": "undercut", "source": "C-INVEST-NOT-SOLE-CAUSE", "target_type": "inference", "target": "I-GROW-SOLE-CAUSE-HEURISTIC"},
    ]
    grown["information_nodes"].extend(evidence_nodes + claim_nodes)
    grown["scheme_nodes"].extend(schemes)
    grown["format"] = "gdu-logic-real-slice-v0.2"
    grown.setdefault("revision_history", []).append(
        {
            "event_id": event_id,
            "recorded_at": recorded_at,
            "operation": "promote_query_gap_candidate",
            "parent_format": graph.get("format"),
            "candidate_hash": validation["candidate_hash"],
            "added_information_node_ids": [node["id"] for node in evidence_nodes + claim_nodes],
            "added_scheme_node_ids": [node["id"] for node in schemes],
        }
    )
    promoted_issues = validate_aif_interface(grown)
    if promoted_issues:
        raise ValueError([issue.to_dict() for issue in promoted_issues])
    return grown
