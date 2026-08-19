from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Iterable, Mapping

from .types import (
    PdfBackend,
    PdfPageFragment,
    SourceDocumentIdentity,
    SourcePacket,
    SourceRequest,
    TechnicalFailure,
)


class PypdfBackend:
    """Optional real PDF backend. Import is delayed until the backend is used."""

    def __init__(self) -> None:
        try:
            import pypdf
        except ModuleNotFoundError as exc:
            raise TechnicalFailure(
                "source_reader",
                "pypdf is required for the real PDF backend; install requirements-builder.txt",
            ) from exc
        self._pypdf = pypdf

    @property
    def name(self) -> str:
        return f"pypdf {self._pypdf.__version__}"

    def page_count(self, path: Path) -> int:
        try:
            reader = self._pypdf.PdfReader(path)
            if reader.is_encrypted:
                raise TechnicalFailure(
                    "source_reader", "encrypted PDFs are not supported in v0"
                )
            return len(reader.pages)
        except TechnicalFailure:
            raise
        except Exception as exc:
            raise TechnicalFailure("source_reader", f"cannot inspect PDF: {exc}") from exc

    def extract_page_text(self, path: Path, page_number: int) -> str:
        try:
            reader = self._pypdf.PdfReader(path)
            if reader.is_encrypted:
                raise TechnicalFailure(
                    "source_reader", "encrypted PDFs are not supported in v0"
                )
            return reader.pages[page_number - 1].extract_text() or ""
        except TechnicalFailure:
            raise
        except Exception as exc:
            raise TechnicalFailure(
                "source_reader", f"cannot extract physical page {page_number}: {exc}"
            ) from exc


class SourceReader:
    """Read physical PDF pages without choosing a long-document chunking policy."""

    def __init__(
        self,
        pdf_path: Path,
        document_id: str,
        backend: PdfBackend,
        expected_source_sha256: str | None = None,
    ) -> None:
        if not document_id.strip():
            raise ValueError("document_id must be non-empty")
        self.pdf_path = pdf_path
        self.document_id = document_id
        self.backend = backend
        self.expected_source_sha256 = expected_source_sha256
        self._identity: SourceDocumentIdentity | None = None

    def inspect(self) -> SourceDocumentIdentity:
        if not self.pdf_path.is_file():
            raise TechnicalFailure(
                "source_reader", f"PDF does not exist: {self.pdf_path}"
            )
        digest = self._sha256_file(self.pdf_path)
        if (
            self.expected_source_sha256 is not None
            and digest != self.expected_source_sha256
        ):
            raise TechnicalFailure(
                "source_reader", "PDF hash does not match the preregistered source"
            )
        page_count = self.backend.page_count(self.pdf_path)
        if page_count < 1:
            raise TechnicalFailure("source_reader", "PDF must contain at least one page")
        self._identity = SourceDocumentIdentity(
            document_id=self.document_id,
            original_filename=self.pdf_path.name,
            source_sha256=digest,
            pdf_page_count=page_count,
            extraction_system=self.backend.name,
        )
        return self._identity

    def read(
        self,
        request: SourceRequest,
        navigation_text: Mapping[int, str] | None = None,
    ) -> SourcePacket:
        identity = self._require_unchanged_identity()
        pages = self._expand_ranges(request.page_ranges, identity.pdf_page_count)
        if not request.purpose.strip():
            raise ValueError("source request purpose must be non-empty")
        if not request.modalities or any(
            modality != "text" for modality in request.modalities
        ):
            raise TechnicalFailure(
                "source_reader",
                "SourceReader v0 only extracts the PDF text layer; visual modalities require a later renderer",
            )

        fragments: list[PdfPageFragment] = []
        notes: list[str] = []
        nav: list[str] = []
        for page in pages:
            text = self.backend.extract_page_text(self.pdf_path, page)
            normalized = self._normalize_text(text)
            if normalized:
                fragments.append(self._fragment(page, f"physical-page:{page}", normalized))
            else:
                notes.append(
                    f"physical page {page} has no extractable text layer; OCR was not attempted"
                )
            if navigation_text and page in navigation_text:
                nav.append(navigation_text[page])

        request_identity = self._sha256_text(
            "|".join(
                [
                    request.purpose,
                    repr(request.page_ranges),
                    repr(request.modalities),
                    repr(request.locator_hints),
                    identity.source_sha256,
                ]
            )
        )
        return SourcePacket(
            source_document_id=identity.document_id,
            request_identity=request_identity,
            pdf_fragments=tuple(fragments),
            navigation_text=tuple(nav),
            retrieval_notes=tuple(notes),
        )

    def verify_excerpt(
        self, page: int, excerpt: str, locator: str
    ) -> PdfPageFragment:
        identity = self._require_unchanged_identity()
        self._validate_page(page, identity.pdf_page_count)
        normalized_excerpt = self._normalize_text(excerpt)
        if not normalized_excerpt:
            raise ValueError("evidence excerpt must be non-empty")
        page_text = self._normalize_text(
            self.backend.extract_page_text(self.pdf_path, page)
        )
        if normalized_excerpt not in page_text:
            raise ValueError(
                "excerpt is not present in the authoritative PDF page text"
            )
        return self._fragment(page, locator, normalized_excerpt)

    def _require_unchanged_identity(self) -> SourceDocumentIdentity:
        identity = self._identity or self.inspect()
        current = self._sha256_file(self.pdf_path)
        if current != identity.source_sha256:
            raise TechnicalFailure(
                "source_reader", "PDF changed after source identity was inspected"
            )
        return identity

    @classmethod
    def _expand_ranges(
        cls, ranges: Iterable[tuple[int, int]], page_count: int
    ) -> tuple[int, ...]:
        pages: list[int] = []
        seen: set[int] = set()
        for start, end in ranges:
            cls._validate_page(start, page_count)
            cls._validate_page(end, page_count)
            if end < start:
                raise ValueError(f"invalid page range: {start}-{end}")
            for page in range(start, end + 1):
                if page not in seen:
                    seen.add(page)
                    pages.append(page)
        if not pages:
            raise ValueError("source request must include at least one page")
        return tuple(pages)

    @staticmethod
    def _validate_page(page: int, page_count: int) -> None:
        if page < 1 or page > page_count:
            raise ValueError(f"physical page {page} is outside 1-{page_count}")

    @classmethod
    def _fragment(cls, page: int, locator: str, excerpt: str) -> PdfPageFragment:
        if not locator.strip():
            raise ValueError("evidence locator must be non-empty")
        return PdfPageFragment(
            page=page,
            locator=locator,
            excerpt=excerpt,
            fragment_sha256=cls._sha256_text(excerpt),
        )

    @staticmethod
    def _normalize_text(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()

    @staticmethod
    def _sha256_text(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        try:
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
        except OSError as exc:
            raise TechnicalFailure("source_reader", str(exc)) from exc
        return digest.hexdigest()
