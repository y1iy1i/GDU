"""Minimal interface laboratory for the GDU candidate logic architecture v0.1.

The module tests compatibility boundaries.  It is not a production reasoner and
does not replace any frozen GDU schema.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from itertools import product
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class InterfaceIssue:
    code: str
    location: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class StructuredArgument:
    id: str
    conclusion: str
    ordinary_premises: frozenset[str]
    subarguments: frozenset[str]
    top_inference: str | None
    rule_kind: str | None


def _by_id(items: Iterable[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    return {str(item["id"]): item for item in items}


def _same_scope(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    return left.get("context", {}) == right.get("context", {})


def _inference_order(schemes: Mapping[str, Mapping[str, Any]]) -> list[str] | None:
    """Return a stable producer-before-consumer order, or None for a cycle."""

    inferences = {
        scheme_id: scheme
        for scheme_id, scheme in schemes.items()
        if scheme.get("kind") == "inference" and scheme.get("active", True)
    }
    producers: dict[str, set[str]] = {}
    for scheme_id, inference in inferences.items():
        producers.setdefault(str(inference["conclusion"]), set()).add(scheme_id)
    dependencies = {
        scheme_id: {
            producer
            for premise in inference.get("premises", [])
            for producer in producers.get(str(premise), set())
        }
        for scheme_id, inference in inferences.items()
    }
    ready = sorted(scheme_id for scheme_id, deps in dependencies.items() if not deps)
    order: list[str] = []
    while ready:
        current = ready.pop(0)
        order.append(current)
        for scheme_id in sorted(dependencies):
            if current not in dependencies[scheme_id]:
                continue
            dependencies[scheme_id].remove(current)
            if not dependencies[scheme_id] and scheme_id not in order and scheme_id not in ready:
                ready.append(scheme_id)
                ready.sort()
    return order if len(order) == len(inferences) else None


def validate_aif_interface(graph: Mapping[str, Any]) -> list[InterfaceIssue]:
    """Check the v0.1 representation contract without mutating the graph."""

    info = _by_id(graph.get("information_nodes", []))
    schemes = _by_id(graph.get("scheme_nodes", []))
    issues: list[InterfaceIssue] = []

    for node_id, node in info.items():
        kind = node.get("kind")
        if kind not in {"evidence", "claim"}:
            issues.append(InterfaceIssue("invalid_information_kind", node_id, str(kind)))
            continue
        if kind == "evidence":
            provenance = node.get("provenance", {})
            if not provenance.get("source_locator") or not provenance.get("source_hash"):
                issues.append(
                    InterfaceIssue(
                        "evidence_provenance_missing", node_id, "证据缺少位置或来源哈希"
                    )
                )
        if kind == "claim":
            if node.get("polarity") not in {"positive", "negative"}:
                issues.append(InterfaceIssue("claim_polarity_missing", node_id, "命题缺少极性"))
            if not isinstance(node.get("context"), Mapping):
                issues.append(InterfaceIssue("claim_context_missing", node_id, "命题缺少Context"))
            provenance = node.get("provenance", {})
            if node.get("asserted", False):
                refs = provenance.get("quoted_from", [])
                if not refs or any(ref not in info or info[ref].get("kind") != "evidence" for ref in refs):
                    issues.append(
                        InterfaceIssue("asserted_claim_untraced", node_id, "来源命题未追溯到Evidence")
                    )
            elif not provenance.get("generated_by"):
                issues.append(
                    InterfaceIssue("derived_claim_untraced", node_id, "派生命题未追溯到Inference")
                )

    for scheme_id, scheme in schemes.items():
        kind = scheme.get("kind")
        if kind == "inference":
            premises = scheme.get("premises", [])
            conclusion = scheme.get("conclusion")
            if not premises:
                issues.append(InterfaceIssue("inference_without_premise", scheme_id, "推理没有前提"))
            if any(ref not in info or info[ref].get("kind") != "claim" for ref in premises):
                issues.append(InterfaceIssue("invalid_inference_premise", scheme_id, "前提不是Claim"))
            if conclusion not in info or info.get(conclusion, {}).get("kind") != "claim":
                issues.append(InterfaceIssue("invalid_inference_conclusion", scheme_id, "结论不是Claim"))
            if scheme.get("rule_kind") not in {"strict", "defeasible"} or not scheme.get("rule_id"):
                issues.append(InterfaceIssue("inference_rule_missing", scheme_id, "推理缺少规则类型或ID"))
        elif kind == "conflict":
            attack_kind = scheme.get("attack_kind")
            source = info.get(str(scheme.get("source")))
            target_id = str(scheme.get("target"))
            target_type = scheme.get("target_type")
            if attack_kind not in {"rebut", "undermine", "undercut"}:
                issues.append(InterfaceIssue("invalid_attack_kind", scheme_id, str(attack_kind)))
            if source is None or source.get("kind") != "claim":
                issues.append(InterfaceIssue("invalid_attack_source", scheme_id, "攻击来源不是Claim"))
            if target_type == "claim":
                target = info.get(target_id)
                if target is None or target.get("kind") != "claim":
                    issues.append(InterfaceIssue("invalid_attack_target", scheme_id, "攻击目标不是Claim"))
                elif attack_kind == "rebut" and source is not None:
                    if not _same_scope(source, target) and not scheme.get("scope_alignment", False):
                        issues.append(
                            InterfaceIssue(
                                "rebut_scope_mismatch", scheme_id, "不同Context不能自动构成rebut"
                            )
                        )
            elif target_type == "inference":
                if target_id not in schemes or schemes[target_id].get("kind") != "inference":
                    issues.append(InterfaceIssue("invalid_attack_target", scheme_id, "攻击目标不是Inference"))
                if attack_kind != "undercut":
                    issues.append(
                        InterfaceIssue("attack_target_type_mismatch", scheme_id, "Inference只接受undercut")
                    )
                elif schemes.get(target_id, {}).get("rule_kind") != "defeasible":
                    issues.append(
                        InterfaceIssue(
                            "strict_inference_cannot_be_undercut",
                            scheme_id,
                            "严格推理不能被undercut；应攻击前提或重新分类规则",
                        )
                    )
            else:
                issues.append(InterfaceIssue("attack_target_type_missing", scheme_id, str(target_type)))
        else:
            issues.append(InterfaceIssue("invalid_scheme_kind", scheme_id, str(kind)))
    if _inference_order(schemes) is None:
        issues.append(
            InterfaceIssue(
                "cyclic_inference_dependency",
                "scheme_nodes",
                "v0.1不允许推理依赖环；攻击环仍然允许",
            )
        )
    return issues


def compile_structured_arguments(
    graph: Mapping[str, Any],
) -> tuple[dict[str, StructuredArgument], set[tuple[str, str]]]:
    """Compile AIF-like nodes into structured arguments and Dung attacks."""

    issues = validate_aif_interface(graph)
    if issues:
        raise ValueError([issue.to_dict() for issue in issues])
    info = _by_id(graph["information_nodes"])
    schemes = _by_id(graph["scheme_nodes"])
    arguments: dict[str, StructuredArgument] = {}
    claim_arguments: dict[str, set[str]] = {}

    for claim_id, claim in info.items():
        if claim.get("kind") != "claim" or not claim.get("asserted", False) or not claim.get("active", True):
            continue
        argument_id = f"ARG-P-{claim_id}"
        arguments[argument_id] = StructuredArgument(
            argument_id, claim_id, frozenset({claim_id}), frozenset(), None, None
        )
        claim_arguments.setdefault(claim_id, set()).add(argument_id)

    order = _inference_order(schemes)
    if order is None:  # guarded by validation; keeps the type contract explicit
        raise ValueError("cyclic inference dependency")
    for inference_id in order:
        inference = schemes[inference_id]
        premise_argument_sets = [
            sorted(claim_arguments.get(str(ref), set())) for ref in inference["premises"]
        ]
        if not premise_argument_sets or any(not values for values in premise_argument_sets):
            continue
        combinations = list(product(*premise_argument_sets))
        for index, chosen in enumerate(combinations, 1):
            subarguments = set(chosen)
            ordinary_premises = set()
            for argument_id in chosen:
                subarguments.update(arguments[argument_id].subarguments)
                ordinary_premises.update(arguments[argument_id].ordinary_premises)
            argument_id = (
                f"ARG-I-{inference_id}"
                if len(combinations) == 1
                else f"ARG-I-{inference_id}-{index:03d}"
            )
            arguments[argument_id] = StructuredArgument(
                argument_id,
                str(inference["conclusion"]),
                frozenset(ordinary_premises),
                frozenset(subarguments),
                str(inference_id),
                str(inference["rule_kind"]),
            )
            claim_arguments.setdefault(str(inference["conclusion"]), set()).add(argument_id)

    attacks: set[tuple[str, str]] = set()
    for conflict in schemes.values():
        if conflict.get("kind") != "conflict" or not conflict.get("active", True):
            continue
        sources = claim_arguments.get(str(conflict["source"]), set())
        if conflict["target_type"] == "claim":
            target_claim = str(conflict["target"])
            if conflict["attack_kind"] == "rebut":
                targets = claim_arguments.get(target_claim, set())
            else:  # undermine
                targets = {
                    arg.id for arg in arguments.values() if target_claim in arg.ordinary_premises
                }
        else:  # undercut
            target_roots = {
                arg.id
                for arg in arguments.values()
                if arg.top_inference == str(conflict["target"])
            }
            targets = {
                arg.id
                for arg in arguments.values()
                if arg.id in target_roots or not target_roots.isdisjoint(arg.subarguments)
            }
        attacks.update((source, target) for source in sources for target in targets if source != target)
    return arguments, attacks


def grounded_labels(
    argument_ids: Iterable[str], attacks: Iterable[tuple[str, str]]
) -> dict[str, str]:
    """Compute Dung grounded labels by the least fixed point."""

    arguments = set(argument_ids)
    attack_set = set(attacks)
    attackers = {arg: {src for src, dst in attack_set if dst == arg} for arg in arguments}
    accepted: set[str] = set()
    while True:
        defended = {
            arg
            for arg in arguments
            if all(any((defender, attacker) in attack_set for defender in accepted) for attacker in attackers[arg])
        }
        if defended == accepted:
            break
        accepted = defended
    rejected = {target for source, target in attack_set if source in accepted}
    return {
        arg: "accepted" if arg in accepted else "rejected" if arg in rejected else "undecided"
        for arg in sorted(arguments)
    }


def belnap_status(graph: Mapping[str, Any], atom: str) -> str:
    """Return raw information state, deliberately independent of Dung labels."""

    polarities = {
        node.get("polarity")
        for node in graph.get("information_nodes", [])
        if node.get("kind") == "claim"
        and node.get("atom") == atom
        and node.get("active", True)
        and node.get("information_available", True)
    }
    positive = "positive" in polarities
    negative = "negative" in polarities
    if positive and negative:
        return "BOTH"
    if positive:
        return "TRUE_ONLY"
    if negative:
        return "FALSE_ONLY"
    return "NEITHER"


def recompute_after_invalidation(
    graph: Mapping[str, Any], invalid_claim_ids: Iterable[str], *, event_id: str
) -> dict[str, Any]:
    """TMS-style forward recomputation that preserves the original graph."""

    updated = deepcopy(graph)
    invalid = set(invalid_claim_ids)
    info = _by_id(updated.get("information_nodes", []))
    inferences = [item for item in updated.get("scheme_nodes", []) if item.get("kind") == "inference"]
    active_claims = {
        node_id
        for node_id, node in info.items()
        if node.get("kind") == "claim"
        and node.get("asserted", False)
        and node.get("active", True)
        and node_id not in invalid
    }
    active_inferences: set[str] = set()
    changed = True
    while changed:
        changed = False
        for inference in inferences:
            if inference["id"] in active_inferences or not inference.get("active", True):
                continue
            if set(inference["premises"]) <= active_claims:
                active_inferences.add(str(inference["id"]))
                before = len(active_claims)
                active_claims.add(str(inference["conclusion"]))
                changed = changed or len(active_claims) != before

    for node in updated.get("information_nodes", []):
        if node.get("kind") != "claim":
            continue
        node["active"] = node["id"] in active_claims
        if node["id"] in invalid:
            node.setdefault("provenance", {})["invalidated_by"] = event_id
    for inference in inferences:
        inference["effective"] = inference["id"] in active_inferences
    return {
        "graph": updated,
        "active_claim_ids": sorted(active_claims),
        "active_inference_ids": sorted(active_inferences),
        "invalidated_claim_ids": sorted(invalid),
        "event_id": event_id,
    }
