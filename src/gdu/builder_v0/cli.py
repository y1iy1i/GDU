from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Sequence

from .config import ConfigError, load_builder_config
from .fixture_adapter import GduFixtureAdapter
from .orchestrator import BuilderOrchestrator
from .source_reader import PypdfBackend, SourceReader
from .types import TechnicalFailure


class ConfiguredClock:
    def __init__(self, timestamp: str) -> None:
        self.timestamp = timestamp

    def now(self) -> str:
        return self.timestamp


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.command != "run":
        parser.error("a command is required")

    try:
        loaded = load_builder_config(args.config)
        spec = loaded.spec
        if args.output_dir is not None:
            spec = replace(spec, output_dir=args.output_dir.resolve())
        fixture = json.loads(loaded.fixture_gdu_path.read_text(encoding="utf-8"))
        backend = PypdfBackend()
        reader = SourceReader(
            spec.source_pdf,
            loaded.document_id,
            backend,
            expected_source_sha256=spec.expected_source_sha256,
        )
        adapter = GduFixtureAdapter(
            fixture,
            spec.immutable_run_identity,
            strict_source_fragments=loaded.strict_source_fragments,
        )
        result = BuilderOrchestrator(
            spec=spec,
            adapter=adapter,
            clock=ConfiguredClock(loaded.run_timestamp),
            source_reader=reader,
        ).build()
    except (
        ConfigError,
        TechnicalFailure,
        OSError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        _print_json(
            {
                "outcome": "setup_failed",
                "error": str(exc),
                "artifact_paths": [],
            },
            stream=sys.stderr,
        )
        return 2

    _print_json(
        {
            "outcome": result.outcome,
            "final_checkpoint": result.final_checkpoint,
            "semantic_corrections_used": result.semantic_corrections_used,
            "technical_retries_used": result.technical_retries_used,
            "artifact_paths": [str(path) for path in result.artifact_paths],
            "summary": result.public_summary,
        },
        stream=sys.stdout if result.outcome == "frozen_complete" else sys.stderr,
    )
    return 0 if result.outcome == "frozen_complete" else 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gdu-builder-v0",
        description="Run the deterministic GDU Builder v0 fixture pipeline.",
    )
    subparsers = parser.add_subparsers(dest="command")
    run = subparsers.add_parser("run", help="run one preregistered Builder job")
    run.add_argument(
        "--config",
        type=Path,
        required=True,
        help="path to a builder-run-v0 JSON configuration",
    )
    run.add_argument(
        "--output-dir",
        type=Path,
        help="explicit one-run output override; the directory must not exist",
    )
    return parser


def _print_json(value: object, stream: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2), file=stream)


if __name__ == "__main__":
    raise SystemExit(main())
