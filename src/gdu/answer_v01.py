"""Auditable answer assembly for the GDU logic interface laboratory.

This module verbalizes accepted external arguments.  It does not expose or
attempt to store a model's private chain of thought.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from .logic_v01 import compile_structured_arguments, grounded_labels, validate_aif_interface


def _by_id(items: Iterable[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    return {str(item["id"]): item for item in items}


def _select_accepted_argument(arguments, labels, claim_id):
    candidates = [
        argument
        for argument in arguments.values()
        if argument.conclusion == claim_id and labels[argument.id] == "accepted"
    ]
    if not candidates:
        raise ValueError(f"claim has no accepted argument: {claim_id}")
    return min(candidates, key=lambda item: (len(item.ordinary_premises), item.id))


def _proof_for_argument(argument, arguments, schemes):
    steps = []
    visited = set()

    def visit(argument_id):
        if argument_id in visited:
            return
        current = arguments[argument_id]
        for subargument_id in sorted(current.subarguments):
            visit(subargument_id)
        visited.add(argument_id)
        if current.top_inference is None:
            return
        inference = schemes[current.top_inference]
        steps.append(
            {
                "argument_id": current.id,
                "inference_id": current.top_inference,
                "rule_id": inference["rule_id"],
                "rule_kind": current.rule_kind,
                "premise_claim_ids": list(inference["premises"]),
                "conclusion_claim_id": current.conclusion,
            }
        )
    visit(argument.id)
    return steps


def build_answer_package(
    graph: Mapping[str, Any],
    *,
    target_claim_ids: Iterable[str],
    limitation_claim_ids: Iterable[str] = (),
) -> dict[str, Any]:
    """Build an answer only from claims accepted under grounded semantics.

    Query understanding is deliberately outside this boundary: the caller
    supplies target and limitation Claim IDs selected for the question.
    """

    issues = validate_aif_interface(graph)
    if issues:
        raise ValueError([issue.to_dict() for issue in issues])
    info = _by_id(graph.get("information_nodes", []))
    schemes = _by_id(graph.get("scheme_nodes", []))
    arguments, attacks = compile_structured_arguments(graph)
    labels = grounded_labels(arguments, attacks)

    selected = []
    for role, claim_ids in (
        ("conclusion", list(target_claim_ids)),
        ("limitation", list(limitation_claim_ids)),
    ):
        for claim_id in claim_ids:
            claim = info.get(claim_id)
            if claim is None or claim.get("kind") != "claim":
                raise KeyError(f"unknown claim: {claim_id}")
            argument = _select_accepted_argument(arguments, labels, claim_id)
            if not claim.get("statement"):
                raise ValueError(f"answer claim has no statement: {claim_id}")
            selected.append((role, claim, argument))

    premise_claim_ids = sorted(
        {
            premise
            for _, _, argument in selected
            for premise in argument.ordinary_premises
        }
    )
    evidence_ids = sorted(
        {
            evidence_id
            for claim_id in premise_claim_ids
            for evidence_id in info[claim_id].get("provenance", {}).get("quoted_from", [])
        }
    )
    chosen_argument_ids = {argument.id for _, _, argument in selected}
    rejected = sorted(
        {
            argument.conclusion
            for argument in arguments.values()
            if labels[argument.id] == "rejected"
            and argument.conclusion not in {claim["id"] for _, claim, _ in selected}
        }
    )

    return {
        "answer": " ".join(claim["statement"] for _, claim, _ in selected),
        "selected_claims": [
            {
                "role": role,
                "claim_id": claim["id"],
                "argument_id": argument.id,
                "grounded_label": labels[argument.id],
            }
            for role, claim, argument in selected
        ],
        "proof_steps": [
            step
            for _, _, argument in selected
            for step in _proof_for_argument(argument, arguments, schemes)
        ],
        "evidence": [
            {
                "evidence_id": evidence_id,
                "text": info[evidence_id].get("text", ""),
                **info[evidence_id]["provenance"],
            }
            for evidence_id in evidence_ids
        ],
        "rejected_claim_ids": rejected,
        "argument_status": {
            argument_id: labels[argument_id]
            for argument_id in sorted(chosen_argument_ids)
        },
    }
