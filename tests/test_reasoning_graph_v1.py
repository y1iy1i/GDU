import json
from copy import deepcopy
from pathlib import Path

import pytest

from gdu.reasoning_graph_v1 import (
    answer_gate,
    apply_approved_repair,
    audit_path,
    propose_repairs,
)
from scripts.run_reasoning_graph_self_repair_experiment import run


ROOT = Path(__file__).resolve().parents[1]
GRAPH_PATH = ROOT / "research_inputs/replication_01_lafang_2025/GOLD_GDU_SLICE_V1.json"


def graph():
    return json.loads(GRAPH_PATH.read_text(encoding="utf-8"))


def test_validated_path_is_allowed():
    issues = audit_path(graph(), ["A-CF-01", "A-CF-02", "A-CF-04", "A-CF-05"])
    assert answer_gate(issues)["decision"] == "answer_allowed"


def test_wrong_inventory_direction_is_blocked_and_proposed_for_repair():
    candidate = graph()
    node = next(node for node in candidate["nodes"] if node["id"] == "A-CF-03")
    node["statement"] = "2025年公司存货减少2182144.36元"
    node["structured_claim"]["direction"] = "decrease"

    issues = audit_path(candidate, ["A-CF-03", "A-CF-05"])
    gate = answer_gate(issues)
    assert gate["decision"] == "blocked_repair_required"
    assert {item["code"] for item in gate["issues"]} == {"evidence_direction_mismatch"}

    proposals = propose_repairs(candidate, issues)
    assert len(proposals) == 1
    assert proposals[0]["replacement"]["structured_claim"]["direction"] == "increase"
    assert proposals[0]["approval_status"] == "pending"


def test_repair_requires_approval_and_retains_old_version():
    candidate = graph()
    node = next(node for node in candidate["nodes"] if node["id"] == "A-CF-03")
    node["structured_claim"]["direction"] = "decrease"
    issues = audit_path(candidate, ["A-CF-03"])
    proposal = propose_repairs(candidate, issues)[0]

    with pytest.raises(PermissionError):
        apply_approved_repair(candidate, proposal, approved=False)

    repaired = apply_approved_repair(candidate, proposal, approved=True)
    old = next(node for node in repaired["nodes"] if node["id"] == "A-CF-03")
    new = next(node for node in repaired["nodes"] if node["id"] == "A-CF-03-v2")
    assert old["status"] == "superseded"
    assert new["status"] == "machine_verified"
    assert new["supersedes"] == "A-CF-03"
    assert repaired["repair_log"][0]["affected_paths_must_recompute"] is True
    assert answer_gate(audit_path(repaired, ["A-CF-03-v2", "A-CF-05"]))["decision"] == "answer_allowed"


def test_explicit_conflict_preserves_uncertainty_instead_of_forcing_answer():
    candidate = graph()
    candidate["nodes"].append(
        {
            "id": "A-ALT",
            "statement": "存在另一项仍待核验的相反解释",
            "role": "interpretation",
            "status": "active",
            "version": 1,
            "evidence_refs": ["E-156-INV"],
        }
    )
    candidate["edges"].append(
        {"id": "R-CONFLICT", "source": "A-CF-03", "target": "A-ALT", "type": "conflicts"}
    )
    gate = answer_gate(audit_path(candidate, ["A-CF-03", "A-ALT"]))
    assert gate["decision"] == "answer_with_uncertainty"


def test_missing_path_element_blocks_answer():
    gate = answer_gate(audit_path(graph(), ["A-CF-01", "A-NOT-THERE"]))
    assert gate["decision"] == "blocked_repair_required"


def test_reproducible_experiment_passes_without_remote_calls():
    result = run(GRAPH_PATH)
    assert result["stage_pass"] is True
    assert result["remote_model_calls"] == 0
