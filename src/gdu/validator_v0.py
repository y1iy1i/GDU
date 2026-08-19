from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


DEFAULT_SCHEMA = Path(__file__).resolve().parents[2] / "gdu.schema.json"
SHA256_LINE = re.compile(r"^([a-f0-9]{64})  (.+)$")


@dataclass(frozen=True)
class ValidationIssue:
    """A deterministic validation failure with a stable machine-readable code."""

    code: str
    path: str
    message: str


def validate_schema(
    gdu: Mapping[str, Any], schema: Mapping[str, Any]
) -> list[ValidationIssue]:
    """Validate one GDU against the frozen JSON Schema candidate."""

    try:
        import jsonschema
    except ModuleNotFoundError:
        return [
            ValidationIssue(
                code="schema_dependency_missing",
                path="$",
                message=(
                    "Python package 'jsonschema' is required; install "
                    "requirements-validator.txt in the active environment"
                ),
            )
        ]

    try:
        jsonschema.Draft202012Validator.check_schema(schema)
    except jsonschema.SchemaError as exc:
        return [
            ValidationIssue(
                code="invalid_schema",
                path="$schema",
                message=exc.message,
            )
        ]

    validator = jsonschema.Draft202012Validator(
        schema,
        format_checker=jsonschema.FormatChecker(),
    )
    issues = [
        ValidationIssue(
            code="schema_validation",
            path=_json_path(error.absolute_path),
            message=error.message,
        )
        for error in validator.iter_errors(gdu)
    ]
    return sorted(issues, key=_issue_key)


def validate_semantics(gdu: Mapping[str, Any]) -> list[ValidationIssue]:
    """Check v0 invariants that JSON Schema cannot express reliably.

    This function assumes Schema validation already passed. It checks only
    mechanical integrity; it does not judge truth, evidence sufficiency,
    semantic-unit quality, relation correctness, or Plan faithfulness.
    """

    issues: list[ValidationIssue] = []
    page_count = gdu["manifest"]["source_identity"]["pdf_page_count"]

    physical_items = gdu["physical_structure"]
    unit_items = gdu["semantic_units"]
    assertion_items = gdu["assertions"]["items"]
    group_items = gdu["assertions"]["interpretation_groups"]
    relation_items = gdu["relations"]
    evidence_items = gdu["evidence"]

    physical = _index(issues, physical_items, "physical_structure")
    units = _index(issues, unit_items, "semantic_units")
    assertions = _index(issues, assertion_items, "assertions.items")
    groups = _index(
        issues,
        group_items,
        "assertions.interpretation_groups",
    )
    relations = _index(issues, relation_items, "relations")
    evidence = _index(issues, evidence_items, "evidence")

    _check_global_id_uniqueness(
        issues,
        (
            ("physical_structure", physical_items),
            ("semantic_units", unit_items),
            ("assertions.items", assertion_items),
            ("assertions.interpretation_groups", group_items),
            ("relations", relation_items),
            ("evidence", evidence_items),
        ),
    )

    _check_physical_structure(issues, physical_items, physical, evidence, page_count)
    _check_semantic_units(issues, unit_items, physical, assertions, evidence)
    _check_assertions(issues, assertion_items, units, assertions, evidence)
    _check_interpretation_groups(issues, group_items, assertions)
    _check_relations(issues, relation_items, units, assertions, evidence)
    _check_plan(issues, gdu["generative_plan"], units, assertions, groups, relations)
    _check_evidence(issues, evidence_items, page_count)

    return sorted(set(issues), key=_issue_key)


def validate_freeze_package(
    gdu_path: Path,
    gdu: Mapping[str, Any],
    build_log_path: Path | None,
    artifacts_path: Path | None,
) -> list[ValidationIssue]:
    """Validate the external pieces required for a frozen GDU package."""

    issues: list[ValidationIssue] = []
    is_frozen = gdu["manifest"]["gdu_identity"]["status"] == "frozen"

    if is_frozen and build_log_path is None:
        _add(
            issues,
            "missing_build_log",
            "$package.build_log",
            "frozen GDU requires --build-log",
        )
    if is_frozen and artifacts_path is None:
        _add(
            issues,
            "missing_artifacts_manifest",
            "$package.artifacts",
            "frozen GDU requires --artifacts",
        )
    if (build_log_path is None) != (artifacts_path is None):
        _add(
            issues,
            "incomplete_freeze_inputs",
            "$package",
            "--build-log and --artifacts must be provided together",
        )
    if build_log_path is None or artifacts_path is None:
        return sorted(set(issues), key=_issue_key)

    issues.extend(_check_build_log(build_log_path, require_freeze=is_frozen))
    issues.extend(
        _check_artifacts_manifest(
            artifacts_path,
            required_files=(gdu_path, build_log_path),
        )
    )
    return sorted(set(issues), key=_issue_key)


