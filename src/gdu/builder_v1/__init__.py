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
from .representation import (
    EvidenceQuote,
    Quantity,
    RepresentationCandidate,
    RepresentationValidationError,
    SemanticArgument,
    SemanticCue,
    compile_representation_seed,
    make_evidence_quote,
    make_representation_candidate,
    representation_candidate_from_proposal,
    validate_representation_candidates,
)

__all__ = [
    "BLOCK_TYPES",
    "BlockType",
    "DocumentMap",
    "DocumentSection",
    "EvidenceBlock",
    "EvidenceManifest",
    "EvidenceValidationError",
    "EvidenceQuote",
    "PageElement",
    "Quantity",
    "RepresentationCandidate",
    "RepresentationValidationError",
    "SemanticArgument",
    "SemanticCue",
    "build_document_map",
    "compile_representation_seed",
    "evidence_manifest_from_elements",
    "evidence_manifest_from_packet",
    "make_evidence_block",
    "make_evidence_quote",
    "make_representation_candidate",
    "representation_candidate_from_proposal",
    "validate_evidence_manifest",
    "validate_representation_candidates",
]
