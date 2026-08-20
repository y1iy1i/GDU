import json
from copy import deepcopy
from pathlib import Path

import pytest

from gdu.answer_v01 import build_answer_package
from gdu.growth_v01 import promote_growth_candidate, validate_growth_candidate
from gdu.logic_v01 import (
    compile_structured_arguments,
    grounded_labels,
    incremental_recompute_after_invalidation,
    recompute_after_invalidation,
    validate_aif_interface,
)
from gdu.query_planner_v01 import plan_query


ROOT = Path(__file__).parents[1]
BASE = ROOT / "research_inputs/replication_01_lafang_2025/GDU_LOGIC_REAL_SLICE_V0_1.json"
CANDIDATE = ROOT / "research_inputs/replication_01_lafang_2025/GDU_QUERY_GAP_CANDIDATE_V0_1.json"
PROMOTED = ROOT / "research_inputs/replication_01_lafang_2025/GDU_LOGIC_REAL_SLICE_V0_2.json"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def promote():
    return promote_growth_candidate(
        load(BASE), load(CANDIDATE), event_id="GROWTH-2025-INVEST-001",
        recorded_at="2026-08-20T18:00:00+08:00",
    )


def test_valid_candidate_promotes_without_mutating_base():
    base = load(BASE)
    before = deepcopy(base)
    candidate = load(CANDIDATE)
    assert validate_growth_candidate(candidate)["valid"] is True
    grown = promote_growth_candidate(
        base, candidate, event_id="GROWTH-2025-INVEST-001",
        recorded_at="2026-08-20T18:00:00+08:00",
    )
    assert base == before
    assert grown["format"] == "gdu-logic-real-slice-v0.2"
    assert validate_aif_interface(grown) == []
    assert grown["revision_history"][-1]["parent_format"] == "gdu-logic-real-slice-v0.1"


def test_materialized_v02_matches_reproducible_promotion():
    assert load(PROMOTED) == promote()


def test_same_query_moves_from_gap_to_answer_ready_after_growth():
    question = "哪项投资活动导致全年现金减少？"
    assert plan_query(load(BASE), question)["status"] == "gap"
    grown = promote()
    plan = plan_query(grown, question)
    assert plan["status"] == "ready"
    assert plan["target_claim_ids"] == ["C-INVEST-CASH-CONTRIBUTION"]
    assert plan["limitation_claim_ids"] == ["C-INVEST-NOT-SOLE-CAUSE"]
    package = build_answer_package(
        grown,
        target_claim_ids=plan["target_claim_ids"],
        limitation_claim_ids=plan["limitation_claim_ids"],
    )
    assert "重要组成部分" in package["answer"]
    assert "不是全年现金减少的唯一组成部分" in package["answer"]
    assert "C-INVEST-SOLE-CAUSE-HEURISTIC" in package["rejected_claim_ids"]
    assert {item["source_locator"] for item in package["evidence"]} >= {
        "paper.pdf#physical-page=15", "paper.pdf#physical-page=72", "paper.pdf#physical-page=73"
    }


def test_promoted_graph_accepts_growth_and_rejects_single_cause_heuristic():
    grown = promote()
    arguments, attacks = compile_structured_arguments(grown)
    labels = grounded_labels(arguments, attacks)
    contribution = next(arg for arg in arguments.values() if arg.conclusion == "C-INVEST-CASH-CONTRIBUTION")
    heuristic = next(arg for arg in arguments.values() if arg.conclusion == "C-INVEST-SOLE-CAUSE-HEURISTIC")
    assert labels[contribution.id] == "accepted"
    assert labels[heuristic.id] == "rejected"


def test_tampered_candidate_is_not_promoted():
    candidate = load(CANDIDATE)
    candidate["numeric_checks"]["investment_outflow"] = "300000000.00"
    validation = validate_growth_candidate(candidate)
    assert validation["valid"] is False
    assert "investment_arithmetic_mismatch" in validation["errors"]
    with pytest.raises(ValueError):
        promote_growth_candidate(
            load(BASE), candidate, event_id="BAD", recorded_at="2026-08-20T18:00:00+08:00"
        )


def test_invalidated_investment_detail_breaks_explanation_not_reported_cash():
    grown = promote()
    full = recompute_after_invalidation(
        grown, ["C-INVEST-OUTFLOW-REPORTED"], event_id="REV-GROW-1"
    )
    incremental = incremental_recompute_after_invalidation(
        grown, ["C-INVEST-OUTFLOW-REPORTED"], event_id="REV-GROW-1"
    )
    assert incremental["active_claim_ids"] == full["active_claim_ids"]
    assert incremental["active_inference_ids"] == full["active_inference_ids"]
    assert "C-CASH-INCREASE-OBSERVED" in full["active_claim_ids"]
    assert "C-INVEST-NET-CALCULATED" not in full["active_claim_ids"]
    assert "C-INVEST-NET-MATCH" not in full["active_claim_ids"]
    assert "C-INVEST-CASH-CONTRIBUTION" not in full["active_claim_ids"]
