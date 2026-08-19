from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

from gdu.validator_v0 import validate_file

from .types import TechnicalFailure


class ArtifactWriterValidator:
    """Stage, validate, hash, and atomically publish one GDU package."""

    def __init__(self, gdu_schema: Path, build_log_schema: Path) -> None:
        self.gdu_schema = gdu_schema
        self.build_log_schema = build_log_schema

    def publish(
        self,
        gdu: Mapping[str, Any],
        events: Sequence[Mapping[str, Any]],
        output_dir: Path,
    ) -> tuple[Path, Path, Path]:
        parent = output_dir.parent
        parent.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.stage-", dir=parent))
        try:
            gdu_path = stage / "gdu.json"
            log_path = stage / "build_log.jsonl"
            artifacts_path = stage / "ARTIFACTS.sha256"

            gdu_path.write_text(
                json.dumps(gdu, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            log_path.write_text(
                "".join(
                    json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n"
                    for event in events
                ),
                encoding="utf-8",
            )

            self._validate_log(events, gdu)
            artifacts_path.write_text(
                "".join(
                    f"{self._sha256(path)}  {path.name}\n"
                    for path in (gdu_path, log_path)
                ),
                encoding="utf-8",
            )

            issues, setup_error = validate_file(
                gdu_path,
                self.gdu_schema,
                log_path,
                artifacts_path,
            )
            if setup_error or issues:
                detail = "; ".join(
                    f"{issue.code}@{issue.path}: {issue.message}" for issue in issues
                )
                raise TechnicalFailure(
                    "artifact_validator", detail or "package validation failed"
                )
            if output_dir.exists():
                raise TechnicalFailure(
                    "artifact_writer", "output directory already exists"
                )
            os.replace(stage, output_dir)
            return (
                output_dir / "gdu.json",
                output_dir / "build_log.jsonl",
                output_dir / "ARTIFACTS.sha256",
            )
        except TechnicalFailure:
            raise
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise TechnicalFailure("artifact_writer", str(exc)) from exc
        finally:
            if stage.exists():
                shutil.rmtree(stage)

    def _validate_log(
        self,
        events: Sequence[Mapping[str, Any]],
        gdu: Mapping[str, Any],
    ) -> None:
        try:
            import jsonschema
        except ModuleNotFoundError as exc:
            raise TechnicalFailure(
                "artifact_validator", "jsonschema dependency is missing"
            ) from exc

        schema = json.loads(self.build_log_schema.read_text(encoding="utf-8"))
        validator = jsonschema.Draft202012Validator(
            schema, format_checker=jsonschema.FormatChecker()
        )
        errors = [error for event in events for error in validator.iter_errors(event)]
        if errors:
            raise TechnicalFailure(
                "artifact_validator",
                "invalid build log event: " + errors[0].message,
            )

        ids = [str(event["event_id"]) for event in events]
        times = [int(event["logical_time"]) for event in events]
        if len(ids) != len(set(ids)):
            raise TechnicalFailure("artifact_validator", "duplicate build log event id")
        if times != list(range(1, len(times) + 1)):
            raise TechnicalFailure(
                "artifact_validator", "logical_time must be strictly sequential"
            )

        freezes = [index for index, event in enumerate(events) if event["event_type"] == "freeze"]
        status = gdu["manifest"]["gdu_identity"]["status"]
        if status == "frozen":
            if freezes != [len(events) - 1]:
                raise TechnicalFailure(
                    "artifact_validator", "frozen log requires one final freeze"
                )
        elif freezes:
            raise TechnicalFailure(
                "artifact_validator", "provisional log cannot contain freeze"
            )

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
