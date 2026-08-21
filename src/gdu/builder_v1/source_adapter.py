"""Adapters from page-aware parser output to Builder V1 evidence manifests."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Iterable

from gdu.builder_v0.types import SourceDocumentIdentity, SourcePacket

from .evidence import (
    BLOCK_TYPES,
    BlockType,
    EvidenceRelation,
    EvidenceRelationKind,
    EvidenceManifest,
    EvidenceValidationError,
    make_evidence_block,
    normalize_evidence_text,
    require_valid_evidence_manifest,
    TableRegion,
)


@dataclass(frozen=True)
class PageElement:
    physical_page: int
    text: str
    block_type: BlockType = "paragraph"
    source_locator: str | None = None
    bbox: tuple[float, float, float, float] | None = None
    table_region: TableRegion | None = None


@dataclass(frozen=True)
class EvidenceRelationSpec:
    """Relate parser elements by their stable source locators."""

    source_locator: str
    target_locator: str
    relation: EvidenceRelationKind


def evidence_manifest_from_elements(
    identity: SourceDocumentIdentity,
    elements: Iterable[PageElement],
    *,
    extraction_notes: Iterable[str] = (),
    relation_specs: Iterable[EvidenceRelationSpec] = (),
) -> EvidenceManifest:
    """Compile typed parser elements without treating them as final knowledge units."""

    indexed = list(enumerate(elements))
    indexed.sort(key=lambda item: (item[1].physical_page, item[0]))
    page_sequences: dict[int, int] = {}
    blocks = []
    errors: list[str] = []
    for _, element in indexed:
        page_sequences[element.physical_page] = page_sequences.get(element.physical_page, 0) + 1
        sequence = page_sequences[element.physical_page]
        if element.block_type not in BLOCK_TYPES:
            errors.append(f"element:{element.physical_page}:{sequence}:block_type_invalid")
            continue
        if not normalize_evidence_text(element.text):
            errors.append(f"element:{element.physical_page}:{sequence}:text_missing")
            continue
        locator = element.source_locator or (
            f"{identity.original_filename}#physical-page={element.physical_page}"
            f"&element={sequence}"
        )
        blocks.append(
            make_evidence_block(
                document_id=identity.document_id,
                physical_page=element.physical_page,
                sequence=sequence,
                block_type=element.block_type,
                text=element.text,
                source_locator=locator,
                source_hash=identity.source_sha256,
                extraction_system=identity.extraction_system,
                bbox=element.bbox,
                table_region=element.table_region,
            )
        )
    if errors:
        raise EvidenceValidationError(errors)
    blocks_by_locator = {block.source_locator: block for block in blocks}
    relations: list[EvidenceRelation] = []
    for spec in relation_specs:
        source = blocks_by_locator.get(spec.source_locator)
        target = blocks_by_locator.get(spec.target_locator)
        if source is None:
            errors.append(f"relation_source_locator_unknown:{spec.source_locator}")
        if target is None:
            errors.append(f"relation_target_locator_unknown:{spec.target_locator}")
        if source is not None and target is not None:
            relations.append(
                EvidenceRelation(source.block_id, target.block_id, spec.relation)
            )
    if errors:
        raise EvidenceValidationError(errors)
    manifest = EvidenceManifest(
        format="gdu-evidence-manifest-v1",
        document_id=identity.document_id,
        original_filename=identity.original_filename,
        source_hash=identity.source_sha256,
        physical_page_count=identity.pdf_page_count,
        extraction_system=identity.extraction_system,
        blocks=tuple(blocks),
        extraction_notes=tuple(str(note) for note in extraction_notes),
        relations=tuple(relations),
    )
    return require_valid_evidence_manifest(manifest)


def evidence_manifest_from_packet(
    identity: SourceDocumentIdentity,
    packet: SourcePacket,
) -> EvidenceManifest:
    """Upgrade a verified v0 SourcePacket to the V1 evidence contract."""

    errors: list[str] = []
    if packet.source_document_id != identity.document_id:
        errors.append("source_packet_document_id_mismatch")
    elements: list[PageElement] = []
    for fragment in packet.pdf_fragments:
        normalized = normalize_evidence_text(fragment.excerpt)
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        if digest != fragment.fragment_sha256:
            errors.append(f"physical_page:{fragment.page}:fragment_hash_mismatch")
        elements.append(
            PageElement(
                physical_page=fragment.page,
                text=normalized,
                block_type="page_text",
                source_locator=fragment.locator,
            )
        )
    if errors:
        raise EvidenceValidationError(errors)
    notes = list(packet.retrieval_notes)
    if packet.navigation_text:
        notes.append(
            "Navigation-only text was excluded from authoritative Evidence Blocks."
        )
    return evidence_manifest_from_elements(identity, elements, extraction_notes=notes)
