from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class ValidationIssue:
    """A deterministic semantic validation failure."""

    code: str
    path: str
    message: str


def validate_semantics(gdu: Mapping[str, Any]) -> list[ValidationIssue]:
    """Validate cross-object GDU v0.1 invariants.

    JSON Schema validation must run first. This function assumes the required
    top-level fields and primitive types are present, then checks constraints
    that JSON Schema cannot express reliably: global ID uniqueness, reference
    integrity, evidence requirements, locator bounds, and claim-type usage.
    """

    issues: list[ValidationIssue] = []
    manifest = gdu["manifest"]
    page_count = manifest["source_document"]["page_count"]
    source_units = gdu["source_units"]
    claims = gdu["claims"]
    evidence_links = gdu["evidence_links"]
    document_model = gdu["document_model"]
    sections = document_model["sections"]
    relations = document_model["relations"]
    choices = document_model["document_specific_choices"]
    views = gdu["views"]

    source_by_id = _index(source_units, "source_unit_id")
    claim_by_id = _index(claims, "claim_id")
    evidence_by_id = _index(evidence_links, "evidence_link_id")
    section_by_id = _index(sections, "section_id")
    relation_by_id = _index(relations, "relation_id")
    choice_by_id = _index(choices, "choice_id")
    view_by_id = _index(views, "view_id")

    _check_global_id_uniqueness(
        issues,
        (
            ("source_units", source_units, "source_unit_id"),
            ("claims", claims, "claim_id"),
            ("evidence_links", evidence_links, "evidence_link_id"),
            ("document_model.sections", sections, "section_id"),
            ("document_model.relations", relations, "relation_id"),
            ("document_model.document_specific_choices", choices, "choice_id"),
            ("views", views, "view_id"),
        ),
    )

    for index, unit in enumerate(source_units):
        path = f"source_units[{index}]"
        if unit["page_end"] < unit["page_start"]:
            _add(issues, "invalid_page_range", path, "page_end is before page_start")
        if unit["page_end"] > page_count:
            _add(
                issues,
                "page_out_of_bounds",
                path,
                f"page_end {unit['page_end']} exceeds document page_count {page_count}",
            )
        char_start = unit.get("char_start")
        char_end = unit.get("char_end")
        if char_start is not None and char_end is not None and char_end < char_start:
            _add(issues, "invalid_char_range", path, "char_end is before char_start")

    links_by_claim: dict[str, list[Mapping[str, Any]]] = {}
    for index, link in enumerate(evidence_links):
        path = f"evidence_links[{index}]"
        claim_id = link["claim_id"]
        if claim_id not in claim_by_id:
            _add(issues, "unknown_claim", f"{path}.claim_id", claim_id)
        else:
            links_by_claim.setdefault(claim_id, []).append(link)
        _check_references(
            issues,
            link["source_unit_ids"],
            source_by_id,
            f"{path}.source_unit_ids",
            "unknown_source_unit",
        )

    for index, claim in enumerate(claims):
        path = f"claims[{index}]"
        status = claim["epistemic_status"]
        claim_links = links_by_claim.get(claim["claim_id"], [])
        supporting_links = [link for link in claim_links if link["role"] == "supports"]
        source_grounded_links = [
            link
            for link in supporting_links
            if link["support_mode"] != "genre_prior"
        ]

        if status in {"explicit", "entailed"} and not source_grounded_links:
            _add(
                issues,
                "missing_source_evidence",
                path,
                f"{status} claim requires a non-genre supporting evidence link",
            )
        if claim["claim_type"] == "fact" and not any(
            link["support_mode"] in {"direct", "multi_source_inference"}
            for link in supporting_links
        ):
            _add(
                issues,
                "fact_without_textual_evidence",
                path,
                "fact claim requires direct or multi-source textual evidence",
            )
        if status in {"inferred", "hypothesis"} and not claim["rationale"].strip():
            _add(
                issues,
                "missing_inference_rationale",
                f"{path}.rationale",
                f"{status} claim requires a rationale",
            )
        _check_references(
            issues,
            claim["alternative_claim_ids"],
            claim_by_id,
            f"{path}.alternative_claim_ids",
            "unknown_alternative_claim",
        )
        if claim["claim_id"] in claim["alternative_claim_ids"]:
            _add(
                issues,
                "self_alternative",
                f"{path}.alternative_claim_ids",
                "claim cannot be its own alternative",
            )

    _check_claim_list(
        issues,
        document_model["purpose_claim_ids"],
        claim_by_id,
        "document_model.purpose_claim_ids",
        "purpose",
    )
    _check_claim_list(
        issues,
        document_model["main_idea_claim_ids"],
        claim_by_id,
        "document_model.main_idea_claim_ids",
        "main_idea",
    )
    _check_claim_list(
        issues,
        document_model["constraint_claim_ids"],
        claim_by_id,
        "document_model.constraint_claim_ids",
        "constraint",
    )

    for index, choice in enumerate(choices):
        _check_claim_list(
            issues,
            [choice["claim_id"]],
            claim_by_id,
            f"document_model.document_specific_choices[{index}].claim_id",
            "genre_deviation",
        )

    for index, section in enumerate(sections):
        path = f"document_model.sections[{index}]"
        parent_id = section["parent_section_id"]
        if parent_id is not None and parent_id not in section_by_id:
            _add(issues, "unknown_parent_section", f"{path}.parent_section_id", parent_id)
        if parent_id == section["section_id"]:
            _add(issues, "self_parent_section", f"{path}.parent_section_id", parent_id)
        _check_references(
            issues,
            section["source_unit_ids"],
            source_by_id,
            f"{path}.source_unit_ids",
            "unknown_section_source_unit",
        )
        _check_claim_list(
            issues,
            section["function_claim_ids"],
            claim_by_id,
            f"{path}.function_claim_ids",
            "section_function",
        )
        if section["boundary_origin"] == "inferred" and not section[
            "boundary_rationale"
        ].strip():
            _add(
                issues,
                "missing_boundary_rationale",
                f"{path}.boundary_rationale",
                "inferred section boundary requires a rationale",
            )

    _check_section_parent_cycles(issues, section_by_id)

    relation_endpoints = {**claim_by_id, **section_by_id}
    for index, relation in enumerate(relations):
        path = f"document_model.relations[{index}]"
        _check_references(
            issues,
            [relation["source_id"], relation["target_id"]],
            relation_endpoints,
            path,
            "unknown_relation_endpoint",
        )
        if relation["source_id"] == relation["target_id"]:
            _add(issues, "self_relation", path, "relation endpoints must differ")
        relation_claim = claim_by_id.get(relation["claim_id"])
        if relation_claim is None:
            _add(
                issues,
                "unknown_relation_claim",
                f"{path}.claim_id",
                relation["claim_id"],
            )
        elif relation_claim["claim_type"] != "relation":
            _add(
                issues,
                "wrong_claim_type",
                f"{path}.claim_id",
                "relation edge must reference a relation claim",
            )

    all_referable_ids = {
        **source_by_id,
        **claim_by_id,
        **evidence_by_id,
        **section_by_id,
        **relation_by_id,
        **choice_by_id,
    }
    for index, view in enumerate(views):
        _check_references(
            issues,
            view["derived_from_ids"],
            all_referable_ids,
            f"views[{index}].derived_from_ids",
            "unknown_view_input",
        )

    return sorted(issues, key=lambda issue: (issue.path, issue.code, issue.message))


