import json
from copy import deepcopy
from pathlib import Path

import pytest

from gdu.promotion_v01 import (
    promote_candidate_transaction,
    validate_candidate_envelope,
)


ROOT = Path(__file__).parents[1]
BASE = ROOT / "research_inputs/replication_01_lafang_2025/GDU_LOGIC_REAL_SLICE_V0_1.json"
CANDIDATE = ROOT / "research_inputs/replication_01_lafang_2025/GDU_QUERY_GAP_CANDIDATE_V0_1.json"
GATES = {
    "context_matches_consolidated_2025",
    "cross_page_table_reconciles",
    "component_sum_reconciles_to_total_cash_change",
    "causal_wording_preserves_report_scope",
    "limitation_prevents_single-cause_overclaim",
}


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def valid_envelope(candidate):
    return validate_candidate_envelope(
        candidate,
        required_gates=GATES,
        expected_document_id="lafang-2025-annual-report",
    )


def promote_with(base, candidate, builder):
    return promote_candidate_transaction(
        base,
        candidate,
        validation=valid_envelope(candidate),
        event_id="FRAMEWORK-TEST-001",
        recorded_at="2026-08-20T21:00:00+08:00",
        output_format="gdu-framework-test-v0.2",
        operation="test_promotion",
        build_additions=builder,
    )


def test_envelope_rejects_missing_source_locator_before_domain_logic():
    candidate = load(CANDIDATE)
    candidate["candidate_evidence"][0]["source_locator"] = ""
    result = valid_envelope(candidate)
    assert result["valid"] is False
    assert "source_locator_missing" in result["errors"]


def test_transaction_rejects_id_collision_with_base_graph():
    base = load(BASE)
    candidate = load(CANDIDATE)
    existing = base["information_nodes"][0]["id"]

    def builder(_candidate, event_id):
        return ([{
            "id": existing,
            "kind": "evidence",
            "text": "collision",
            "provenance": {
                "source_locator": "paper.pdf#physical-page=1",
                "source_hash": candidate["source_pdf_sha256"],
                "growth_event": event_id,
            },
        }], [])

    with pytest.raises(ValueError, match="promoted_node_id_collision"):
        promote_with(base, candidate, builder)


def test_transaction_rejects_missing_growth_provenance():
    base = load(BASE)
    candidate = load(CANDIDATE)

    def builder(_candidate, _event_id):
        return ([{
            "id": "E-NO-PROVENANCE",
            "kind": "evidence",
            "text": "missing provenance",
            "provenance": {},
        }], [])

    with pytest.raises(ValueError, match="growth_provenance_missing"):
        promote_with(base, candidate, builder)


def test_transaction_detects_builder_input_mutation():
    base = load(BASE)
    candidate = load(CANDIDATE)
    base_before = deepcopy(base)
    candidate_before = deepcopy(candidate)

    def builder(candidate_input, _event_id):
        candidate_input["question"] = "mutated"
        return ([], [])

    with pytest.raises(ValueError, match="promotion_builder_mutated_input"):
        promote_with(base, candidate, builder)
    assert base == base_before
    assert candidate == candidate_before


def test_plugin_cannot_bypass_final_logic_interface_validation():
    base = load(BASE)
    candidate = load(CANDIDATE)

    def builder(_candidate, _event_id):
        return ([], [{
            "id": "I-BROKEN-PLUGIN",
            "kind": "inference",
            "premises": ["C-NOT-PRESENT"],
            "conclusion": "C-ALSO-NOT-PRESENT",
            "rule_kind": "strict",
            "rule_id": "broken-rule-v1",
        }])

    with pytest.raises(ValueError):
        promote_with(base, candidate, builder)


def test_empty_valid_transaction_is_deterministic_and_does_not_mutate_inputs():
    base = load(BASE)
    candidate = load(CANDIDATE)
    base_before = deepcopy(base)
    candidate_before = deepcopy(candidate)
    first = promote_with(base, candidate, lambda _candidate, _event_id: ([], []))
    second = promote_with(base, candidate, lambda _candidate, _event_id: ([], []))
    assert first == second
    assert base == base_before
    assert candidate == candidate_before
    assert first["revision_history"][-1]["candidate_hash"] == valid_envelope(candidate)["candidate_hash"]
