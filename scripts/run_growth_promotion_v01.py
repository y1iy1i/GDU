#!/usr/bin/env python3
"""Promote a quarantined query-growth candidate into a versioned GDU graph."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from gdu.growth_v01 import promote_growth_candidate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--event-id", required=True)
    parser.add_argument("--recorded-at", required=True)
    args = parser.parse_args()

    base = json.loads(args.base.read_text(encoding="utf-8"))
    candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
    grown = promote_growth_candidate(
        base,
        candidate,
        event_id=args.event_id,
        recorded_at=args.recorded_at,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(grown, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "format": grown["format"],
                "information_nodes": len(grown["information_nodes"]),
                "scheme_nodes": len(grown["scheme_nodes"]),
                "event_id": args.event_id,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
