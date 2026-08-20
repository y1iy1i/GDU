"""Deterministic audit and versioned repair primitives for a GDU reasoning graph.

This module intentionally does not generate free-form answers.  It protects the
graph before an answer model is allowed to use a reasoning path.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, asdict
from typing import Any, Iterable, Mapping


ACTIVE_STATUSES = {"active", "validated", "machine_verified"}


@dataclass(frozen=True)
class AuditIssue:
    code: str
    severity: str
    node_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    message: str

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["node_ids"] = list(self.node_ids)
        result["evidence_ids"] = list(self.evidence_ids)
        return result


def _index(items: Iterable[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    return {str(item["id"]): item for item in items}


def _expected_direction(normalization: Mapping[str, Any]) -> str | None:
    if normalization.get("kind") != "signed_decrease_increase":
        return None
    value = normalization.get("raw_value")
    if not isinstance(value, (int, float)):
        return None
    if value < 0:
        return "increase"
    if value > 0:
        return "decrease"
    return "unchanged"


def audit_path(graph: Mapping[str, Any], path_node_ids: Iterable[str]) -> list[AuditIssue]:
    """Audit only the subgraph selected for one answer.

    High-severity issues mean the answer must not treat the affected node as a
    valid premise.  The checks are deliberately deterministic; semantic review
    can be added later as a separate candidate-producing stage.
    """

    nodes = _index(graph.get("nodes", []))
    evidence = _index(graph.get("evidence", []))
    selected = tuple(dict.fromkeys(path_node_ids))
    selected_set = set(selected)
    issues: list[AuditIssue] = []

    for node_id in selected:
        node = nodes.get(node_id)
        if node is None:
            issues.append(
                AuditIssue("missing_node", "high", (node_id,), (), f"路径引用不存在的节点 {node_id}")
            )
            continue
        if node.get("status") not in ACTIVE_STATUSES:
            issues.append(
                AuditIssue(
                    "inactive_node",
                    "high",
                    (node_id,),
                    tuple(node.get("evidence_refs", [])),
                    f"节点 {node_id} 当前状态为 {node.get('status')}，不可作为有效前提",
                )
            )
        for evidence_id in node.get("evidence_refs", []):
            if evidence_id not in evidence:
                issues.append(
                    AuditIssue(
                        "missing_evidence",
                        "high",
                        (node_id,),
                        (evidence_id,),
                        f"节点 {node_id} 引用的证据 {evidence_id} 不存在",
                    )
                )

        structured = node.get("structured_claim", {})
        for evidence_id in node.get("evidence_refs", []):
            item = evidence.get(evidence_id)
            if item is None:
                continue
            expected = _expected_direction(item.get("normalization", {}))
            claimed = structured.get("direction")
            if expected is not None and claimed is not None and claimed != expected:
                issues.append(
                    AuditIssue(
                        "evidence_direction_mismatch",
                        "high",
                        (node_id,),
                        (evidence_id,),
                        f"节点方向为 {claimed}，但证据规则解析结果为 {expected}",
                    )
                )

    for edge in graph.get("edges", []):
        if edge.get("type") != "conflicts":
            continue
        source = str(edge.get("source"))
        target = str(edge.get("target"))
        if source in selected_set and target in selected_set:
            if nodes.get(source, {}).get("status") in ACTIVE_STATUSES and nodes.get(
                target, {}
            ).get("status") in ACTIVE_STATUSES:
                issues.append(
                    AuditIssue(
                        "unresolved_conflict",
                        "medium",
                        (source, target),
                        (),
                        f"路径同时使用存在冲突的节点 {source} 与 {target}",
                    )
                )
    return issues


def answer_gate(issues: Iterable[AuditIssue]) -> dict[str, Any]:
    issues = list(issues)
    blockers = [issue for issue in issues if issue.severity == "high"]
    conflicts = [issue for issue in issues if issue.code == "unresolved_conflict"]
    if blockers:
        decision = "blocked_repair_required"
    elif conflicts:
        decision = "answer_with_uncertainty"
    else:
        decision = "answer_allowed"
    return {
        "decision": decision,
        "issues": [issue.to_dict() for issue in issues],
    }


def propose_repairs(graph: Mapping[str, Any], issues: Iterable[AuditIssue]) -> list[dict[str, Any]]:
    """Create evidence-bound patches; never mutate the graph."""

    nodes = _index(graph.get("nodes", []))
    evidence = _index(graph.get("evidence", []))
    proposals: list[dict[str, Any]] = []
    for issue in issues:
        if issue.code != "evidence_direction_mismatch":
            continue
        node = nodes[issue.node_ids[0]]
        item = evidence[issue.evidence_ids[0]]
        normalization = item["normalization"]
        expected = _expected_direction(normalization)
        magnitude = abs(float(normalization["raw_value"]))
        direction_label = {"increase": "增加", "decrease": "减少", "unchanged": "未变化"}[
            expected
        ]
        proposals.append(
            {
                "id": f"RP-{len(proposals) + 1:03d}",
                "operation": "supersede_node",
                "target_node_id": node["id"],
                "reason": issue.code,
                "evidence_refs": list(issue.evidence_ids),
                "verification": "deterministic_rule",
                "approval_status": "pending",
                "replacement": {
                    "statement": (
                        f"{normalization['period']}年{normalization['subject']}"
                        f"{normalization['metric']}{direction_label} {magnitude:.2f}"
                        f"{normalization.get('unit', '')}"
                    ),
                    "structured_claim": {
                        **node.get("structured_claim", {}),
                        "direction": expected,
                        "magnitude": magnitude,
                        "unit": normalization.get("unit"),
                    },
                },
            }
        )
    return proposals


def apply_approved_repair(
    graph: Mapping[str, Any], proposal: Mapping[str, Any], *, approved: bool
) -> dict[str, Any]:
    """Apply one approved patch as a new node version while retaining history."""

    if not approved:
        raise PermissionError("repair proposal requires explicit approval")
    if proposal.get("operation") != "supersede_node":
        raise ValueError("unsupported repair operation")
    updated = deepcopy(graph)
    target_id = str(proposal["target_node_id"])
    target = next((node for node in updated["nodes"] if node["id"] == target_id), None)
    if target is None:
        raise KeyError(target_id)
    target["status"] = "superseded"
    version = int(target.get("version", 1)) + 1
    new_id = f"{target_id}-v{version}"
    replacement = proposal["replacement"]
    new_node = deepcopy(target)
    new_node.update(
        {
            "id": new_id,
            "statement": replacement["statement"],
            "structured_claim": deepcopy(replacement["structured_claim"]),
            "status": "machine_verified",
            "version": version,
            "supersedes": target_id,
            "repair_proposal_id": proposal["id"],
        }
    )
    updated["nodes"].append(new_node)

    cloned_edges = []
    for edge in updated.get("edges", []):
        if target_id not in {edge.get("source"), edge.get("target")}:
            continue
        clone = deepcopy(edge)
        clone["id"] = f"{edge['id']}-r{version}"
        if clone.get("source") == target_id:
            clone["source"] = new_id
        if clone.get("target") == target_id:
            clone["target"] = new_id
        clone["derived_from_repair"] = proposal["id"]
        cloned_edges.append(clone)
    updated.setdefault("edges", []).extend(cloned_edges)
    updated.setdefault("repair_log", []).append(
        {
            "proposal_id": proposal["id"],
            "old_node_id": target_id,
            "new_node_id": new_id,
            "affected_paths_must_recompute": True,
        }
    )
    return updated
