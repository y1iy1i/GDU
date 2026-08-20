import json
from pathlib import Path

from gdu.query_growth_v1 import (
    detect_explanation_gap,
    expand_adjacent_evidence,
    integrate_growth,
    prune_growth_targets,
    validate_growth_response,
)


ROOT = Path(__file__).resolve().parents[1]
GOLD = ROOT / "research_inputs/replication_01_lafang_2025/GOLD_GDU_GROWTH_V1.json"


def load_gold():
    return json.loads(GOLD.read_text(encoding="utf-8"))


def fixture_response():
    return {
        "nodes": [
            {
                "candidate_id": "C01", "role": "mechanism",
                "mechanism_type": "noncash_adjustments",
                "statement": "资产减值准备、折旧摊销和投资损失构成调节项目",
                "evidence_refs": ["E-156-A"], "inventory_direction": "not_mentioned"
            },
            {
                "candidate_id": "C02", "role": "mechanism",
                "mechanism_type": "working_capital_adjustments",
                "statement": "应收减少、应付增加和存货增加共同参与营运资本调节",
                "evidence_refs": ["E-156-B", "E-157-A"], "inventory_direction": "increase"
            },
            {
                "candidate_id": "C03", "role": "bridge",
                "mechanism_type": "combined_explanation",
                "statement": "两类调节共同解释差异，但正经营现金流不等于整体现金改善",
                "evidence_refs": ["E-156-A", "E-156-B", "E-157-A", "E-157-B"],
                "inventory_direction": "not_mentioned"
            }
        ],
        "edges": [
            {"edge_id": "R01", "source": "C01", "target": "C03", "type": "composes"},
            {"edge_id": "R02", "source": "C02", "target": "C03", "type": "composes"},
            {"edge_id": "R03", "source": "OBS-CASH", "target": "C03", "type": "limits"}
        ]
    }


def test_pruned_graph_is_blocked_and_expansion_is_bounded():
    pruned = prune_growth_targets(load_gold())
    assert detect_explanation_gap(pruned)["decision"] == "blocked_missing_bridge"
    expansion = expand_adjacent_evidence(pruned, ["OBS-PROFIT", "OBS-OCF", "OBS-CASH"])
    assert expansion["selected_pages"] == [156, 157]


def test_structurally_valid_growth_is_not_yet_answer_ready():
    pruned = prune_growth_targets(load_gold())
    expansion = expand_adjacent_evidence(pruned, ["OBS-PROFIT", "OBS-OCF", "OBS-CASH"])
    response = fixture_response()
    validation = validate_growth_response(response, expansion["evidence"])
    assert validation["valid"] is True
    grown = integrate_growth(pruned, response, validation)
    assert detect_explanation_gap(grown)["decision"] == "blocked_missing_bridge"
    added = [node for node in grown["nodes"] if node["id"].startswith("GROW-")]
    assert len(added) == 3
    assert {node["status"] for node in added} == {"structurally_valid"}


def test_reviewed_growth_can_be_promoted_and_answered():
    pruned = prune_growth_targets(load_gold())
    expansion = expand_adjacent_evidence(pruned, ["OBS-PROFIT", "OBS-OCF"])
    response = fixture_response()
    validation = validate_growth_response(response, expansion["evidence"])
    grown = integrate_growth(pruned, response, validation)
    for node in grown["nodes"]:
        if node["id"].startswith("GROW-"):
            node["status"] = "validated"
    assert detect_explanation_gap(grown)["decision"] == "answer_allowed"


def test_wrong_inventory_sign_is_rejected():
    pruned = prune_growth_targets(load_gold())
    expansion = expand_adjacent_evidence(pruned, ["OBS-PROFIT", "OBS-OCF"])
    response = fixture_response()
    response["nodes"][1]["inventory_direction"] = "decrease"
    validation = validate_growth_response(response, expansion["evidence"])
    assert validation["valid"] is False
    assert "inventory_direction_not_verified" in validation["errors"]


def test_bridge_without_limitation_is_rejected():
    pruned = prune_growth_targets(load_gold())
    expansion = expand_adjacent_evidence(pruned, ["OBS-PROFIT", "OBS-OCF"])
    response = fixture_response()
    response["nodes"][2]["statement"] = "两类调节共同解释利润和经营现金流差异"
    validation = validate_growth_response(response, expansion["evidence"])
    assert validation["valid"] is False
    assert "bridge_missing_limitation" in validation["errors"]
