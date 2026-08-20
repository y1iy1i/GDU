import json
from pathlib import Path

from gdu.answer_v01 import build_answer_package
from gdu.query_planner_v01 import plan_query, search_source_pages


ARTIFACT = (
    Path(__file__).parents[1]
    / "research_inputs"
    / "replication_01_lafang_2025"
    / "GDU_LOGIC_REAL_SLICE_V0_1.json"
)


def load_graph():
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def test_paraphrases_map_to_same_explanation_claim():
    questions = [
        "为什么2025年净利润亏损但经营现金流为正？",
        "利润是负的，经营活动现金流却为正，怎么解释？",
        "为何亏损而经营现金流仍然为正？",
    ]
    plans = [plan_query(load_graph(), question) for question in questions]
    assert {plan["status"] for plan in plans} == {"ready"}
    assert {tuple(plan["target_claim_ids"]) for plan in plans} == {
        ("C-PROFIT-OCF-BRIDGE",)
    }
    assert all(plan["expansion"]["nodes"] == [] for plan in plans)


def test_misleading_premise_maps_to_counterevidence_not_rejected_claim():
    graph = load_graph()
    plan = plan_query(graph, "经营现金流为正，是不是说明全年现金增加？")
    assert plan["status"] == "ready"
    assert plan["target_claim_ids"] == ["C-CASH-INCREASE-OBSERVED"]
    assert plan["limitation_claim_ids"] == ["C-CATEGORY-DISTINCT"]
    package = build_answer_package(
        graph,
        target_claim_ids=plan["target_claim_ids"],
        limitation_claim_ids=plan["limitation_claim_ids"],
    )
    assert "净减少187,884,922.38元" in package["answer"]
    assert "C-CASH-INCREASE-HEURISTIC" in package["rejected_claim_ids"]


def test_missing_investment_driver_triggers_bounded_source_fallback():
    plan = plan_query(load_graph(), "哪项投资活动导致全年现金减少？")
    assert plan["status"] == "gap"
    assert plan["missing_atoms"] == [
        "investment_cash_change_driver",
        "investment_is_sole_cash_decrease_cause",
    ]
    assert plan["source_lookup"]["required"] is True
    assert plan["source_lookup"]["mode"] == "bounded_fallback_only"
    assert plan["expansion"]["max_hops"] == 2
    assert plan["expansion"]["nodes"]

    pages = {
        72: "投资活动现金流入小计69,525,306.42；投资支付的现金158,196,484.74。",
        73: "投资活动产生的现金流量净额-236,629,819.79。",
        156: "将净利润调节为经营活动现金流量。",
    }
    found = search_source_pages(pages, plan["source_lookup"]["terms"])
    assert [item["physical_page"] for item in found] == [72, 73]
    assert all(item["status"] == "candidate_evidence" for item in found)


def test_unknown_question_reports_gap_instead_of_guessing():
    plan = plan_query(load_graph(), "公司的品牌战略是否成功？")
    assert plan["status"] == "gap"
    assert plan["target_claim_ids"] == []
    assert plan["source_lookup"]["required"] is True
    assert plan["gap_reasons"] == ["unresolved_query_structure"]


def test_explicit_parent_company_scope_does_not_reuse_consolidated_claim():
    plan = plan_query(load_graph(), "母公司为什么净利润亏损但经营现金流为正？")
    assert plan["status"] == "gap"
    assert plan["target_claim_ids"] == []
    assert plan["missing_atoms"] == ["negative_profit_positive_ocf_explained"]
    assert plan["gap_reasons"] == ["no_accepted_claim_in_context"]
    assert plan["context"]["company_scope"] == "parent_company"
    assert plan["context"]["resolution"]["company_scope"] == "explicit"
