"""Candidate contract between Evidence Blocks and the GDU representation layer."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable, Literal, Mapping, Sequence

from gdu.logic_v01 import validate_aif_interface

from .evidence import (
    EvidenceBlock,
    EvidenceManifest,
    normalize_evidence_text,
    require_valid_evidence_manifest,
)


Polarity = Literal["positive", "negative"]
EpistemicStatus = Literal["certain", "possible"]
NormativeForce = Literal[
    "none", "obligation", "prohibition", "permission", "recommendation"
]
CueKind = Literal["negation", "epistemic", "normative", "condition", "attribution"]

POLARITIES = frozenset({"positive", "negative"})
EPISTEMIC_STATUSES = frozenset({"certain", "possible"})
NORMATIVE_FORCES = frozenset(
    {"none", "obligation", "prohibition", "permission", "recommendation"}
)
CUE_KINDS = frozenset(
    {"negation", "epistemic", "normative", "condition", "attribution"}
)
_ATOM = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
_ROLE = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
_NUMBER = re.compile(r"(?<![\d.,])[-+]?\d[\d,]*(?:\.\d+)?%?(?![\d.,])")


class RepresentationValidationError(ValueError):
    """Representation candidates cannot safely enter the GDU seed graph."""

    def __init__(self, errors: Sequence[str]) -> None:
        self.errors = tuple(sorted(set(errors)))
        super().__init__(list(self.errors))


def _canonical_hash(value: Mapping[str, Any]) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _slug(value: str) -> str:
    slug = re.sub(r"[^0-9a-z]+", "-", value.lower()).strip("-")
    return slug[:36] or "claim"


@dataclass(frozen=True)
class SemanticArgument:
    role: str
    value: str

    def as_dict(self) -> dict[str, str]:
        return {"role": self.role, "value": self.value}


@dataclass(frozen=True)
class EvidenceQuote:
    block_id: str
    quote: str
    quote_hash: str

    def as_dict(self) -> dict[str, str]:
        return {
            "block_id": self.block_id,
            "quote": self.quote,
            "quote_hash": self.quote_hash,
        }


@dataclass(frozen=True)
class SemanticCue:
    kind: CueKind
    text: str

    def as_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "text": self.text}


@dataclass(frozen=True)
class Quantity:
    surface: str
    normalized_value: str
    unit: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        return {
            "surface": self.surface,
            "normalized_value": self.normalized_value,
            "unit": self.unit,
        }


@dataclass(frozen=True)
class RepresentationCandidate:
    candidate_id: str
    statement: str
    atom: str
    semantic_arguments: tuple[SemanticArgument, ...]
    polarity: Polarity
    epistemic_status: EpistemicStatus
    normative_force: NormativeForce
    context: Mapping[str, Any]
    evidence_quotes: tuple[EvidenceQuote, ...]
    semantic_cues: tuple[SemanticCue, ...]
    quantities: tuple[Quantity, ...]
    attribution: str | None
    compiler_id: str
    candidate_hash: str

    def content_dict(self) -> dict[str, Any]:
        return {
            "statement": self.statement,
            "atom": self.atom,
            "semantic_arguments": [item.as_dict() for item in self.semantic_arguments],
            "polarity": self.polarity,
            "epistemic_status": self.epistemic_status,
            "normative_force": self.normative_force,
            "context": self.context,
            "evidence_quotes": [item.as_dict() for item in self.evidence_quotes],
            "semantic_cues": [item.as_dict() for item in self.semantic_cues],
            "quantities": [item.as_dict() for item in self.quantities],
            "attribution": self.attribution,
            "compiler_id": self.compiler_id,
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            **self.content_dict(),
            "candidate_hash": self.candidate_hash,
        }


def make_evidence_quote(block_id: str, quote: str) -> EvidenceQuote:
    normalized = normalize_evidence_text(quote)
    return EvidenceQuote(
        block_id=block_id,
        quote=normalized,
        quote_hash=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
    )


def make_representation_candidate(
    *,
    statement: str,
    atom: str,
    semantic_arguments: Iterable[SemanticArgument],
    polarity: Polarity,
    context: Mapping[str, Any],
    evidence_quotes: Iterable[EvidenceQuote],
    compiler_id: str,
    epistemic_status: EpistemicStatus = "certain",
    normative_force: NormativeForce = "none",
    semantic_cues: Iterable[SemanticCue] = (),
    quantities: Iterable[Quantity] = (),
    attribution: str | None = None,
) -> RepresentationCandidate:
    candidate = RepresentationCandidate(
        candidate_id="",
        statement=normalize_evidence_text(statement),
        atom=atom.strip(),
        semantic_arguments=tuple(semantic_arguments),
        polarity=polarity,
        epistemic_status=epistemic_status,
        normative_force=normative_force,
        context=dict(context),
        evidence_quotes=tuple(evidence_quotes),
        semantic_cues=tuple(semantic_cues),
        quantities=tuple(quantities),
        attribution=normalize_evidence_text(attribution) if attribution else None,
        compiler_id=compiler_id.strip(),
        candidate_hash="",
    )
    digest = _canonical_hash(candidate.content_dict())
    return RepresentationCandidate(
        **{
            **candidate.__dict__,
            "candidate_id": f"C-{_slug(candidate.atom)}-{digest[:12]}",
            "candidate_hash": digest,
        }
    )


def representation_candidate_from_proposal(
    value: Mapping[str, Any], *, compiler_id: str
) -> RepresentationCandidate:
    """Parse an untrusted model proposal; identity and hashes are computed locally."""

    expected = {
        "statement",
        "atom",
        "semantic_arguments",
        "polarity",
        "context",
        "evidence_quotes",
        "epistemic_status",
        "normative_force",
        "semantic_cues",
        "quantities",
        "attribution",
    }
    unknown = sorted(set(value) - expected)
    if unknown:
        raise RepresentationValidationError(
            [f"proposal_unknown_field:{field}" for field in unknown]
        )
    try:
        arguments = tuple(
            SemanticArgument(role=str(item["role"]), value=str(item["value"]))
            for item in value["semantic_arguments"]
        )
        quotes = tuple(
            make_evidence_quote(str(item["block_id"]), str(item["quote"]))
            for item in value["evidence_quotes"]
        )
        cues = tuple(
            SemanticCue(kind=str(item["kind"]), text=str(item["text"]))
            for item in value.get("semantic_cues", [])
        )
        quantities = tuple(
            Quantity(
                surface=str(item["surface"]),
                normalized_value=str(item["normalized_value"]),
                unit=str(item["unit"]) if item.get("unit") is not None else None,
            )
            for item in value.get("quantities", [])
        )
        context = value["context"]
        if not isinstance(context, Mapping):
            raise TypeError("context must be an object")
        attribution_value = value.get("attribution")
        return make_representation_candidate(
            statement=str(value["statement"]),
            atom=str(value["atom"]),
            semantic_arguments=arguments,
            polarity=str(value["polarity"]),
            epistemic_status=str(value.get("epistemic_status", "certain")),
            normative_force=str(value.get("normative_force", "none")),
            context=context,
            evidence_quotes=quotes,
            semantic_cues=cues,
            quantities=quantities,
            attribution=str(attribution_value) if attribution_value is not None else None,
            compiler_id=compiler_id,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise RepresentationValidationError(
            [f"proposal_shape_invalid:{type(exc).__name__}"]
        ) from exc


def _validate_context(value: Mapping[str, Any], location: str) -> list[str]:
    errors: list[str] = []
    if not value:
        return [f"{location}:context_missing"]
    for key, item in value.items():
        if not isinstance(key, str) or not key.strip():
            errors.append(f"{location}:context_key_invalid")
            continue
        if item is None or item == "":
            errors.append(f"{location}:context_value_missing:{key}")
        if isinstance(item, Mapping):
            item_type = item.get("type")
            if item_type == "interval":
                try:
                    start = date.fromisoformat(str(item["start"]))
                    end = date.fromisoformat(str(item["end"]))
                    if start > end:
                        raise ValueError
                except (KeyError, TypeError, ValueError):
                    errors.append(f"{location}:context_interval_invalid:{key}")
            elif item_type == "set":
                values = item.get("values")
                if not isinstance(values, list) or not values:
                    errors.append(f"{location}:context_set_invalid:{key}")
            else:
                errors.append(f"{location}:context_mapping_type_invalid:{key}")
        elif not isinstance(item, (str, int, float, bool)):
            errors.append(f"{location}:context_value_invalid:{key}")
    try:
        json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError):
        errors.append(f"{location}:context_not_canonical_json")
    return errors


def validate_representation_candidates(
    manifest: EvidenceManifest,
    candidates: Sequence[RepresentationCandidate],
) -> list[str]:
    """Validate model-proposed claims without deciding whether they are true."""

    require_valid_evidence_manifest(manifest)
    errors: list[str] = []
    blocks = {block.block_id: block for block in manifest.blocks}
    candidate_ids: list[str] = []
    for candidate in candidates:
        location = f"candidate:{candidate.candidate_id or '<missing>'}"
        candidate_ids.append(candidate.candidate_id)
        if not candidate.statement or candidate.statement != normalize_evidence_text(
            candidate.statement
        ):
            errors.append(f"{location}:statement_not_normalized")
        if not _ATOM.fullmatch(candidate.atom):
            errors.append(f"{location}:atom_invalid")
        if candidate.polarity not in POLARITIES:
            errors.append(f"{location}:polarity_invalid")
        if candidate.epistemic_status not in EPISTEMIC_STATUSES:
            errors.append(f"{location}:epistemic_status_invalid")
        if candidate.normative_force not in NORMATIVE_FORCES:
            errors.append(f"{location}:normative_force_invalid")
        if not candidate.compiler_id:
            errors.append(f"{location}:compiler_id_missing")
        errors.extend(_validate_context(candidate.context, location))

        roles: list[str] = []
        if not candidate.semantic_arguments:
            errors.append(f"{location}:semantic_arguments_missing")
        for argument in candidate.semantic_arguments:
            roles.append(argument.role)
            if not _ROLE.fullmatch(argument.role):
                errors.append(f"{location}:semantic_role_invalid:{argument.role}")
            if not argument.value or argument.value != normalize_evidence_text(argument.value):
                errors.append(f"{location}:semantic_argument_value_invalid:{argument.role}")
        if len(roles) != len(set(roles)):
            errors.append(f"{location}:semantic_role_collision")

        quoted_texts: list[str] = []
        quote_keys: list[tuple[str, str]] = []
        if not candidate.evidence_quotes:
            errors.append(f"{location}:evidence_quotes_missing")
        for quote in candidate.evidence_quotes:
            quote_keys.append((quote.block_id, quote.quote))
            block = blocks.get(quote.block_id)
            if block is None:
                errors.append(f"{location}:evidence_block_unknown:{quote.block_id}")
                continue
            if not quote.quote or quote.quote != normalize_evidence_text(quote.quote):
                errors.append(f"{location}:evidence_quote_not_normalized:{quote.block_id}")
                continue
            expected_quote_hash = hashlib.sha256(quote.quote.encode("utf-8")).hexdigest()
            if quote.quote_hash != expected_quote_hash:
                errors.append(f"{location}:evidence_quote_hash_mismatch:{quote.block_id}")
            if quote.quote not in block.text:
                errors.append(f"{location}:evidence_quote_not_in_block:{quote.block_id}")
            else:
                quoted_texts.append(quote.quote)
        if len(quote_keys) != len(set(quote_keys)):
            errors.append(f"{location}:evidence_quote_collision")

        support = " ".join(quoted_texts)
        cue_kinds: set[str] = set()
        for cue in candidate.semantic_cues:
            cue_kinds.add(cue.kind)
            if cue.kind not in CUE_KINDS:
                errors.append(f"{location}:semantic_cue_kind_invalid")
            if not cue.text or normalize_evidence_text(cue.text) not in support:
                errors.append(f"{location}:semantic_cue_untraced:{cue.kind}")
        if candidate.polarity == "negative" and "negation" not in cue_kinds:
            errors.append(f"{location}:negative_polarity_without_cue")
        if candidate.epistemic_status == "possible" and "epistemic" not in cue_kinds:
            errors.append(f"{location}:possible_status_without_cue")
        if candidate.normative_force != "none" and "normative" not in cue_kinds:
            errors.append(f"{location}:normative_force_without_cue")
        if candidate.attribution and "attribution" not in cue_kinds:
            errors.append(f"{location}:attribution_without_cue")

        quantity_surfaces: list[str] = []
        for quantity in candidate.quantities:
            surface = normalize_evidence_text(quantity.surface)
            quantity_surfaces.append(surface)
            if not surface or surface not in support:
                errors.append(f"{location}:quantity_untraced:{surface or '<missing>'}")
            if not quantity.normalized_value.strip():
                errors.append(f"{location}:quantity_normalized_value_missing")
        for token in _NUMBER.findall(candidate.statement):
            if token not in support:
                errors.append(f"{location}:statement_number_untraced:{token}")
            if not any(token in surface for surface in quantity_surfaces):
                errors.append(f"{location}:statement_number_unannotated:{token}")

        expected_hash = _canonical_hash(candidate.content_dict())
        expected_id = f"C-{_slug(candidate.atom)}-{expected_hash[:12]}"
        if candidate.candidate_hash != expected_hash:
            errors.append(f"{location}:candidate_hash_mismatch")
        if candidate.candidate_id != expected_id:
            errors.append(f"{location}:candidate_id_mismatch")

    if not candidates:
        errors.append("representation_candidates_missing")
    if len(candidate_ids) != len(set(candidate_ids)):
        errors.append("representation_candidate_id_collision")
    return sorted(set(errors))


def require_valid_representation_candidates(
    manifest: EvidenceManifest,
    candidates: Sequence[RepresentationCandidate],
) -> tuple[RepresentationCandidate, ...]:
    errors = validate_representation_candidates(manifest, candidates)
    if errors:
        raise RepresentationValidationError(errors)
    return tuple(candidates)


def _evidence_node(block: EvidenceBlock) -> dict[str, Any]:
    return {
        "id": block.block_id,
        "kind": "evidence",
        "text": block.text,
        "block_type": block.block_type,
        "provenance": {
            "source_locator": block.source_locator,
            "source_hash": block.source_hash,
            "physical_page": block.physical_page,
            "block_hash": block.block_hash,
            "extraction_system": block.extraction_system,
        },
    }


def compile_representation_seed(
    manifest: EvidenceManifest,
    candidates: Sequence[RepresentationCandidate],
) -> dict[str, Any]:
    """Compile validated claims into an AIF-compatible seed graph with no inferences."""

    valid = require_valid_representation_candidates(manifest, candidates)
    blocks = {block.block_id: block for block in manifest.blocks}
    referenced_ids = sorted(
        {quote.block_id for candidate in valid for quote in candidate.evidence_quotes}
    )
    information_nodes: list[dict[str, Any]] = [
        _evidence_node(blocks[block_id]) for block_id in referenced_ids
    ]
    for candidate in sorted(valid, key=lambda item: item.candidate_id):
        information_nodes.append(
            {
                "id": candidate.candidate_id,
                "kind": "claim",
                "atom": candidate.atom,
                "polarity": candidate.polarity,
                "statement": candidate.statement,
                "asserted": True,
                "active": True,
                "context": dict(candidate.context),
                "semantic_arguments": [
                    item.as_dict() for item in candidate.semantic_arguments
                ],
                "epistemic_status": candidate.epistemic_status,
                "normative_force": candidate.normative_force,
                "attribution": candidate.attribution,
                "quantities": [item.as_dict() for item in candidate.quantities],
                "provenance": {
                    "quoted_from": sorted(
                        {quote.block_id for quote in candidate.evidence_quotes}
                    ),
                    "generated_by": candidate.compiler_id,
                    "candidate_hash": candidate.candidate_hash,
                },
            }
        )
    graph = {
        "format": "gdu-representation-seed-v1",
        "document_id": manifest.document_id,
        "source_hash": manifest.source_hash,
        "information_nodes": information_nodes,
        "scheme_nodes": [],
    }
    issues = validate_aif_interface(graph)
    if issues:
        raise RepresentationValidationError(
            [f"aif:{issue.location}:{issue.code}" for issue in issues]
        )
    return graph
