"""Deterministic, page-addressable evidence interface for Builder V1."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from typing import Any, Literal, Mapping, Sequence


BlockType = Literal[
    "page_text",
    "heading",
    "paragraph",
    "table",
    "figure",
    "algorithm",
    "footnote",
    "other",
]
BLOCK_TYPES: frozenset[str] = frozenset(
    {
        "page_text",
        "heading",
        "paragraph",
        "table",
        "figure",
        "algorithm",
        "footnote",
        "other",
    }
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class EvidenceValidationError(ValueError):
    """The evidence manifest cannot safely enter Builder V1."""

    def __init__(self, errors: Sequence[str]) -> None:
        self.errors = tuple(sorted(set(errors)))
        super().__init__(list(self.errors))


def normalize_evidence_text(value: str) -> str:
    """Normalize layout whitespace without changing signs, punctuation, or values."""

    return re.sub(r"\s+", " ", value).strip()


def _canonical_hash(value: Mapping[str, Any]) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _block_hash_payload(
    *,
    document_id: str,
    physical_page: int,
    sequence: int,
    block_type: str,
    text: str,
    source_locator: str,
    source_hash: str,
    bbox: tuple[float, float, float, float] | None,
) -> dict[str, Any]:
    return {
        "document_id": document_id,
        "physical_page": physical_page,
        "sequence": sequence,
        "block_type": block_type,
        "text": text,
        "source_locator": source_locator,
        "source_hash": source_hash,
        "bbox": list(bbox) if bbox is not None else None,
    }


def _slug(value: str) -> str:
    slug = re.sub(r"[^0-9a-z]+", "-", value.lower()).strip("-")
    return slug[:32] or "document"


@dataclass(frozen=True)
class EvidenceBlock:
    block_id: str
    document_id: str
    physical_page: int
    sequence: int
    block_type: BlockType
    text: str
    source_locator: str
    source_hash: str
    block_hash: str
    extraction_system: str
    bbox: tuple[float, float, float, float] | None = None

    def as_dict(self) -> dict[str, Any]:
        value: dict[str, Any] = {
            "block_id": self.block_id,
            "document_id": self.document_id,
            "physical_page": self.physical_page,
            "sequence": self.sequence,
            "block_type": self.block_type,
            "text": self.text,
            "source_locator": self.source_locator,
            "source_hash": self.source_hash,
            "block_hash": self.block_hash,
            "extraction_system": self.extraction_system,
        }
        if self.bbox is not None:
            value["bbox"] = list(self.bbox)
        return value


@dataclass(frozen=True)
class EvidenceManifest:
    format: str
    document_id: str
    original_filename: str
    source_hash: str
    physical_page_count: int
    extraction_system: str
    blocks: tuple[EvidenceBlock, ...]
    extraction_notes: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "format": self.format,
            "document_id": self.document_id,
            "original_filename": self.original_filename,
            "source_hash": self.source_hash,
            "physical_page_count": self.physical_page_count,
            "extraction_system": self.extraction_system,
            "blocks": [block.as_dict() for block in self.blocks],
            "extraction_notes": list(self.extraction_notes),
        }

    @property
    def manifest_hash(self) -> str:
        return _canonical_hash(self.as_dict())


def make_evidence_block(
    *,
    document_id: str,
    physical_page: int,
    sequence: int,
    block_type: BlockType,
    text: str,
    source_locator: str,
    source_hash: str,
    extraction_system: str,
    bbox: tuple[float, float, float, float] | None = None,
) -> EvidenceBlock:
    normalized = normalize_evidence_text(text)
    payload = _block_hash_payload(
        document_id=document_id,
        physical_page=physical_page,
        sequence=sequence,
        block_type=block_type,
        text=normalized,
        source_locator=source_locator,
        source_hash=source_hash,
        bbox=bbox,
    )
    block_hash = _canonical_hash(payload)
    block_id = (
        f"EB-{_slug(document_id)}-{physical_page:04d}-{sequence:03d}-{block_hash[:12]}"
    )
    return EvidenceBlock(
        block_id=block_id,
        document_id=document_id,
        physical_page=physical_page,
        sequence=sequence,
        block_type=block_type,
        text=normalized,
        source_locator=source_locator,
        source_hash=source_hash,
        block_hash=block_hash,
        extraction_system=extraction_system.strip(),
        bbox=bbox,
    )


def validate_evidence_manifest(manifest: EvidenceManifest) -> list[str]:
    """Return deterministic validation errors; an empty list means valid."""

    errors: list[str] = []
    if manifest.format != "gdu-evidence-manifest-v1":
        errors.append("manifest_format_invalid")
    if not manifest.document_id.strip():
        errors.append("document_id_missing")
    if not manifest.original_filename.strip():
        errors.append("original_filename_missing")
    if not _SHA256.fullmatch(manifest.source_hash):
        errors.append("source_hash_invalid")
    if manifest.physical_page_count < 1:
        errors.append("physical_page_count_invalid")
    if not manifest.extraction_system.strip():
        errors.append("extraction_system_missing")
    if not manifest.blocks:
        errors.append("manifest_blocks_missing")

    block_ids: list[str] = []
    locators: list[str] = []
    page_sequences: list[tuple[int, int]] = []
    for block in manifest.blocks:
        location = f"block:{block.block_id or '<missing>'}"
        block_ids.append(block.block_id)
        locators.append(block.source_locator)
        page_sequences.append((block.physical_page, block.sequence))
        if block.document_id != manifest.document_id:
            errors.append(f"{location}:document_id_mismatch")
        if block.source_hash != manifest.source_hash:
            errors.append(f"{location}:source_hash_mismatch")
        if block.physical_page < 1 or block.physical_page > manifest.physical_page_count:
            errors.append(f"{location}:physical_page_out_of_range")
        if block.sequence < 1:
            errors.append(f"{location}:sequence_invalid")
        if block.block_type not in BLOCK_TYPES:
            errors.append(f"{location}:block_type_invalid")
        if not block.text or block.text != normalize_evidence_text(block.text):
            errors.append(f"{location}:text_not_normalized")
        if not block.source_locator.strip():
            errors.append(f"{location}:source_locator_missing")
        if not block.extraction_system.strip():
            errors.append(f"{location}:extraction_system_missing")
        elif block.extraction_system != manifest.extraction_system:
            errors.append(f"{location}:extraction_system_mismatch")
        if block.bbox is not None:
            numeric = all(
                isinstance(value, (int, float)) and not isinstance(value, bool)
                for value in block.bbox
            )
            if len(block.bbox) != 4 or not numeric:
                errors.append(f"{location}:bbox_invalid")
            else:
                x0, y0, x1, y1 = block.bbox
                if (
                    not all(math.isfinite(value) for value in block.bbox)
                    or min(block.bbox) < 0
                    or x0 > x1
                    or y0 > y1
                ):
                    errors.append(f"{location}:bbox_invalid")
        expected_hash = _canonical_hash(
            _block_hash_payload(
                document_id=block.document_id,
                physical_page=block.physical_page,
                sequence=block.sequence,
                block_type=block.block_type,
                text=block.text,
                source_locator=block.source_locator,
                source_hash=block.source_hash,
                bbox=block.bbox,
            )
        )
        if block.block_hash != expected_hash:
            errors.append(f"{location}:block_hash_mismatch")
        expected_id = (
            f"EB-{_slug(block.document_id)}-{block.physical_page:04d}-"
            f"{block.sequence:03d}-{expected_hash[:12]}"
        )
        if block.block_id != expected_id:
            errors.append(f"{location}:block_id_mismatch")

    for name, values in (
        ("block_id_collision", block_ids),
        ("source_locator_collision", locators),
        ("page_sequence_collision", page_sequences),
    ):
        if len(values) != len(set(values)):
            errors.append(name)
    if list(manifest.blocks) != sorted(
        manifest.blocks, key=lambda item: (item.physical_page, item.sequence, item.block_id)
    ):
        errors.append("blocks_not_in_physical_order")
    return sorted(set(errors))


def require_valid_evidence_manifest(manifest: EvidenceManifest) -> EvidenceManifest:
    errors = validate_evidence_manifest(manifest)
    if errors:
        raise EvidenceValidationError(errors)
    return manifest
