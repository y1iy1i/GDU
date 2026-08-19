from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gdu.builder_v0.source_reader import PypdfBackend, SourceReader  # noqa: E402
from gdu.builder_v0.types import SourceRequest, TechnicalFailure  # noqa: E402


class FakePdfBackend:
    def __init__(self, pages: list[str]) -> None:
        self.pages = pages
        self.calls: list[int] = []
        self.fail_page: int | None = None

    @property
    def name(self) -> str:
        return "fake-pdf-backend-v0"

    def page_count(self, path: Path) -> int:
        return len(self.pages)

    def extract_page_text(self, path: Path, page_number: int) -> str:
        self.calls.append(page_number)
        if page_number == self.fail_page:
            raise TechnicalFailure("source_reader", "injected page failure")
        return self.pages[page_number - 1]


class SourceReaderV0ContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.work = Path(self.temp.name)
        self.pdf = self.work / "paper.pdf"
        self.pdf.write_bytes(b"fixed fake PDF identity bytes")
        self.backend = FakePdfBackend(
            ["Page one  has text.", "", "Page three\ncontains evidence."]
        )
        self.reader = SourceReader(self.pdf, "doc-1", self.backend)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_identity_records_hash_page_count_and_backend(self) -> None:
        identity = self.reader.inspect()

        self.assertEqual(identity.document_id, "doc-1")
        self.assertEqual(identity.original_filename, "paper.pdf")
        self.assertEqual(identity.pdf_page_count, 3)
        self.assertEqual(identity.extraction_system, "fake-pdf-backend-v0")
        self.assertEqual(
            identity.source_sha256, hashlib.sha256(self.pdf.read_bytes()).hexdigest()
        )

    def test_overlapping_ranges_are_read_once_in_physical_order(self) -> None:
        packet = self.reader.read(
            SourceRequest("inspect evidence", ((1, 2), (2, 3)))
        )

        self.assertEqual(self.backend.calls, [1, 2, 3])
        self.assertEqual([item.page for item in packet.pdf_fragments], [1, 3])
        self.assertEqual(len(packet.retrieval_notes), 1)
        self.assertIn("OCR was not attempted", packet.retrieval_notes[0])

    def test_page_ranges_are_one_based_and_bounded(self) -> None:
        for ranges in (((0, 1),), ((1, 4),), ((3, 2),), ()):
            with self.subTest(ranges=ranges):
                with self.assertRaises(ValueError):
                    self.reader.read(SourceRequest("bounded", ranges))

    def test_pdf_change_after_inspection_is_rejected(self) -> None:
        self.reader.inspect()
        self.pdf.write_bytes(b"changed source bytes")

        with self.assertRaises(TechnicalFailure):
            self.reader.read(SourceRequest("read", ((1, 1),)))

    def test_preregistered_pdf_hash_is_enforced(self) -> None:
        reader = SourceReader(
            self.pdf,
            "doc-1",
            self.backend,
            expected_source_sha256="0" * 64,
        )
        with self.assertRaises(TechnicalFailure):
            reader.inspect()

    def test_navigation_text_is_separate_from_pdf_fragments(self) -> None:
        packet = self.reader.read(
            SourceRequest("navigation", ((1, 1),)),
            navigation_text={1: "A navigation-only sentence."},
        )

        self.assertEqual(packet.navigation_text, ("A navigation-only sentence.",))
        self.assertNotIn(
            "A navigation-only sentence.",
            [fragment.excerpt for fragment in packet.pdf_fragments],
        )
        with self.assertRaises(ValueError):
            self.reader.verify_excerpt(
                1, "A navigation-only sentence.", "physical-page:1"
            )

    def test_verified_excerpt_has_validator_compatible_hash(self) -> None:
        fragment = self.reader.verify_excerpt(
            3, "Page three contains evidence.", "physical-page:3#line:1"
        )

        value = fragment.as_evidence_fragment()
        self.assertEqual(value["page"], 3)
        self.assertEqual(
            value["fragment_sha256"],
            hashlib.sha256(value["excerpt"].encode("utf-8")).hexdigest(),
        )

    def test_excerpt_must_exist_on_requested_pdf_page(self) -> None:
        with self.assertRaises(ValueError):
            self.reader.verify_excerpt(1, "Page three contains evidence.", "wrong")

    def test_non_text_modalities_are_not_silently_flattened(self) -> None:
        with self.assertRaises(TechnicalFailure):
            self.reader.read(
                SourceRequest("inspect image", ((1, 1),), modalities=("image",))
            )

    def test_backend_failure_remains_a_technical_failure(self) -> None:
        self.backend.fail_page = 3
        with self.assertRaises(TechnicalFailure):
            self.reader.read(SourceRequest("read", ((3, 3),)))

    def test_request_identity_is_stable_and_request_specific(self) -> None:
        first = self.reader.read(SourceRequest("one", ((1, 1),)))
        repeated = self.reader.read(SourceRequest("one", ((1, 1),)))
        different = self.reader.read(SourceRequest("two", ((1, 1),)))

        self.assertEqual(first.request_identity, repeated.request_identity)
        self.assertNotEqual(first.request_identity, different.request_identity)


try:
    import pypdf  # noqa: F401
    from reportlab.pdfgen import canvas

    REAL_PDF_AVAILABLE = True
except ModuleNotFoundError:
    REAL_PDF_AVAILABLE = False


@unittest.skipUnless(REAL_PDF_AVAILABLE, "pypdf/reportlab runtime not available")
class PypdfBackendIntegrationTests(unittest.TestCase):
    def test_two_page_pdf_round_trip_uses_physical_pages(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            pdf = Path(directory) / "two-pages.pdf"
            document = canvas.Canvas(str(pdf))
            document.drawString(72, 720, "First physical page")
            document.showPage()
            document.drawString(72, 720, "Second physical page evidence")
            document.save()

            reader = SourceReader(pdf, "real-fixture", PypdfBackend())
            identity = reader.inspect()
            packet = reader.read(SourceRequest("round trip", ((2, 2),)))
            fragment = reader.verify_excerpt(
                2, "Second physical page evidence", "physical-page:2"
            )

            self.assertEqual(identity.pdf_page_count, 2)
            self.assertEqual([item.page for item in packet.pdf_fragments], [2])
            self.assertEqual(fragment.page, 2)


if __name__ == "__main__":
    unittest.main()
