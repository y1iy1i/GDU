"""Minimal structural map derived only from typed Evidence Blocks."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .evidence import EvidenceManifest, require_valid_evidence_manifest


@dataclass(frozen=True)
class DocumentSection:
    section_id: str
    title: str
    section_kind: str
    heading_block_id: str | None
    start_page: int
    end_page: int
    member_block_ids: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "section_id": self.section_id,
            "title": self.title,
            "section_kind": self.section_kind,
            "heading_block_id": self.heading_block_id,
            "start_page": self.start_page,
            "end_page": self.end_page,
            "member_block_ids": list(self.member_block_ids),
        }


@dataclass(frozen=True)
class DocumentMap:
    format: str
    document_id: str
    source_hash: str
    map_mode: str
    sections: tuple[DocumentSection, ...]
    block_type_counts: tuple[tuple[str, int], ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "format": self.format,
            "document_id": self.document_id,
            "source_hash": self.source_hash,
            "map_mode": self.map_mode,
            "sections": [section.as_dict() for section in self.sections],
            "block_type_counts": dict(self.block_type_counts),
        }

    @property
    def map_hash(self) -> str:
        payload = json.dumps(
            self.as_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _explicit_sections(manifest: EvidenceManifest) -> tuple[DocumentSection, ...]:
    blocks = list(manifest.blocks)
    heading_indexes = [index for index, block in enumerate(blocks) if block.block_type == "heading"]
    sections: list[DocumentSection] = []
    if heading_indexes and heading_indexes[0] > 0:
        members = blocks[: heading_indexes[0]]
        sections.append(
            DocumentSection(
                section_id="SEC-000-PREFACE",
                title="Document preface",
                section_kind="implicit_preface",
                heading_block_id=None,
                start_page=members[0].physical_page,
                end_page=members[-1].physical_page,
                member_block_ids=tuple(block.block_id for block in members),
            )
        )
    for ordinal, start in enumerate(heading_indexes, 1):
        end = heading_indexes[ordinal] if ordinal < len(heading_indexes) else len(blocks)
        members = blocks[start:end]
        heading = members[0]
        sections.append(
            DocumentSection(
                section_id=f"SEC-{ordinal:03d}-{heading.block_hash[:10]}",
                title=heading.text,
                section_kind="explicit_heading",
                heading_block_id=heading.block_id,
                start_page=members[0].physical_page,
                end_page=members[-1].physical_page,
                member_block_ids=tuple(block.block_id for block in members),
            )
        )
    return tuple(sections)


def build_document_map(manifest: EvidenceManifest) -> DocumentMap:
    """Create a conservative map; it does not infer headings from plain page text."""

    require_valid_evidence_manifest(manifest)
    type_counts: dict[str, int] = {}
    for block in manifest.blocks:
        type_counts[block.block_type] = type_counts.get(block.block_type, 0) + 1

    if any(block.block_type == "heading" for block in manifest.blocks):
        mode = "heading_aware"
        sections = _explicit_sections(manifest)
    else:
        mode = "page_only"
        sections = (
            DocumentSection(
                section_id="SEC-000-DOCUMENT",
                title=manifest.original_filename,
                section_kind="implicit_document",
                heading_block_id=None,
                start_page=manifest.blocks[0].physical_page,
                end_page=manifest.blocks[-1].physical_page,
                member_block_ids=tuple(block.block_id for block in manifest.blocks),
            ),
        )
    return DocumentMap(
        format="gdu-document-map-v1",
        document_id=manifest.document_id,
        source_hash=manifest.source_hash,
        map_mode=mode,
        sections=sections,
        block_type_counts=tuple(sorted(type_counts.items())),
    )
