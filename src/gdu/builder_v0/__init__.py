"""Deterministic GDU Builder v0 skeleton and reproducible fixture runner."""

from .config import ConfigError, LoadedBuilderConfig, load_builder_config
from .fixture_adapter import GduFixtureAdapter
from .orchestrator import BuilderOrchestrator
from .types import (
    AdapterStageResult,
    BuilderRunResult,
    BuilderRunSpec,
    CandidateBundle,
    CandidateObject,
    CorrectionRequest,
    Gap,
    ObjectMutation,
    PdfPageFragment,
    SourceDocumentIdentity,
    SourcePacket,
    SourceRequest,
    RevisionRecord,
    StopGateResult,
    TechnicalFailure,
)

__all__ = [
    "AdapterStageResult",
    "BuilderOrchestrator",
    "BuilderRunResult",
    "BuilderRunSpec",
    "CandidateBundle",
    "CandidateObject",
    "ConfigError",
    "CorrectionRequest",
    "Gap",
    "GduFixtureAdapter",
    "LoadedBuilderConfig",
    "ObjectMutation",
    "PdfPageFragment",
    "SourceDocumentIdentity",
    "SourcePacket",
    "SourceRequest",
    "RevisionRecord",
    "StopGateResult",
    "TechnicalFailure",
    "load_builder_config",
]
