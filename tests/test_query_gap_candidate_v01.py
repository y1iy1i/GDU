import json
from decimal import Decimal
from pathlib import Path


CANDIDATE = (
    Path(__file__).parents[1]
    / "research_inputs"
    / "replication_01_lafang_2025"
    / "GDU_QUERY_GAP_CANDIDATE_V0_1.json"
)


def load_candidate():
    return json.loads(CANDIDATE.read_text(encoding="utf-8"))


def test_gap_growth_remains_quarantined_before_logic_validation():
    candidate = load_candidate()
    assert candidate["planner_result"]["growth_policy"] == "quarantine_before_validation"
    assert {claim["status"] for claim in candidate["candidate_claims"]} == {
        "candidate_pending_logic_validation"
    }


def test_investment_cross_page_values_and_total_cash_change_close_exactly():
    candidate = load_candidate()
    checks = candidate["numeric_checks"]
    investment_net = Decimal(checks["investment_inflow"]) - Decimal(checks["investment_outflow"])
    total_change = sum(
        map(
            Decimal,
            ["72545781.16", "-236629819.79", "-23890866.02", "89982.27"],
        )
    )
    assert investment_net == Decimal(checks["reported_investment_net"])
    assert total_change == Decimal(checks["reported_total_cash_change"])
    assert Decimal(checks["residual"]) == Decimal("0.00")


def test_candidate_preserves_multi_component_limitation():
    candidate = load_candidate()
    composition = next(
        claim
        for claim in candidate["candidate_claims"]
        if claim["id"] == "CC-CASH-DECREASE-COMPOSITION"
    )
    assert "不能单独解释全部变化" in composition["statement"]
    assert "limitation_prevents_single-cause_overclaim" in candidate["promotion_gate"]
