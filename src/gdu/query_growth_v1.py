"""Query-driven gap detection, evidence expansion, and graph growth."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable, Mapping


REQUIRED_GROWTH_ROLES = {
    ("mechanism", "noncash_adjustments"),
    ("mechanism", "working_capital_adjustments"),
    ("bridge", "combined_explanation"),
}


def prune_growth_targets(graph: Mapping[str, Any]) -> dict[str, Any]:
    """Create the blinded working graph without changing the frozen Gold."""

    pruned = deepcopy(graph)
    removed = {
        node["id"]
        for node in pruned.get("nodes", [])
        if (node.get("role"), node.get("mechanism_type", "combined_explanation"))
        in REQUIRED_GROWTH_ROLES
    }
    pruned["nodes"] = [node for node in pruned.get("nodes", []) if node["id"] not in removed]
    pruned["edges"] = [
        edge
        for edge in pruned.get("edges", [])
        if edge.get("source") not in removed and edge.get("target") not in removed
    ]
    pruned["blinding"] = {"removed_node_count": len(removed), "removed_ids_hidden": True}
    return pruned


def detect_explanation_gap(graph: Mapping[str, Any]) -> dict[str, Any]:
    present = {
        (node.get("role"), node.get("mechanism_type", "combined_explanation"))
        for node in graph.get("nodes", [])
        if node.get("status") in {"active", "validated", "machine_verified"}
    }
    missing = sorted(REQUIRED_GROWTH_ROLES - present)
    return {
        "decision": "blocked_missing_bridge" if missing else "answer_allowed",
        "missing_roles": [f"{role}:{kind}" for role, kind in missing],
    }


def expand_adjacent_evidence(
    graph: Mapping[str, Any], seed_node_ids: Iterable[str], *, page_radius: int = 1
) -> dict[str, Any]:
    nodes = {node["id"]: node for node in graph.get("nodes", [])}
    evidence = {item["id"]: item for item in graph.get("evidence", [])}
    seed_pages = []
    for node_id in seed_node_ids:
        for evidence_id in nodes[node_id].get("evidence_refs", []):
            seed_pages.append(int(evidence[evidence_id]["physical_page"]))
    if not seed_pages:
        raise ValueError("seed nodes have no evidence pages")
    lower = min(seed_pages) - page_radius
    upper = max(seed_pages) + page_radius
    selected = [
        deepcopy(item)
        for item in evidence.values()
        if lower <= int(item["physical_page"]) <= upper
    ]
    return {
        "seed_node_ids": list(seed_node_ids),
        "seed_pages": sorted(set(seed_pages)),
        "page_radius": page_radius,
        "selected_pages": sorted({int(item["physical_page"]) for item in selected}),
        "evidence": selected,
    }


def validate_growth_response(
    response: Mapping[str, Any], available_evidence: Iterable[Mapping[str, Any]]
) -> dict[str, Any]:
    available = {item["id"] for item in available_evidence}
    nodes = response.get("nodes", [])
    edges = response.get("edges", [])
    ids = {node.get("candidate_id") for node in nodes}
    errors: list[str] = []
    if len(ids) != len(nodes):
        errors.append("duplicate_candidate_id")

    roles = set()
    for node in nodes:
        role_key = (node.get("role"), node.get("mechanism_type"))
        roles.add(role_key)
        refs = set(node.get("evidence_refs", []))
        if not refs or not refs <= available:
            errors.append(f"invalid_evidence_refs:{node.get('candidate_id')}")
        if role_key == ("mechanism", "noncash_adjustments") and "E-156-A" not in refs:
            errors.append("noncash_missing_source")
        if role_key == ("mechanism", "working_capital_adjustments"):
            if not {"E-156-B", "E-157-A"} <= refs:
                errors.append("working_capital_missing_cross_page_source")
            if node.get("inventory_direction") != "increase":
                errors.append("inventory_direction_not_verified")
        if role_key == ("bridge", "combined_explanation"):
            if len(refs) < 2:
                errors.append("bridge_insufficient_evidence")
            statement = str(node.get("statement", ""))
            if not any(term in statement for term in ("不能", "不等于", "不代表", "不否定")):
                errors.append("bridge_missing_limitation")

    missing = REQUIRED_GROWTH_ROLES - roles
    errors.extend(f"missing_role:{role}:{kind}" for role, kind in sorted(missing))

    allowed_endpoint_ids = ids | {"OBS-PROFIT", "OBS-OCF", "OBS-CASH"}
    bridge_ids = {
        node["candidate_id"]
        for node in nodes
        if (node.get("role"), node.get("mechanism_type"))
        == ("bridge", "combined_explanation")
    }
    composed_types = set()
    node_roles = {node["candidate_id"]: node.get("mechanism_type") for node in nodes}
    for edge in edges:
        if edge.get("source") not in allowed_endpoint_ids or edge.get("target") not in allowed_endpoint_ids:
            errors.append(f"unknown_edge_endpoint:{edge.get('edge_id')}")
        if edge.get("target") in bridge_ids and edge.get("type") == "composes":
            composed_types.add(node_roles.get(edge.get("source")))
    if not {"noncash_adjustments", "working_capital_adjustments"} <= composed_types:
        errors.append("bridge_not_composed_from_both_mechanisms")

    return {"valid": not errors, "errors": errors, "recovered_roles": sorted(f"{a}:{b}" for a, b in roles)}


def integrate_growth(
    graph: Mapping[str, Any], response: Mapping[str, Any], validation: Mapping[str, Any]
) -> dict[str, Any]:
    if not validation.get("valid"):
        raise ValueError("candidate growth did not pass validation")
    grown = deepcopy(graph)
    id_map = {}
    for index, candidate in enumerate(response["nodes"], 1):
        new_id = f"GROW-{index:03d}"
        id_map[candidate["candidate_id"]] = new_id
        grown["nodes"].append(
            {
                "id": new_id,
                "role": candidate["role"],
                "mechanism_type": candidate["mechanism_type"],
                "statement": candidate["statement"],
                # Structural checks prove traceability and shape, not that a
                # semantic explanation is complete.  A later closure/review
                # stage must explicitly promote this node to ``validated``.
                "status": "structurally_valid",
                "evidence_refs": list(candidate["evidence_refs"]),
                "growth_origin": "query_gap_expansion",
            }
        )
    for index, edge in enumerate(response["edges"], 1):
        grown["edges"].append(
            {
                "id": f"GROW-R{index:03d}",
                "source": id_map.get(edge["source"], edge["source"]),
                "target": id_map.get(edge["target"], edge["target"]),
                "type": edge["type"],
                "growth_origin": "query_gap_expansion",
            }
        )
    return grown
