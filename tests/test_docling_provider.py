from __future__ import annotations

from types import SimpleNamespace

import pytest

from Tool.parsers.providers.docling_provider import (
    build_docling_parser_fusion_metadata,
    extract_docling_blocks,
    load_docling_converter_class,
)


class FakeConverter:
    def __init__(self, document):
        self.document = document
        self.sources: list[str] = []

    def convert(self, source: str):
        self.sources.append(source)
        return SimpleNamespace(document=self.document)


def test_docling_provider_maps_text_layout_table_and_visual_candidates(tmp_dir):
    document = SimpleNamespace(
        texts=[
            SimpleNamespace(
                self_ref="#/texts/0",
                text="R2 Planning",
                label="section_header",
                prov=[
                    SimpleNamespace(
                        page_no=12,
                        bbox=SimpleNamespace(l=72, t=130, r=510, b=155),
                    )
                ],
                reading_order=18,
                confidence=0.91,
            )
        ],
        tables=[
            SimpleNamespace(
                self_ref="#/tables/0",
                rows=[["Role", "Deliverable"], ["PO", "QMP"]],
                label="table",
                prov=[SimpleNamespace(page_no=14, bbox=[64, 220, 530, 470])],
                confidence=0.87,
            )
        ],
        pictures=[
            SimpleNamespace(
                self_ref="#/pictures/0",
                text="R2 review flow diagram",
                label="picture",
                prov=[SimpleNamespace(page_no=18, bbox=(80, 180, 500, 430))],
                confidence=0.76,
            )
        ],
    )
    converter = FakeConverter(document)
    source_path = tmp_dir / "pep.pdf"

    output = extract_docling_blocks(source_path, converter=converter)

    assert converter.sources == [str(source_path)]
    assert output.provider == "docling"
    assert output.extraction_blocks[0].text == "R2 Planning"
    assert output.extraction_blocks[0].anchors["page"] == 12
    assert output.layout_blocks[0].layout_type == "section_header"
    assert output.layout_blocks[0].anchors["bbox"] == [72, 130, 510, 155]
    assert output.layout_blocks[0].anchors["reading_order"] == 18
    assert output.table_blocks[0].rows[1] == ["PO", "QMP"]
    assert output.table_blocks[0].anchors["bbox"] == [64, 220, 530, 470]
    assert output.visual_candidates[0].provider == "docling_ocr"
    assert output.visual_candidates[0].candidate_type == "picture"
    assert output.visual_candidates[0].anchors["page"] == 18


def test_docling_provider_builds_fusion_metadata(tmp_dir):
    document = SimpleNamespace(
        texts=[SimpleNamespace(self_ref="#/texts/0", text="Purpose", prov=[SimpleNamespace(page_no=1)])],
        tables=[SimpleNamespace(self_ref="#/tables/0", rows=[["A", "B"]], prov=[SimpleNamespace(page_no=2)])],
        pictures=[],
    )
    output = extract_docling_blocks(tmp_dir / "sample.pdf", converter=FakeConverter(document))

    metadata = build_docling_parser_fusion_metadata(
        output,
        canonical_output={"sections": 0, "fragments": 0, "tables": 1, "figures": 0},
    )

    assert metadata["schema_version"] == "parser-fusion-v0.1"
    assert metadata["fusion_mode"] == "docling_provider_extraction"
    assert metadata["providers"] == ["docling"]
    assert metadata["provider_roles"]["docling"] == "layout_table_ocr"
    assert metadata["counts"]["extraction_blocks"] == 1
    assert metadata["counts"]["table_blocks"] == 1
    assert metadata["canonical_output"]["tables"] == 1


def test_docling_converter_import_error_is_actionable():
    def missing_docling(module_name: str):
        raise ImportError(f"No module named {module_name}")

    with pytest.raises(RuntimeError, match="pip install docling"):
        load_docling_converter_class(import_module=missing_docling)