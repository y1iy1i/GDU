from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from .types import BuilderRunSpec, SourceRequest


class ConfigError(ValueError):
    """A reproducible-run configuration is missing, unsafe, or inconsistent."""


@dataclass(frozen=True)
class LoadedBuilderConfig:
    config_path: Path
    spec: BuilderRunSpec
    run_timestamp: str
    document_id: str
    fixture_gdu_path: Path
    fixture_gdu_sha256: str
    strict_source_fragments: bool


def load_builder_config(
    config_path: Path,
    schema_path: Path | None = None,
) -> LoadedBuilderConfig:
    config_path = config_path.resolve()
    schema_path = schema_path or (
        Path(__file__).resolve().parents[3] / "builder-run-v0.schema.json"
    )
    raw = _load_json(config_path, "builder run configuration")
    schema = _load_json(schema_path, "builder run configuration schema")
    _validate_json(raw, schema, "builder run configuration")
    _validate_timestamp(raw["run_timestamp"])

    base = config_path.parent
    source = raw["source"]
    contracts = raw["contracts"]
    adapter = raw["adapter"]
    identity = raw["model_identity"]
    limits = raw["limits"]

    resolved = {
        "source_pdf": _resolve_safe(base, source["pdf"]),
        "extracted_text": _resolve_safe(base, source["extracted_text"]),
        "gdu_schema": _resolve_safe(base, contracts["gdu_schema"]),
        "build_log_schema": _resolve_safe(base, contracts["build_log_schema"]),
        "protocol_path": _resolve_safe(base, contracts["protocol"]),
        "fixture_gdu": _resolve_safe(base, adapter["fixture_gdu"]),
    }
    output_dir = _resolve_safe(base, raw["output_dir"])

    expected_hashes = (
        (resolved["source_pdf"], source["pdf_sha256"]),
        (resolved["extracted_text"], source["extracted_text_sha256"]),
        (resolved["gdu_schema"], contracts["gdu_schema_sha256"]),
        (resolved["build_log_schema"], contracts["build_log_schema_sha256"]),
        (resolved["protocol_path"], contracts["protocol_sha256"]),
        (resolved["fixture_gdu"], adapter["fixture_gdu_sha256"]),
    )
    for path, expected in expected_hashes:
        _verify_file(path, expected)

    fixture = _load_json(resolved["fixture_gdu"], "fixture GDU")
    gdu_schema = _load_json(resolved["gdu_schema"], "GDU schema")
    _validate_json(fixture, gdu_schema, "fixture GDU")
    fixture_document_id = (
        fixture.get("manifest", {})
        .get("source_identity", {})
        .get("document_id")
    )
    if fixture_document_id != source["document_id"]:
        raise ConfigError(
            "fixture GDU document_id does not match configured source document_id"
        )

    source_requests = {
        checkpoint: _source_request(value)
        for checkpoint, value in raw["checkpoint_source_requests"].items()
    }
    spec = BuilderRunSpec(
        run_id=raw["run_id"],
        source_pdf=resolved["source_pdf"],
        extracted_text=resolved["extracted_text"],
        gdu_schema=resolved["gdu_schema"],
        gdu_schema_sha256=contracts["gdu_schema_sha256"],
        build_log_schema=resolved["build_log_schema"],
        build_log_schema_sha256=contracts["build_log_schema_sha256"],
        protocol_path=resolved["protocol_path"],
        protocol_name=contracts["protocol_name"],
        protocol_version=contracts["protocol_version"],
        protocol_sha256=contracts["protocol_sha256"],
        config_or_prompt_sha256=identity["config_or_prompt_sha256"],
        model_id=identity["model_id"],
        reasoning_effort=identity["reasoning_effort"],
        output_dir=output_dir,
        expected_source_sha256=source["pdf_sha256"],
        expected_extracted_text_sha256=source["extracted_text_sha256"],
        expected_extraction_system=source["extraction_system"],
        checkpoint_source_requests=source_requests,
        max_semantic_corrections=limits["max_semantic_corrections"],
        max_technical_retries=limits["max_technical_retries"],
        single_builder=limits["single_builder"],
        external_knowledge_allowed=limits["external_knowledge_allowed"],
    )
    return LoadedBuilderConfig(
        config_path=config_path,
        spec=spec,
        run_timestamp=raw["run_timestamp"],
        document_id=source["document_id"],
        fixture_gdu_path=resolved["fixture_gdu"],
        fixture_gdu_sha256=adapter["fixture_gdu_sha256"],
        strict_source_fragments=adapter["strict_source_fragments"],
    )


def _source_request(value: Mapping[str, Any]) -> SourceRequest:
    ranges = tuple((item["start"], item["end"]) for item in value["page_ranges"])
    for start, end in ranges:
        if end < start:
            raise ConfigError(f"source page range ends before it starts: {start}-{end}")
    return SourceRequest(
        purpose=value["purpose"],
        page_ranges=ranges,
        modalities=tuple(value["modalities"]),
        locator_hints=tuple(value["locator_hints"]),
    )


def _validate_timestamp(value: str) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ConfigError(f"invalid run_timestamp: {value}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ConfigError("run_timestamp must include an explicit timezone")


def _resolve_safe(base: Path, relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ConfigError(f"unsafe path in configuration: {relative}")
    resolved = (base / candidate).resolve()
    if not resolved.is_relative_to(base.resolve()):
        raise ConfigError(f"path escapes configuration directory: {relative}")
    return resolved


def _verify_file(path: Path, expected_sha256: str) -> None:
    if not path.is_file():
        raise ConfigError(f"configured file does not exist: {path}")
    actual = _sha256(path)
    if actual != expected_sha256:
        raise ConfigError(f"configured file hash mismatch: {path}")


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ConfigError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise ConfigError(f"{label} must be a JSON object")
    return value


def _validate_json(
    instance: Mapping[str, Any], schema: Mapping[str, Any], label: str
) -> None:
    try:
        import jsonschema
    except ModuleNotFoundError as exc:
        raise ConfigError("jsonschema is required to load Builder configurations") from exc
    validator = jsonschema.Draft202012Validator(
        schema, format_checker=jsonschema.FormatChecker()
    )
    errors = sorted(validator.iter_errors(instance), key=lambda error: list(error.path))
    if errors:
        first = errors[0]
        location = ".".join(str(part) for part in first.absolute_path) or "$"
        raise ConfigError(f"invalid {label} at {location}: {first.message}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
