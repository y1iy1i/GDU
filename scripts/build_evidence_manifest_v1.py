from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gdu.builder_v0.source_reader import PypdfBackend, SourceReader  # noqa: E402
from gdu.builder_v0.types import SourceRequest  # noqa: E402
from gdu.builder_v1 import (  # noqa: E402
    build_document_map,
    evidence_manifest_from_packet,
)


def parse_page_ranges(value: str, page_count: int) -> tuple[tuple[int, int], ...]:
    if value.strip().lower() == "all":
        return ((1, page_count),)
    ranges: list[tuple[int, int]] = []
    for part in value.split(","):
        token = part.strip()
        if not token:
            raise ValueError("page range contains an empty item")
        if "-" in token:
            start_text, end_text = token.split("-", 1)
            start, end = int(start_text), int(end_text)
        else:
            start = end = int(token)
        if start < 1 or end < start or end > page_count:
            raise ValueError(f"page range {token!r} is outside 1-{page_count}")
        ranges.append((start, end))
    if not ranges:
        raise ValueError("at least one physical page is required")
    return tuple(ranges)


def write_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build deterministic Builder V1 evidence and document-map artifacts."
    )
    parser.add_argument("--source-pdf", type=Path, required=True)
    parser.add_argument("--document-id", required=True)
    parser.add_argument("--pages", default="all", help="Physical pages, e.g. 1-3,7")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--map-output", type=Path, required=True)
    parser.add_argument("--expected-source-sha256")
    args = parser.parse_args()

    reader = SourceReader(
        args.source_pdf,
        args.document_id,
        PypdfBackend(),
        expected_source_sha256=args.expected_source_sha256,
    )
    identity = reader.inspect()
    ranges = parse_page_ranges(args.pages, identity.pdf_page_count)
    packet = reader.read(SourceRequest("Builder V1 evidence extraction", ranges))
    manifest = evidence_manifest_from_packet(identity, packet)
    document_map = build_document_map(manifest)

    manifest_value = manifest.as_dict()
    manifest_value["manifest_hash"] = manifest.manifest_hash
    map_value = document_map.as_dict()
    map_value["map_hash"] = document_map.map_hash
    write_json(args.output, manifest_value)
    write_json(args.map_output, map_value)

    print(f"DOCUMENT {identity.document_id}")
    print(f"SOURCE_SHA256 {identity.source_sha256}")
    print(f"PDF_PAGES {identity.pdf_page_count}")
    print(f"EVIDENCE_BLOCKS {len(manifest.blocks)}")
    print(f"DOCUMENT_MAP_MODE {document_map.map_mode}")
    print(f"MANIFEST_HASH {manifest.manifest_hash}")
    print(f"MAP_HASH {document_map.map_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
