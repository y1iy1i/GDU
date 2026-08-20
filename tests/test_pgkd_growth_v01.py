import json
from copy import deepcopy
from pathlib import Path

import pytest

from gdu.answer_v01 import build_answer_package
from gdu.growth_pgkd_v01 import promote_pgkd_candidate, validate_pgkd_candidate
from gdu.logic_v01 import (
    belnap_status,
    compile_structured_arguments,
    grounded_labels,
    incremental_recompute_after_invalidation,
    recompute_after_invalidation,
    validate_aif_interface,
)
from gdu.query_planner_v01 import plan_query


ROOT = Path(__file__).parents[1]
BASE = ROOT / "research_inputs/pilot_02_pgkd/GDU_LOGIC_METHOD_SLICE_V0_1.json"
CANDIDATE = ROOT / "research_inputs/pilot_02_pgkd/GDU_QUERY_GAP_CANDIDATE_V0_1.json"
PROMOTED = ROOT / "research_inputs/pilot_02_pgkd/GDU_LOGIC_METHOD_SLICE_V0_2.json"
QUESTION = "PGKD每轮训练新学生后，评估的是新模型还是旧模型？"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def promote():
    return promote_pgkd_candidate(
        load(BASE), load(CANDIDATE), event_id="GROWTH-PGKD-METHOD-001",
        recorded_at="2026-08-20T20:00:00+08:00",
    )


def test_valid_candidate_promotes_without_mutating_base():
    base = load(BASE)
    before = deepcopy(base)
    validation = validate_pgkd_candidate(load(CANDIDATE))
    assert validation["valid"] is True
    grown = promote_pgkd_candidate(
        base, load(CANDIDATE), event_id="GROWTH-PGKD-METHOD-001",
        recorded_at="2026-08-20T20:00:00+08:00",
    )
    assert base == before
    assert grown["format"] == "gdu-logic-method-slice-v0.2"
    assert validate_aif_interface(grown) == []


def test_same_question_moves_from_gap_to_auditable_ambiguity_answer():
    assert plan_query(load(BASE), QUESTION)["status"] == "gap"
    grown = promote()
    plan = plan_query(grown, QUESTION)
    assert plan["status"] == "ready"
    assert plan["target_claim_ids"] == ["C-PGKD-IDENTITY-UNRESOLVED"]
    assert plan["limitation_claim_ids"] == ["C-PGKD-NOT-RESOLVED"]
    package = build_answer_package(
        grown,
        target_claim_ids=plan["target_claim_ids"],
        limitation_claim_ids=plan["limitation_claim_ids"],
    )
    assert "未消解歧义" in package["answer"]
    assert "不能静默改写索引" in package["answer"]
    assert "C-PGKD-SILENT-CORRECTION" in package["rejected_claim_ids"]
    assert {item["source_locator"] for item in package["evidence"]} == {
        "paper.pdf#physical-page=3&section=3-methods",
        "paper.pdf#physical-page=4&figure=1-2",
        "paper.pdf#physical-page=4&algorithm=1&lines=8-17",
    }


def test_conflicting_interpretations_remain_both_and_undecided():
    grown = promote()
    arguments, attacks = compile_structured_arguments(grown)
    labels = grounded_labels(arguments, attacks)
    updated = next(arg for arg in arguments.values() if arg.conclusion == "C-PGKD-EVAL-UPDATED-INTERPRETATION")
    old = next(arg for arg in arguments.values() if arg.conclusion == "C-PGKD-EVAL-OLD-LITERAL")
    correction = next(arg for arg in arguments.values() if arg.conclusion == "C-PGKD-SILENT-CORRECTION")
    assert belnap_status(grown, "pgkd_evaluates_updated_model") == "BOTH"
    assert labels[updated.id] == "undecided"
    assert labels[old.id] == "undecided"
    assert labels[correction.id] == "rejected"


def test_tampered_algorithm_index_is_rejected_before_promotion():
    candidate = load(CANDIDATE)
    algorithm = next(item for item in candidate["candidate_evidence"] if item["carrier"] == "algorithm")
    algorithm["text"] = algorithm["text"].replace("evaluate(model^i, D^val)", "evaluate(model^{i+1}, D^val)")
    validation = validate_pgkd_candidate(candidate)
    assert validation["valid"] is False
    assert "old_model_evaluation_index_missing" in validation["errors"]
    with pytest.raises(ValueError):
        promote_pgkd_candidate(
            load(BASE), candidate, event_id="BAD", recorded_at="2026-08-20T20:00:00+08:00"
        )


def test_algorithm_evidence_invalidation_reopens_query_gap():
    grown = promote()
    invalid = ["C-PGKD-ALGORITHM-LITERAL-OLD"]
    full = recompute_after_invalidation(grown, invalid, event_id="REV-PGKD-1")
    incremental = incremental_recompute_after_invalidation(grown, invalid, event_id="REV-PGKD-1")
    assert incremental["active_claim_ids"] == full["active_claim_ids"]
    assert incremental["active_inference_ids"] == full["active_inference_ids"]
    assert "C-PGKD-IDENTITY-UNRESOLVED" not in full["active_claim_ids"]
    assert "C-PGKD-NOT-RESOLVED" not in full["active_claim_ids"]
    assert plan_query(full["graph"], QUESTION)["status"] == "gap"


def test_materialized_v02_matches_reproducible_promotion():
    assert load(PROMOTED) == promote()
