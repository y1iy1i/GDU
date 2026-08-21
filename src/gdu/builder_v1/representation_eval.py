"""Blind scoring for isolated Representation Candidate proposals."""

from __future__ import annotations

from collections import Counter
from typing import Any, Mapping, Sequence

from .evidence import EvidenceManifest
from .representation import (
    RepresentationValidationError,
    representation_candidate_from_proposal,
    validate_representation_candidates,
)


def _quantity_signature(items: Sequence[Mapping[str, Any]]) -> list[tuple[str, str | None]]:
    return sorted(
        (str(item.get("normalized_value", "")), item.get("unit")) for item in items
    )


def _constraint_signature(
    items: Sequence[Mapping[str, Any]],
) -> list[tuple[str, str, str | None]]:
    return sorted(
        (
            str(item.get("operator", "")),
            str(item.get("threshold", "")),
            item.get("unit"),
        )
        for item in items
    )


def _problem_family(error: str) -> str:
    if "number_" in error or "quantity_" in error:
        return "quantity_fidelity"
    if "comparison_" in error:
        return "comparison_scope"
    if "context_" in error:
        return "context_scope"
    if "evidence_" in error or "quote_" in error:
        return "evidence_grounding"
    if "polarity" in error or "negation" in error:
        return "polarity_scope"
    if "epistemic" in error or "possible_" in error:
        return "epistemic_modality"
    if "normative" in error:
        return "normative_modality"
    if "attribution" in error:
        return "attribution_scope"
    if "atom_" in error or "semantic_" in error:
        return "atomic_structure"
    return "candidate_contract"


def score_representation_response(
    *,
    manifests: Mapping[str, EvidenceManifest],
    response: Mapping[str, Any],
    gold: Mapping[str, Any],
    compiler_id: str,
) -> dict[str, Any]:
    """Score only after model generation; gold is not part of the request contract."""

    response_cases = response.get("cases")
    if not isinstance(response_cases, list):
        raise RepresentationValidationError(["response_cases_missing"])
    response_by_id: dict[str, Mapping[str, Any]] = {}
    for item in response_cases:
        if not isinstance(item, Mapping) or not isinstance(item.get("case_id"), str):
            raise RepresentationValidationError(["response_case_shape_invalid"])
        case_id = str(item["case_id"])
        if case_id in response_by_id:
            raise RepresentationValidationError([f"response_case_collision:{case_id}"])
        response_by_id[case_id] = item

    results: list[dict[str, Any]] = []
    totals = Counter()
    family_counts = Counter()
    for gold_case in gold.get("cases", []):
        case_id = str(gold_case["case_id"])
        manifest = manifests[case_id]
        response_case = response_by_id.get(case_id, {})
        proposals = response_case.get("proposals", [])
        if not isinstance(proposals, list):
            proposals = []
        gold_by_atom = {str(item["atom"]): item for item in gold_case["claims"]}
        parsed_by_atom: dict[str, Any] = {}
        invalid: list[dict[str, Any]] = []
        duplicate_atoms: list[str] = []
        for index, proposal in enumerate(proposals):
            totals["submitted"] += 1
            try:
                if not isinstance(proposal, Mapping):
                    raise RepresentationValidationError(["proposal_not_object"])
                candidate = representation_candidate_from_proposal(
                    proposal, compiler_id=compiler_id
                )
                errors = validate_representation_candidates(manifest, [candidate])
                if errors:
                    raise RepresentationValidationError(errors)
                if candidate.atom in parsed_by_atom:
                    duplicate_atoms.append(candidate.atom)
                    family_counts["atomic_structure"] += 1
                    continue
                parsed_by_atom[candidate.atom] = candidate
                totals["valid"] += 1
            except RepresentationValidationError as exc:
                families = sorted({_problem_family(error) for error in exc.errors})
                family_counts.update(families)
                invalid.append(
                    {"proposal_index": index, "errors": list(exc.errors), "families": families}
                )

        correct: list[str] = []
        field_mismatches: dict[str, list[str]] = {}
        unexpected = sorted(set(parsed_by_atom) - set(gold_by_atom))
        totals["unexpected"] += len(unexpected)
        for atom in sorted(set(parsed_by_atom) & set(gold_by_atom)):
            candidate = parsed_by_atom[atom]
            expected = gold_by_atom[atom]
            mismatches: list[str] = []
            for field in ("polarity", "epistemic_status", "normative_force"):
                if getattr(candidate, field) != expected[field]:
                    mismatches.append(field)
                    family_counts[
                        {
                            "polarity": "polarity_scope",
                            "epistemic_status": "epistemic_modality",
                            "normative_force": "normative_modality",
                        }[field]
                    ] += 1
            if dict(candidate.context) != expected["context"]:
                mismatches.append("context")
                family_counts["context_scope"] += 1
            actual_quantities = _quantity_signature(
                [item.as_dict() for item in candidate.quantities]
            )
            if actual_quantities != _quantity_signature(expected.get("quantities", [])):
                mismatches.append("quantities")
                family_counts["quantity_fidelity"] += 1
            actual_constraints = _constraint_signature(
                [item.as_dict() for item in candidate.comparison_constraints]
            )
            if actual_constraints != _constraint_signature(
                expected.get("comparison_constraints", [])
            ):
                mismatches.append("comparison_constraints")
                family_counts["comparison_scope"] += 1
            if mismatches:
                field_mismatches[atom] = mismatches
            else:
                correct.append(atom)

        missing = sorted(set(gold_by_atom) - set(correct))
        totals["gold"] += len(gold_by_atom)
        totals["correct"] += len(correct)
        results.append(
            {
                "case_id": case_id,
                "submitted": len(proposals),
                "valid_atoms": sorted(parsed_by_atom),
                "correct_atoms": correct,
                "missing_or_incorrect_atoms": missing,
                "unexpected_atoms": unexpected,
                "duplicate_atoms": sorted(set(duplicate_atoms)),
                "field_mismatches": field_mismatches,
                "invalid_proposals": invalid,
            }
        )

    submitted = totals["submitted"]
    gold_count = totals["gold"]
    return {
        "cases": results,
        "summary": {
            "submitted_candidates": submitted,
            "valid_candidates": totals["valid"],
            "gold_claims": gold_count,
            "exact_correct_claims": totals["correct"],
            "exact_precision": totals["correct"] / submitted if submitted else 0.0,
            "exact_recall": totals["correct"] / gold_count if gold_count else 0.0,
            "validator_acceptance_rate": totals["valid"] / submitted if submitted else 0.0,
            "unexpected_atoms": totals["unexpected"],
            "problem_family_counts": dict(sorted(family_counts.items())),
        },
    }