def validate_file(
    gdu_path: Path,
    schema_path: Path = DEFAULT_SCHEMA,
    build_log_path: Path | None = None,
    artifacts_path: Path | None = None,
) -> tuple[list[ValidationIssue], bool]:
    """Load and validate a GDU file.

    Returns (issues, setup_error). setup_error distinguishes tool/I/O failures
    (CLI exit 2) from an invalid GDU (CLI exit 1).
    """

    try:
        gdu = _load_json(gdu_path)
        schema = _load_json(schema_path)
    except (OSError, json.JSONDecodeError) as exc:
        return [ValidationIssue("input_error", "$", str(exc))], True

    schema_issues = validate_schema(gdu, schema)
    if any(
        issue.code in {"schema_dependency_missing", "invalid_schema"}
        for issue in schema_issues
    ):
        return schema_issues, True
    if schema_issues:
        return schema_issues, False

    issues = validate_semantics(gdu)
    issues.extend(
        validate_freeze_package(
            gdu_path=gdu_path,
            gdu=gdu,
            build_log_path=build_log_path,
            artifacts_path=artifacts_path,
        )
    )
    return sorted(set(issues), key=_issue_key), False


def _check_physical_structure(
    issues: list[ValidationIssue],
    items: Sequence[Mapping[str, Any]],
    physical: Mapping[str, Mapping[str, Any]],
    evidence: Mapping[str, Mapping[str, Any]],
    page_count: int,
) -> None:
    roots = [item["id"] for item in items if item["parent_ref"] is None]
    if len(roots) != 1:
        _add(
            issues,
            "physical_root_count",
            "physical_structure",
            f"expected exactly one root, found {len(roots)}",
        )

    sibling_orders: dict[tuple[str | None, int], str] = {}
    for index, node in enumerate(items):
        path = f"physical_structure[{index}]"
        node_id = node["id"]
        parent_ref = node["parent_ref"]
        start = node["page_range"]["start"]
        end = node["page_range"]["end"]

        if parent_ref is not None and parent_ref not in physical:
            _add(issues, "unknown_physical_parent", f"{path}.parent_ref", parent_ref)
        if end < start:
            _add(issues, "invalid_page_range", f"{path}.page_range", f"{start}-{end}")
        if end > page_count:
            _add(
                issues,
                "page_out_of_bounds",
                f"{path}.page_range.end",
                f"{end} exceeds PDF page count {page_count}",
            )
        if parent_ref in physical:
            parent_range = physical[parent_ref]["page_range"]
            if start < parent_range["start"] or end > parent_range["end"]:
                _add(
                    issues,
                    "child_range_outside_parent",
                    f"{path}.page_range",
                    f"{start}-{end} is outside parent {parent_ref}",
                )

        key = (parent_ref, node["order"])
        if key in sibling_orders:
            _add(
                issues,
                "duplicate_sibling_order",
                f"{path}.order",
                f"same parent and order as {sibling_orders[key]}",
            )
        else:
            sibling_orders[key] = node_id

        _check_refs(
            issues,
            node["evidence_refs"],
            evidence,
            f"{path}.evidence_refs",
            "unknown_evidence",
        )

    for node_id in physical:
        chain: list[str] = []
        current: str | None = node_id
        while current is not None and current in physical:
            if current in chain:
                cycle = chain[chain.index(current) :] + [current]
                _add(
                    issues,
                    "physical_parent_cycle",
                    "physical_structure",
                    " -> ".join(cycle),
                )
                break
            chain.append(current)
            current = physical[current]["parent_ref"]


