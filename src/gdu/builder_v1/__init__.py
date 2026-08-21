"""Builder V1: compile source material into the current GDU logic interface."""

from .document_map import DocumentMap, DocumentSection, build_document_map
from .evidence import (
    BLOCK_TYPES,
    BlockType,
    EvidenceBlock,
    EvidenceRelation,
    EvidenceManifest,
    EvidenceValidationError,
    make_evidence_block,
    TableRegion,
    validate_evidence_manifest,
)
from .source_adapter import (
    EvidenceRelationSpec,
    PageElement,
    evidence_manifest_from_elements,
    evidence_manifest_from_packet,
)
from .representation_eval import score_representation_response
from .representation import (
    ComparisonConstraint,
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
    "ComparisonConstraint",
    "DocumentMap",
    "DocumentSection",
    "EvidenceBlock",
    "EvidenceRelation",
    "EvidenceRelationSpec",
    "EvidenceManifest",
    "EvidenceValidationError",
    "EvidenceQuote",
    "PageElement",
    "Quantity",
    "RepresentationCandidate",
    "RepresentationValidationError",
    "SemanticArgument",
    "SemanticCue",
    "TableRegion",
    "build_document_map",
    "compile_representation_seed",
    "evidence_manifest_from_elements",
    "evidence_manifest_from_packet",
    "make_evidence_block",
    "make_evidence_quote",
    "make_representation_candidate",
    "representation_candidate_from_proposal",
    "score_representation_response",
    "validate_evidence_manifest",
    "validate_representation_candidates",
]
