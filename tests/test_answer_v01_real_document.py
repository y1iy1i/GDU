import json
from pathlib import Path

import pytest

from gdu.answer_v01 import build_answer_package


ARTIFACT = (
    Path(__file__).parents[1]
    / "research_inputs"
    / "replication_01_lafang_2025"
    / "GDU_LOGIC_REAL_SLICE_V0_1.json"
)


def load_graph():
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def test_answer_uses_accepted_bridge_and_retains_limits_and_sources():
    package = build_answer_package(
        load_graph(),
        target_claim_ids=["C-PROFIT-OCF-BRIDGE"],
        limitation_claim_ids=["C-CASH-INCREASE-OBSERVED", "C-CATEGORY-DISTINCT"],
    )

    assert all(item["grounded_label"] == "accepted" for item in package["selected_claims"])
    assert "完整调节后的金额与原文经营现金流完全一致" in package["answer"]
    assert "净减少187,884,922.38元" in package["answer"]
    assert "C-CASH-INCREASE-HEURISTIC" in package["rejected_claim_ids"]
    assert {item["evidence_id"] for item in package["evidence"]} == {
        "E-156-A", "E-156-B", "E-157-A", "E-157-B"
    }
    assert {step["inference_id"] for step in package["proof_steps"]} >= {
        "I-SUM-NONCASH",
        "I-SUM-WORKING-CAPITAL",
        "I-SUM-OTHER",
        "I-RECONCILE-OCF",
        "I-COMPARE-OCF",
        "I-BUILD-BRIDGE",
    }
    proof_order = [step["inference_id"] for step in package["proof_steps"]]
    assert proof_order.index("I-RECONCILE-OCF") < proof_order.index("I-COMPARE-OCF")
    assert proof_order.index("I-COMPARE-OCF") < proof_order.index("I-BUILD-BRIDGE")


def test_rejected_heuristic_cannot_be_selected_as_answer():
    with pytest.raises(ValueError, match="no accepted argument"):
        build_answer_package(
            load_graph(), target_claim_ids=["C-CASH-INCREASE-HEURISTIC"]
        )