def _check_semantic_units(
    issues: list[ValidationIssue],
    items: Sequence[Mapping[str, Any]],
    physical: Mapping[str, Mapping[str, Any]],
    assertions: Mapping[str, Mapping[str, Any]],
    evidence: Mapping[str, Mapping[str, Any]],
) -> None:
    ranked_functions: dict[str, str] = {}
    for index, unit in enumerate(items):
        path = f"semantic_units[{index}]"
        unit_id = unit["id"]
        _check_refs(
            issues,
            unit["physical_structure_refs"],
            physical,
            f"{path}.physical_structure_refs",
            "unknown_physical_node",
        )
        _check_refs(
            issues,
            unit["evidence_refs"],
            evidence,
            f"{path}.evidence_refs",
            "unknown_evidence",
        )

        function_refs = [
            unit["primary_function_ref"],
            *unit["secondary_function_refs"],
        ]
        if len(function_refs) != len(set(function_refs)):
            _add(
                issues,
                "duplicate_function_rank",
                path,
                "primary and secondary function references must be distinct",
            )
        for function_ref in function_refs:
            assertion = assertions.get(function_ref)
            if assertion is None:
                _add(
                    issues,
                    "unknown_function_assertion",
                    path,
                    function_ref,
                )
                continue
            if assertion["kind"] != "function":
                _add(
                    issues,
                    "wrong_function_kind",
                    path,
                    f"{function_ref} has kind {assertion['kind']}",
                )
            if assertion.get("semantic_unit_refs") != [unit_id]:
                _add(
                    issues,
                    "function_back_reference_mismatch",
                    path,
                    f"{function_ref} must target only {unit_id}",
                )
            previous_unit = ranked_functions.get(function_ref)
            if previous_unit is not None and previous_unit != unit_id:
                _add(
                    issues,
                    "function_ranked_by_multiple_units",
                    path,
                    f"{function_ref} already ranked by {previous_unit}",
                )
            ranked_functions[function_ref] = unit_id

    for assertion_id, assertion in assertions.items():
        if assertion["kind"] == "function" and assertion_id not in ranked_functions:
            _add(
                issues,
                "unranked_function_assertion",
                "assertions.items",
                assertion_id,
            )


def _check_assertions(
    issues: list[ValidationIssue],
    items: Sequence[Mapping[str, Any]],
    units: Mapping[str, Mapping[str, Any]],
    assertions: Mapping[str, Mapping[str, Any]],
    evidence: Mapping[str, Mapping[str, Any]],
) -> None:
    for index, assertion in enumerate(items):
        path = f"assertions.items[{index}]"
        assertion_id = assertion["id"]
        _check_refs(
            issues,
            assertion.get("semantic_unit_refs", []),
            units,
            f"{path}.semantic_unit_refs",
            "unknown_semantic_unit",
        )
        _check_refs(
            issues,
            assertion["evidence_refs"],
            evidence,
            f"{path}.evidence_refs",
            "unknown_evidence",
        )
        for field in ("input_assertion_refs", "basis_assertion_refs"):
            refs = assertion.get(field, [])
            _check_refs(
                issues,
                refs,
                assertions,
                f"{path}.{field}",
                "unknown_assertion",
            )
            if assertion_id in refs:
                _add(
                    issues,
                    "self_assertion_reference",
                    f"{path}.{field}",
                    assertion_id,
                )


def _check_interpretation_groups(
    issues: list[ValidationIssue],
    items: Sequence[Mapping[str, Any]],
    assertions: Mapping[str, Mapping[str, Any]],
) -> None:
    for index, group in enumerate(items):
        path = f"assertions.interpretation_groups[{index}]"
        _check_refs(
            issues,
            group["member_refs"],
            assertions,
            f"{path}.member_refs",
            "unknown_interpretation_member",
        )
        preferred_ref = group.get("preferred_ref")
        if preferred_ref is not None and preferred_ref not in group["member_refs"]:
            _add(
                issues,
                "preferred_not_member",
                f"{path}.preferred_ref",
                preferred_ref,
            )


def _check_relations(
    issues: list[ValidationIssue],
    items: Sequence[Mapping[str, Any]],
    units: Mapping[str, Mapping[str, Any]],
    assertions: Mapping[str, Mapping[str, Any]],
    evidence: Mapping[str, Mapping[str, Any]],
) -> None:
    symmetric_seen: dict[tuple[str, frozenset[str]], str] = {}
    for index, relation in enumerate(items):
        path = f"relations[{index}]"
        relation_id = relation["id"]
        endpoints = units if relation["endpoint_level"] == "semantic_unit" else assertions

        _check_refs(
            issues,
            [relation["from_ref"], relation["to_ref"]],
            endpoints,
            path,
            "unknown_relation_endpoint",
        )
        if relation["from_ref"] == relation["to_ref"]:
            _add(issues, "self_relation", path, relation["from_ref"])
        _check_refs(
            issues,
            relation["evidence_refs"],
            evidence,
            f"{path}.evidence_refs",
            "unknown_evidence",
        )
        _check_refs(
            issues,
            relation.get("basis_assertion_refs", []),
            assertions,
            f"{path}.basis_assertion_refs",
            "unknown_assertion",
        )

        if relation["relation_type"] in {"conflicts_with", "alternative_to"}:
            key = (
                relation["relation_type"],
                frozenset((relation["from_ref"], relation["to_ref"])),
            )
            if key in symmetric_seen:
                _add(
                    issues,
                    "duplicate_symmetric_relation",
                    path,
                    f"duplicates {symmetric_seen[key]}",
                )
            else:
                symmetric_seen[key] = relation_id


