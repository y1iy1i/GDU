from __future__ import annotations

import hashlib
import sys
import unittest
from dataclasses import replace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gdu.builder_v0.types import (  # noqa: E402
    PdfPageFragment,
    SourceDocumentIdentity,
    SourcePacket,
)
from gdu.builder_v1 import (  # noqa: E402
    EvidenceRelationSpec,
    EvidenceManifest,
    EvidenceValidationError,
    PageElement,
    TableRegion,
    build_document_map,
    evidence_manifest_from_elements,
    evidence_manifest_from_packet,
    validate_evidence_manifest,
)


class BuilderV1EvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.identity = SourceDocumentIdentity(
            document_id="paper-01",
            original_filename="paper.pdf",
            source_sha256="a" * 64,
            pdf_page_count=3,
            extraction_system="typed-parser 1.0",
        )

    def test_elements_become_deterministic_page_addressable_blocks(self) -> None:
        elements = [
            PageElement(2, "Revenue   was 100.00%.", "paragraph"),
            PageElement(1, "Introduction", "heading"),
            PageElement(2, "Cost was -2.5.", "paragraph"),
        ]

        first = evidence_manifest_from_elements(self.identity, elements)
        repeated = evidence_manifest_from_elements(self.identity, elements)

        self.assertEqual(first, repeated)
        self.assertEqual(first.manifest_hash, repeated.manifest_hash)
        self.assertEqual(
            [(block.physical_page, block.sequence) for block in first.blocks],
            [(1, 1), (2, 1), (2, 2)],
        )
        self.assertEqual(first.blocks[1].text, "Revenue was 100.00%.")
        self.assertIn("-2.5", first.blocks[2].text)
        self.assertTrue(first.blocks[0].block_id.startswith("EB-paper-01-0001-001-"))

    def test_empty_or_out_of_range_input_is_rejected(self) -> None:
        cases = (
            [],
            [PageElement(1, "   ")],
            [PageElement(4, "Outside the PDF")],
        )
        for elements in cases:
            with self.subTest(elements=elements):
                with self.assertRaises(EvidenceValidationError):
                    evidence_manifest_from_elements(self.identity, elements)

    def test_duplicate_source_locator_is_rejected(self) -> None:
        with self.assertRaises(EvidenceValidationError) as raised:
            evidence_manifest_from_elements(
                self.identity,
                [
                    PageElement(1, "First", source_locator="physical-page:1#same"),
                    PageElement(1, "Second", source_locator="physical-page:1#same"),
                ],
            )
        self.assertIn("source_locator_collision", raised.exception.errors)

    def test_tampering_with_text_or_extractor_is_detected(self) -> None:
        manifest = evidence_manifest_from_elements(
            self.identity, [PageElement(1, "Original evidence")]
        )
        changed_text = replace(manifest.blocks[0], text="Changed evidence")
        changed_extractor = replace(manifest.blocks[0], extraction_system="other parser")

        text_errors = validate_evidence_manifest(replace(manifest, blocks=(changed_text,)))
        extractor_errors = validate_evidence_manifest(
            replace(manifest, blocks=(changed_extractor,))
        )

        self.assertTrue(any(error.endswith("block_hash_mismatch") for error in text_errors))
        self.assertTrue(
            any(error.endswith("extraction_system_mismatch") for error in extractor_errors)
        )

    def test_malformed_bbox_is_reported_instead_of_crashing(self) -> None:
        manifest = evidence_manifest_from_elements(
            self.identity, [PageElement(1, "Located evidence", bbox=(1, 2, 3, 4))]
        )
        malformed = replace(manifest.blocks[0], bbox=(1, 2, 3))

        errors = validate_evidence_manifest(replace(manifest, blocks=(malformed,)))

        self.assertTrue(any(error.endswith("bbox_invalid") for error in errors))

    def test_verified_v0_packet_can_enter_v1_without_navigation_text(self) -> None:
        text = "Page two evidence."
        packet = SourcePacket(
            source_document_id="paper-01",
            request_identity="request-1",
            pdf_fragments=(
                PdfPageFragment(
                    page=2,
                    locator="physical-page:2",
                    excerpt=text,
                    fragment_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                ),
            ),
            navigation_text=("Unverified navigation text",),
        )

        manifest = evidence_manifest_from_packet(self.identity, packet)

        self.assertEqual(manifest.blocks[0].text, text)
        self.assertEqual(manifest.blocks[0].source_locator, "physical-page:2")
        self.assertNotIn("Unverified navigation text", manifest.blocks[0].text)
        self.assertTrue(any("excluded" in note for note in manifest.extraction_notes))

    def test_packet_fragment_hash_mismatch_is_rejected(self) -> None:
        packet = SourcePacket(
            source_document_id="paper-01",
            request_identity="request-1",
            pdf_fragments=(
                PdfPageFragment(1, "physical-page:1", "Evidence", "0" * 64),
            ),
        )
        with self.assertRaises(EvidenceValidationError) as raised:
            evidence_manifest_from_packet(self.identity, packet)
        self.assertIn(
            "physical_page:1:fragment_hash_mismatch", raised.exception.errors
        )

    def test_plain_page_text_creates_one_conservative_document_section(self) -> None:
        manifest = evidence_manifest_from_elements(
            self.identity,
            [
                PageElement(1, "Page one", "page_text"),
                PageElement(3, "Page three", "page_text"),
            ],
        )

        document_map = build_document_map(manifest)

        self.assertEqual(document_map.map_mode, "page_only")
        self.assertEqual(len(document_map.sections), 1)
        self.assertEqual(document_map.sections[0].start_page, 1)
        self.assertEqual(document_map.sections[0].end_page, 3)

    def test_typed_headings_create_explicit_sections_and_preface(self) -> None:
        manifest = evidence_manifest_from_elements(
            self.identity,
            [
                PageElement(1, "Abstract", "paragraph"),
                PageElement(1, "1 Method", "heading"),
                PageElement(1, "Method body", "paragraph"),
                PageElement(2, "2 Results", "heading"),
                PageElement(2, "Result body", "paragraph"),
            ],
        )

        document_map = build_document_map(manifest)
        repeated = build_document_map(manifest)

        self.assertEqual(document_map.map_mode, "heading_aware")
        self.assertEqual(
            [section.title for section in document_map.sections],
            ["Document preface", "1 Method", "2 Results"],
        )
        self.assertEqual(document_map.map_hash, repeated.map_hash)
        self.assertEqual(len(document_map.sections[1].member_block_ids), 2)

    def test_manifest_without_blocks_is_invalid(self) -> None:
        manifest = EvidenceManifest(
            format="gdu-evidence-manifest-v1",
            document_id=self.identity.document_id,
            original_filename=self.identity.original_filename,
            source_hash=self.identity.source_sha256,
            physical_page_count=self.identity.pdf_page_count,
            extraction_system=self.identity.extraction_system,
            blocks=(),
        )
        self.assertIn("manifest_blocks_missing", validate_evidence_manifest(manifest))

    def test_table_region_links_cells_to_document_text_position(self) -> None:
        manifest = evidence_manifest_from_elements(
            self.identity,
            [
                PageElement(
                    2,
                    "2025年 2024年 同比变动",
                    "table",
                    source_locator="paper.pdf#page=2&table=1&rows=0&cols=0-2",
                    bbox=(20, 100, 560, 130),
                    table_region=TableRegion("table-1", "header", 0, 0, 0, 2),
                ),
                PageElement(
                    2,
                    "经营活动产生的现金流量净额 72,545,781.16 161,441,300.00 -55.06",
                    "table",
                    source_locator="paper.pdf#page=2&table=1&rows=1&cols=0-3",
                    bbox=(20, 130, 560, 165),
                    table_region=TableRegion("table-1", "body", 1, 1, 0, 3),
                ),
                PageElement(
                    2,
                    "本期经营活动现金流下降，主要由于销售商品收到的现金减少。",
                    "paragraph",
                    source_locator="paper.pdf#page=2&paragraph=7",
                    bbox=(20, 190, 560, 220),
                ),
            ],
            relation_specs=(
                EvidenceRelationSpec(
                    "paper.pdf#page=2&table=1&rows=0&cols=0-2",
                    "paper.pdf#page=2&table=1&rows=1&cols=0-3",
                    "qualifies",
                ),
                EvidenceRelationSpec(
                    "paper.pdf#page=2&paragraph=7",
                    "paper.pdf#page=2&table=1&rows=1&cols=0-3",
                    "describes",
                ),
            ),
        )

        self.assertEqual(validate_evidence_manifest(manifest), [])
        self.assertEqual(manifest.blocks[0].table_region.region_kind, "header")
        self.assertEqual(manifest.blocks[1].table_region.row_start, 1)
        self.assertEqual(len(manifest.relations), 2)
        self.assertEqual(manifest.relations[1].relation, "describes")


if __name__ == "__main__":
    unittest.main()
