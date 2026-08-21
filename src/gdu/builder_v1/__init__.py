"""Builder V1: compile source material into the current GDU logic interface."""

from .document_map import DocumentMap, DocumentSection, build_document_map
from .evidence import (
    BLOCK_TYPES,
    BlockType,
    EvidenceBlock,
    EvidenceManifest,
    EvidenceValidationError,
    make_evidence_block,
    validate_evidence_manifest,
)
from .source_adapter import (
    PageElement,
    evidence_manifest_from_elements,
    evidence_manifest_from_packet,
)

__all__ = [
    "BLOCK_TYPES",
    "BlockType",
    "DocumentMap",
    "DocumentSection",
    "EvidenceBlock",
    "EvidenceManifest",
    "EvidenceValidationError",
    "PageElement",
    "build_document_map",
    "evidence_manifest_from_elements",
    "evidence_manifest_from_packet",
    "make_evidence_block",
    "validate_evidence_manifest",
]
