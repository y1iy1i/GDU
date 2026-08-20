import json
from pathlib import Path

from gdu.logic_v01 import validate_aif_interface
from gdu.query_planner_v01 import plan_query, search_source_pages


GRAPH = (
    Path(__file__).parents[1]
    / "research_inputs/pilot_02_pgkd/GDU_LOGIC_METHOD_SLICE_V0_1.json"
)


def load_graph():
    return json.loads(GRAPH.read_text(encoding="utf-8"))


def test_pgkd_method_slice_is_valid_but_question_exposes_gap():
    graph = load_graph()
    assert validate_aif_interface(graph) == []
    plan = plan_query(graph, "PGKD每轮训练新学生后，评估的是新模型还是旧模型？")
    assert plan["status"] == "gap"
    assert plan["query_structure"] == "source_conflict_resolution"
    assert plan["missing_atoms"] == [
        "pgkd_evaluated_model_identity",
        "pgkd_identity_source_resolved",
    ]
    assert plan["context"]["document_scope"] == "pgkd-emnlp-2024"
    assert plan["source_lookup"]["required"] is True
    assert plan["expansion"]["max_hops"] == 2


def test_formula_search_tolerates_lost_spaces_and_superscripts():
    pages = {
        3: "the best model on the validation set, modelbest is returned",
        4: "modeli+1 trainmodelonhistory; new_loss evaluate(modeli,Dval); modelbest modeli",
    }
    found = search_source_pages(
        pages,
        ["train model", "evaluate(model", "model best", "best model on the validation set"],
    )
    assert [item["physical_page"] for item in found] == [4, 3]
