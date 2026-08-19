from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from .types import CandidateBundle, CandidateObject, CandidateValidationError


PREFIXES = {
    "physical_structure": "PS",
    "semantic_unit": "U",
    "assertion": "A",
    "interpretation_group": "IG",
    "relation": "R",
    "evidence": "E",
}


class CanonicalIdAllocator:
    """Allocate deterministic IDs and resolve bundle-local @handles."""

    def __init__(self) -> None:
        self._counts = {kind: 0 for kind in PREFIXES}

    def canonicalize(
        self, bundle: CandidateBundle
    ) -> list[tuple[str, dict[str, Any]]]:
        # Work on a copy so an invalid bundle cannot consume IDs.
        next_counts = dict(self._counts)
        local: dict[str, str] = {}
        for candidate in bundle.objects:
            self._validate_candidate(candidate, local)
            if candidate.kind == "evidence" and candidate.source_authority != "pdf":
                raise CandidateValidationError(
                    "navigation-only material cannot be promoted as evidence"
                )
            next_counts[candidate.kind] += 1
            local[candidate.handle] = (
                f"{PREFIXES[candidate.kind]}-{next_counts[candidate.kind]:03d}"
            )

        canonical: list[tuple[str, dict[str, Any]]] = []
        for candidate in bundle.objects:
            fields = self._resolve(deepcopy(dict(candidate.fields)), local)
            if "id" in fields:
                raise CandidateValidationError("adapter cannot provide a canonical id")
            fields["id"] = local[candidate.handle]
            canonical.append((candidate.kind, fields))
        self._counts = next_counts
        return canonical

    @staticmethod
    def _validate_candidate(
        candidate: CandidateObject, already_seen: Mapping[str, str]
    ) -> None:
        if not candidate.handle or candidate.handle.startswith("@"):
            raise CandidateValidationError("candidate handle must be a plain non-empty name")
        if candidate.handle in already_seen:
            raise CandidateValidationError(
                f"duplicate bundle-local handle: {candidate.handle}"
            )

    def _resolve(self, value: Any, local: Mapping[str, str]) -> Any:
        if isinstance(value, str) and value.startswith("@"):
            handle = value[1:]
            if handle not in local:
                raise CandidateValidationError(f"unknown bundle-local handle: {handle}")
            return local[handle]
        if isinstance(value, list):
            return [self._resolve(item, local) for item in value]
        if isinstance(value, tuple):
            return [self._resolve(item, local) for item in value]
        if isinstance(value, dict):
            return {key: self._resolve(item, local) for key, item in value.items()}
        return value