def _check_plan(
    issues: list[ValidationIssue],
    plan: Mapping[str, Mapping[str, Any]],
    units: Mapping[str, Mapping[str, Any]],
    assertions: Mapping[str, Mapping[str, Any]],
    groups: Mapping[str, Mapping[str, Any]],
    relations: Mapping[str, Mapping[str, Any]],
) -> None:
    targets = {
        "assertion_refs": (assertions, "unknown_assertion"),
        "semantic_unit_refs": (units, "unknown_semantic_unit"),
        "relation_refs": (relations, "unknown_relation"),
        "interpretation_group_refs": (groups, "unknown_interpretation_group"),
    }
    for section_name, section in plan.items():
        for field, (target, code) in targets.items():
            _check_refs(
                issues,
                section[field],
                target,
                f"generative_plan.{section_name}.{field}",
                code,
            )


def _check_evidence(
    issues: list[ValidationIssue],
    items: Sequence[Mapping[str, Any]],
    page_count: int,
) -> None:
    for evidence_index, item in enumerate(items):
        for fragment_index, fragment in enumerate(item["fragments"]):
            path = f"evidence[{evidence_index}].fragments[{fragment_index}]"
            if fragment["page"] > page_count:
                _add(
                    issues,
                    "evidence_page_out_of_bounds",
                    f"{path}.page",
                    f"{fragment['page']} exceeds PDF page count {page_count}",
                )
            actual_hash = hashlib.sha256(
                fragment["excerpt"].encode("utf-8")
            ).hexdigest()
            if actual_hash != fragment["fragment_sha256"]:
                _add(
                    issues,
                    "fragment_hash_mismatch",
                    f"{path}.fragment_sha256",
                    f"expected {actual_hash}",
                )
            bbox = fragment.get("bbox")
            if bbox is not None:
                if bbox["x2"] < bbox["x1"] or bbox["y2"] < bbox["y1"]:
                    _add(issues, "invalid_bbox", f"{path}.bbox", "x2/y2 precede x1/y1")
                if bbox["coordinate_space"] == "normalized_0_1" and any(
                    bbox[key] > 1 for key in ("x1", "y1", "x2", "y2")
                ):
                    _add(
                        issues,
                        "normalized_bbox_out_of_bounds",
                        f"{path}.bbox",
                        "normalized coordinates must be between 0 and 1",
                    )


