"""Common safety envelope and transaction for versioned GDU growth."""

from __future__ import annotations

import json
from copy import deepcopy
from hashlib import sha256
from typing import Any, Callable, Mapping, Sequence

from .logic_v01 import validate_aif_interface


AdditionsBuilder = Callable[
    [Mapping[str, Any], str],
    tuple[list[dict[str, Any]], list[dict[str, Any]]],
]


def canonical_candidate_hash(candidate: Mapping[str, Any]) -> str:
    payload = json.dumps(candidate, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(payload.encode("utf-8")).hexdigest()


def validate_candidate_envelope(
    candidate: Mapping[str, Any],
    *,
    required_gates: set[str],
    expected_document_id: str | None = None,
) -> dict[str, Any]:
    """Validate provenance and quarantine rules shared by all growth domains."""

    errors: list[str] = []
    if expected_document_id is not None and candidate.get("document_id") != expected_document_id:
        errors.append("wrong_document")
    if candidate.get("planner_result", {}).get("growth_policy") != "quarantine_before_validation":
        errors.append("candidate_not_quarantined")
    if set(candidate.get("promotion_gate", [])) != required_gates:
        errors.append("promotion_gate_mismatch")

    source_hash = candidate.get("source_pdf_sha256")
    if not isinstance(source_hash, str) or len(source_hash) != 64:
        errors.append("source_hash_missing")

    evidence_items = candidate.get("candidate_evidence", [])
    evidence_ids = [str(item.get("id", "")) for item in evidence_items]
    if not evidence_ids or any(not item_id for item_id in evidence_ids):
        errors.append("candidate_evidence_missing")
    if len(evidence_ids) != len(set(evidence_ids)):
        errors.append("candidate_evidence_id_collision")
    if any(item.get("status") != "visually_verified_candidate" for item in evidence_items):
        errors.append("evidence_not_visually_verified")
    if any(not item.get("source_locator") for item in evidence_items):
        errors.append("source_locator_missing")

    claim_items = candidate.get("candidate_claims", [])
    claim_ids = [str(item.get("id", "")) for item in claim_items]
    if not claim_ids or any(not item_id for item_id in claim_ids):
        errors.append("candidate_claims_missing")
    if len(claim_ids) != len(set(claim_ids)):
        errors.append("candidate_claim_id_collision")
    available_evidence = set(evidence_ids)
    for claim in claim_items:
        if claim.get("status") != "candidate_pending_logic_validation":
            errors.append(f"candidate_status_invalid:{claim.get('id')}")
        refs = set(claim.get("evidence_refs", []))
        if not refs or not refs <= available_evidence:
            errors.append(f"candidate_evidence_invalid:{claim.get('id')}")

    return {
        "valid": not errors,
        "errors": sorted(set(errors)),
        "candidate_hash": canonical_candidate_hash(candidate),
    }


def merge_validation_results(*results: Mapping[str, Any]) -> dict[str, Any]:
    """Combine envelope and domain validation without changing the replay hash."""

    errors = sorted({str(error) for result in results for error in result.get("errors", [])})
    candidate_hash = next(
        (str(result["candidate_hash"]) for result in results if result.get("candidate_hash")), ""
    )
    return {"valid": not errors, "errors": errors, "candidate_hash": candidate_hash}


def _validate_additions(
    graph: Mapping[str, Any],
    information_nodes: Sequence[Mapping[str, Any]],
    scheme_nodes: Sequence[Mapping[str, Any]],
    *,
    event_id: str,
) -> None:
    existing_ids = {
        str(node.get("id"))
        for key in ("information_nodes", "scheme_nodes")
        for node in graph.get(key, [])
    }
    added = list(information_nodes) + list(scheme_nodes)
    added_ids = [str(node.get("id", "")) for node in added]
    if any(not node_id for node_id in added_ids):
        raise ValueError("promoted_node_id_missing")
    if len(added_ids) != len(set(added_ids)):
        raise ValueError("promoted_node_id_collision")
    collisions = sorted(existing_ids & set(added_ids))
    if collisions:
        raise ValueError({"promoted_node_id_collision": collisions})

    for node in information_nodes:
        provenance = node.get("provenance")
        if not isinstance(provenance, Mapping) or provenance.get("growth_event") != event_id:
            raise ValueError(f"growth_provenance_missing:{node.get('id')}")
        if node.get("kind") == "evidence" and not all(
            provenance.get(key) for key in ("source_locator", "source_hash")
        ):
            raise ValueError(f"evidence_provenance_missing:{node.get('id')}")


def promote_candidate_transaction(
    graph: Mapping[str, Any],
    candidate: Mapping[str, Any],
    *,
    validation: Mapping[str, Any],
    event_id: str,
    recorded_at: str,
    output_format: str,
    operation: str,
    build_additions: AdditionsBuilder,
) -> dict[str, Any]:
    """Atomically promote validated additions and reject an invalid resulting graph."""

    if not validation.get("valid"):
        raise ValueError(list(validation.get("errors", [])))
    if validate_aif_interface(graph):
        raise ValueError("base graph does not pass the logic interface")

    graph_before = deepcopy(graph)
    candidate_before = deepcopy(candidate)
    builder_candidate = deepcopy(candidate)
    information_nodes, scheme_nodes = build_additions(builder_candidate, event_id)
    if graph != graph_before or candidate != candidate_before or builder_candidate != candidate_before:
        raise ValueError("promotion_builder_mutated_input")
    _validate_additions(
        graph, information_nodes, scheme_nodes, event_id=event_id
    )

    grown = deepcopy(graph)
    grown["information_nodes"].extend(deepcopy(information_nodes))
    grown["scheme_nodes"].extend(deepcopy(scheme_nodes))
    grown["format"] = output_format
    grown.setdefault("revision_history", []).append(
        {
            "event_id": event_id,
            "recorded_at": recorded_at,
            "operation": operation,
            "parent_format": graph.get("format"),
            "candidate_hash": validation["candidate_hash"],
            "added_information_node_ids": [node["id"] for node in information_nodes],
            "added_scheme_node_ids": [node["id"] for node in scheme_nodes],
        }
    )
    issues = validate_aif_interface(grown)
    if issues:
        raise ValueError([issue.to_dict() for issue in issues])
    return grown
