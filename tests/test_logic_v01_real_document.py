import json
from decimal import Decimal
from pathlib import Path

from gdu.logic_v01 import (
    belnap_status,
    compile_structured_arguments,
    grounded_labels,
    incremental_recompute_after_invalidation,
    recompute_after_invalidation,
    validate_aif_interface,
)


ARTIFACT = (
    Path(__file__).parents[1]
    / "research_inputs"
    / "replication_01_lafang_2025"
    / "GDU_LOGIC_REAL_SLICE_V0_1.json"
)


def load_graph():
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def by_id(graph):
    return {node["id"]: node for node in graph["information_nodes"]}


def sum_rows(node):
    return sum((Decimal(row["amount"]) for row in node["values"]), Decimal("0"))


def test_real_document_graph_passes_logic_interface():
    assert validate_aif_interface(load_graph()) == []


def test_all_adjustments_reconcile_to_reported_ocf_without_residual():
    graph = load_graph()
    nodes = by_id(graph)
    noncash = sum_rows(nodes["C-NONCASH-ROWS"])
    working_capital = sum_rows(nodes["C-WORKING-CAPITAL-ROWS"])
    other = sum_rows(nodes["C-OTHER-ROWS"])
    calculated = Decimal(nodes["C-NET-PROFIT"]["value"]["amount"]) + noncash + working_capital + other
    reported = Decimal(nodes["C-OCF-REPORTED"]["value"]["amount"])

    assert noncash == Decimal(nodes["C-NONCASH-TOTAL"]["value"]["amount"])
    assert working_capital == Decimal(nodes["C-WORKING-CAPITAL-TOTAL"]["value"]["amount"])
    assert other == Decimal(nodes["C-OTHER-TOTAL"]["value"]["amount"])
    assert calculated == reported == Decimal("72545781.16")
    assert reported - calculated == Decimal("0.00")


def test_real_reasoning_accepts_reconciliation_and_rejects_cash_heuristic():
    graph = load_graph()
    arguments, attacks = compile_structured_arguments(graph)
    labels = grounded_labels(arguments, attacks)

    bridge = next(arg for arg in arguments.values() if arg.conclusion == "C-PROFIT-OCF-BRIDGE")
    heuristic = next(arg for arg in arguments.values() if arg.conclusion == "C-CASH-INCREASE-HEURISTIC")
    observed = next(arg for arg in arguments.values() if arg.conclusion == "C-CASH-INCREASE-OBSERVED")

    assert labels[bridge.id] == "accepted"
    assert labels[heuristic.id] == "rejected"
    assert labels[observed.id] == "accepted"
    assert belnap_status(graph, "cash_and_equivalents_increased") == "BOTH"


def test_bridge_argument_retains_source_claims_needed_for_provenance():
    graph = load_graph()
    arguments, _ = compile_structured_arguments(graph)
    bridge = next(arg for arg in arguments.values() if arg.conclusion == "C-PROFIT-OCF-BRIDGE")

    assert bridge.ordinary_premises == {
        "C-NET-PROFIT",
        "C-NONCASH-ROWS",
        "C-WORKING-CAPITAL-ROWS",
        "C-OTHER-ROWS",
        "C-OCF-REPORTED",
    }


def test_invalidated_row_group_breaks_explanation_but_not_observed_ocf():
    graph = load_graph()
    full = recompute_after_invalidation(
        graph, ["C-WORKING-CAPITAL-ROWS"], event_id="REAL-REV-1"
    )
    incremental = incremental_recompute_after_invalidation(
        graph, ["C-WORKING-CAPITAL-ROWS"], event_id="REAL-REV-1"
    )

    assert incremental["active_claim_ids"] == full["active_claim_ids"]
    assert incremental["active_inference_ids"] == full["active_inference_ids"]
    assert "C-OCF-REPORTED" in full["active_claim_ids"]
    assert "C-WORKING-CAPITAL-TOTAL" not in full["active_claim_ids"]
    assert "C-OCF-CALCULATED" not in full["active_claim_ids"]
    assert "C-RECONCILIATION-MATCH" not in full["active_claim_ids"]
    assert "C-PROFIT-OCF-BRIDGE" not in full["active_claim_ids"]
    assert "I-OCF-TO-CASH-HEURISTIC" in full["active_inference_ids"]
    assert "I-OCF-TO-CASH-HEURISTIC" not in incremental["affected_inference_ids"]