def _index(items: Iterable[Mapping[str, Any]], id_field: str) -> dict[str, Mapping[str, Any]]:
    return {item[id_field]: item for item in items}


def _check_global_id_uniqueness(
    issues: list[ValidationIssue],
    collections: Iterable[tuple[str, Iterable[Mapping[str, Any]], str]],
) -> None:
    seen: dict[str, str] = {}
    for collection_path, items, id_field in collections:
        for index, item in enumerate(items):
            identifier = item[id_field]
            path = f"{collection_path}[{index}].{id_field}"
            if identifier in seen:
                _add(
                    issues,
                    "duplicate_id",
                    path,
                    f"{identifier} already used at {seen[identifier]}",
                )
            else:
                seen[identifier] = path


def _check_references(
    issues: list[ValidationIssue],
    identifiers: Iterable[str],
    index: Mapping[str, Any],
    path: str,
    code: str,
) -> None:
    for identifier in identifiers:
        if identifier not in index:
            _add(issues, code, path, identifier)


def _check_claim_list(
    issues: list[ValidationIssue],
    identifiers: Iterable[str],
    claim_by_id: Mapping[str, Mapping[str, Any]],
    path: str,
    expected_type: str,
) -> None:
    for identifier in identifiers:
        claim = claim_by_id.get(identifier)
        if claim is None:
            _add(issues, "unknown_claim", path, identifier)
        elif claim["claim_type"] != expected_type:
            _add(
                issues,
                "wrong_claim_type",
                path,
                f"{identifier} is {claim['claim_type']}, expected {expected_type}",
            )


def _check_section_parent_cycles(
    issues: list[ValidationIssue],
    section_by_id: Mapping[str, Mapping[str, Any]],
) -> None:
    for section_id in section_by_id:
        path: list[str] = []
        current: str | None = section_id
        while current is not None and current in section_by_id:
            if current in path:
                cycle = path[path.index(current) :] + [current]
                _add(
                    issues,
                    "section_parent_cycle",
                    "document_model.sections",
                    " -> ".join(cycle),
                )
                break
            path.append(current)
            current = section_by_id[current]["parent_section_id"]


def _add(
    issues: list[ValidationIssue], code: str, path: str, message: str
) -> None:
    issue = ValidationIssue(code=code, path=path, message=message)
    if issue not in issues:
        issues.append(issue)