def _check_build_log(
    path: Path, *, require_freeze: bool
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return [ValidationIssue("build_log_read_error", "$package.build_log", str(exc))]

    event_count = 0
    has_freeze = False
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        event_count += 1
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            _add(
                issues,
                "invalid_build_log_jsonl",
                f"$package.build_log:{line_number}",
                exc.msg,
            )
            continue
        if not isinstance(event, dict):
            _add(
                issues,
                "invalid_build_log_event",
                f"$package.build_log:{line_number}",
                "event must be a JSON object",
            )
            continue
        if event.get("event_type") == "freeze":
            has_freeze = True

    if event_count == 0:
        _add(issues, "empty_build_log", "$package.build_log", "no JSONL events")
    if require_freeze and not has_freeze:
        _add(
            issues,
            "missing_freeze_event",
            "$package.build_log",
            "no event_type=freeze event found",
        )
    return issues


def _check_artifacts_manifest(
    path: Path,
    required_files: Sequence[Path],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return [ValidationIssue("artifacts_read_error", "$package.artifacts", str(exc))]

    base = path.parent.resolve()
    manifest_resolved = path.resolve()
    listed: dict[Path, int] = {}
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        match = SHA256_LINE.fullmatch(line)
        line_path = f"$package.artifacts:{line_number}"
        if match is None:
            _add(
                issues,
                "invalid_artifact_line",
                line_path,
                "expected: <64 lowercase hex><two spaces><relative path>",
            )
            continue
        expected_hash, relative_name = match.groups()
        relative_path = Path(relative_name)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            _add(
                issues,
                "unsafe_artifact_path",
                line_path,
                relative_name,
            )
            continue
        target = (base / relative_path).resolve()
        if target == manifest_resolved:
            _add(
                issues,
                "artifacts_self_reference",
                line_path,
                relative_name,
            )
            continue
        if not target.is_relative_to(base):
            _add(issues, "unsafe_artifact_path", line_path, relative_name)
            continue
        if target in listed:
            _add(
                issues,
                "duplicate_artifact_entry",
                line_path,
                f"already listed on line {listed[target]}",
            )
            continue
        listed[target] = line_number
        try:
            actual_hash = _sha256_file(target)
        except OSError as exc:
            _add(issues, "artifact_read_error", line_path, str(exc))
            continue
        if actual_hash != expected_hash:
            _add(
                issues,
                "artifact_hash_mismatch",
                line_path,
                f"{relative_name}: expected {expected_hash}, got {actual_hash}",
            )

    for required in required_files:
        resolved = required.resolve()
        if resolved not in listed:
            _add(
                issues,
                "required_artifact_not_listed",
                "$package.artifacts",
                str(required),
            )
    return issues


def _index(
    issues: list[ValidationIssue],
    items: Sequence[Mapping[str, Any]],
    path: str,
) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for index, item in enumerate(items):
        identifier = item["id"]
        if identifier in result:
            _add(
                issues,
                "duplicate_id",
                f"{path}[{index}].id",
                identifier,
            )
        else:
            result[identifier] = item
    return result


def _check_global_id_uniqueness(
    issues: list[ValidationIssue],
    collections: Iterable[tuple[str, Sequence[Mapping[str, Any]]]],
) -> None:
    seen: dict[str, str] = {}
    for collection_path, items in collections:
        for index, item in enumerate(items):
            identifier = item["id"]
            current_path = f"{collection_path}[{index}].id"
            if identifier in seen:
                _add(
                    issues,
                    "duplicate_id",
                    current_path,
                    f"{identifier} already used at {seen[identifier]}",
                )
            else:
                seen[identifier] = current_path


def _check_refs(
    issues: list[ValidationIssue],
    refs: Iterable[str],
    target: Mapping[str, Any],
    path: str,
    code: str,
) -> None:
    for ref in refs:
        if ref not in target:
            _add(issues, code, path, ref)


def _add(
    issues: list[ValidationIssue], code: str, path: str, message: str
) -> None:
    issue = ValidationIssue(code=code, path=path, message=message)
    if issue not in issues:
        issues.append(issue)


def _json_path(parts: Iterable[Any]) -> str:
    path = "$"
    for part in parts:
        path += f"[{part}]" if isinstance(part, int) else f".{part}"
    return path


def _issue_key(issue: ValidationIssue) -> tuple[str, str, str]:
    return issue.path, issue.code, issue.message


def _load_json(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise json.JSONDecodeError("top-level JSON must be an object", "", 0)
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate a GDU v0 JSON file without calling any model or API."
    )
    parser.add_argument("gdu", type=Path, help="path to gdu.json")
    parser.add_argument(
        "--schema",
        type=Path,
        default=DEFAULT_SCHEMA,
        help=f"Schema path (default: {DEFAULT_SCHEMA})",
    )
    parser.add_argument(
        "--build-log",
        type=Path,
        help="build_log.jsonl; required when manifest status is frozen",
    )
    parser.add_argument(
        "--artifacts",
        type=Path,
        help="ARTIFACTS.sha256; required when manifest status is frozen",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    issues, setup_error = validate_file(
        gdu_path=args.gdu,
        schema_path=args.schema,
        build_log_path=args.build_log,
        artifacts_path=args.artifacts,
    )
    if not issues:
        print(f"VALID: {args.gdu}")
        return 0

    label = "TOOL ERROR" if setup_error else "INVALID"
    print(f"{label}: {args.gdu} ({len(issues)} issue(s))", file=sys.stderr)
    for issue in issues:
        print(
            f"- [{issue.code}] {issue.path}: {issue.message}",
            file=sys.stderr,
        )
    return 2 if setup_error else 1


if __name__ == "__main__":
    raise SystemExit(main())
