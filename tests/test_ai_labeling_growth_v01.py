import json
from copy import deepcopy
from pathlib import Path

import pytest

from gdu.answer_v01 import build_answer_package
from gdu.growth_ai_labeling_v01 import (
    promote_ai_labeling_candidate,
    validate_ai_labeling_candidate,
)
from gdu.logic_v01 import (
    compile_structured_arguments,
    grounded_labels,
    incremental_recompute_after_invalidation,
    recompute_after_invalidation,
    validate_aif_interface,
)
from gdu.query_planner_v01 import parse_question, plan_query, search_source_pages


ROOT = Path(__file__).parents[1]
CASE = ROOT / "research_inputs/pilot_03_ai_labeling"
BASE = CASE / "GDU_LOGIC_NORMATIVE_SLICE_V0_1.json"
CANDIDATE = CASE / "GDU_QUERY_GAP_CANDIDATE_V0_1.json"
PROMOTED = CASE / "GDU_LOGIC_NORMATIVE_SLICE_V0_2.json"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def promote():
    return promote_ai_labeling_candidate(
        load(BASE),
        load(CANDIDATE),
        event_id="GROWTH-GB45438-VIDEO-001",
        recorded_at="2026-08-20T22:00:00+08:00",
    )


def test_standard_version_suffix_is_not_parsed_as_query_year():
    parsed = parse_question(load(BASE)["question"])
    assert parsed["year"] is None
    assert parsed["concepts"] == ["ai_generated_label", "standards_compliance"]


def test_valid_base_exposes_normative_compliance_gap_and_source_terms():
    graph = load(BASE)
    assert validate_aif_interface(graph) == []
    plan = plan_query(graph, graph["question"])
    assert plan["status"] == "gap"
    assert plan["query_structure"] == "normative_compliance_check"
    assert plan["missing_atoms"] == [
        "gb45438_partial_pass_not_overall_pass",
        "gb45438_video_overall_compliance",
    ]
    pages = {
        7: "视频内容显式标识持续时间不应少于2s",
        8: "文件元数据隐式标识格式应符合附录E",
        17: "附录E AIGC Label ContentProducer",
    }
    assert [item["physical_page"] for item in search_source_pages(
        pages, plan["source_lookup"]["terms"]
    )] == [7, 8, 17]


def test_candidate_promotes_without_mutating_inputs_and_replay_is_exact():
    base = load(BASE)
    candidate = load(CANDIDATE)
    base_before = deepcopy(base)
    candidate_before = deepcopy(candidate)
    assert validate_ai_labeling_candidate(candidate)["valid"] is True
    grown = promote_ai_labeling_candidate(
        base,
        candidate,
        event_id="GROWTH-GB45438-VIDEO-001",
        recorded_at="2026-08-20T22:00:00+08:00",
    )
    assert base == base_before
    assert candidate == candidate_before
    assert validate_aif_interface(grown) == []
    assert grown == load(PROMOTED)


def test_growth_produces_auditable_noncompliance_answer():
    grown = promote()
    plan = plan_query(grown, grown["question"])
    assert plan["status"] == "ready"
    assert plan["target_claim_ids"] == ["C-GB-OVERALL-NONCOMPLIANT"]
    assert plan["limitation_claim_ids"] == ["C-GB-PARTIAL-NOT-OVERALL"]
    package = build_answer_package(
        grown,
        target_claim_ids=plan["target_claim_ids"],
        limitation_claim_ids=plan["limitation_claim_ids"],
    )
    assert "不完全符合" in package["answer"]
    assert "不能抵消" in package["answer"]
    assert "C-GB-OVERALL-COMPLIANT-HEURISTIC" in package["rejected_claim_ids"]
    assert {item["source_locator"] for item in package["evidence"]} >= {
        "paper.pdf#physical-page=7&section=5.4",
        "paper.pdf#physical-page=8&section=6.1",
        "paper.pdf#physical-page=17&appendix=E",
        "SCENARIO_V0_1.json#scenario_id=ai-video-labeling-001",
    }


def test_violation_and_obligation_coexist_instead_of_rebutting_each_other():
    grown = promote()
    arguments, attacks = compile_structured_arguments(grown)
    labels = grounded_labels(arguments, attacks)
    obligation = next(
        arg for arg in arguments.values()
        if arg.conclusion == "C-GB-VIDEO-DURATION-OBLIGATION"
    )
    violation = next(
        arg for arg in arguments.values() if arg.conclusion == "C-GB-DURATION-VIOLATION"
    )
    heuristic = next(
        arg for arg in arguments.values()
        if arg.conclusion == "C-GB-OVERALL-COMPLIANT-HEURISTIC"
    )
    assert labels[obligation.id] == "accepted"
    assert labels[violation.id] == "accepted"
    assert labels[heuristic.id] == "rejected"
    assert (violation.id, obligation.id) not in attacks


def test_changed_numeric_threshold_is_rejected_before_promotion():
    candidate = load(CANDIDATE)
    claim = next(
        item for item in candidate["candidate_claims"]
        if item["id"] == "CC-GB-VIDEO-DURATION-OBLIGATION"
    )
    claim["statement"] = claim["statement"].replace("2秒", "1秒")
    validation = validate_ai_labeling_candidate(candidate)
    assert validation["valid"] is False
    assert "duration_obligation_changed" in validation["errors"]
    with pytest.raises(ValueError):
        promote_ai_labeling_candidate(
            load(BASE), candidate, event_id="BAD", recorded_at="2026-08-20T22:00:00+08:00"
        )


def test_duration_rule_invalidation_reopens_gap_incrementally():
    grown = promote()
    invalid = ["C-GB-VIDEO-DURATION-OBLIGATION"]
    full = recompute_after_invalidation(grown, invalid, event_id="REV-GB45438-1")
    incremental = incremental_recompute_after_invalidation(
        grown, invalid, event_id="REV-GB45438-1"
    )
    assert incremental["active_claim_ids"] == full["active_claim_ids"]
    assert incremental["active_inference_ids"] == full["active_inference_ids"]
    assert "C-GB-DURATION-VIOLATION" not in full["active_claim_ids"]
    assert "C-GB-OVERALL-NONCOMPLIANT" not in full["active_claim_ids"]
    assert plan_query(full["graph"], grown["question"])["status"] == "gap"


def test_changed_scenario_facts_are_not_silently_reused():
    base = load(BASE)
    claim = next(
        item for item in base["information_nodes"]
        if item["id"] == "C-SCENARIO-VIDEO-DURATION"
    )
    claim["value"]["amount"] = "3"
    with pytest.raises(ValueError, match="scenario_values_changed"):
        promote_ai_labeling_candidate(
            base,
            load(CANDIDATE),
            event_id="BAD-SCENARIO",
            recorded_at="2026-08-20T22:00:00+08:00",
        )
