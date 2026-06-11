from __future__ import annotations

from pathlib import Path

from Tool.contracts.canonical import CanonicalDocument, DocumentMeta
from Tool.normalizers import detect_doc_type
from Tool.parsers.docx_fusion import build_docx_fusion_metadata, parse_docx_with_fusion
from Tool.parsers.docx_parser import parse_docx
from Tool.parsers.markdown_parser import parse_markdown
from Tool.parsers.pdf_fusion import build_pdf_fusion_metadata, parse_pdf_with_fusion
from Tool.parsers.pdf_parser import parse_pdf
from Tool.parsers.pptx_parser import parse_pptx
from Tool.parsers.xlsx_parser import parse_xlsx

SUPPORTED_SUFFIXES = {".docx", ".pdf", ".pptx", ".xlsx", ".md"}


def parse_document(file_path: str | Path, manifest: dict) -> CanonicalDocument:
    from Tool.workflows.document_parse import apply_parse_workflow_contract

    path = Path(file_path)
    suffix = path.suffix.lower()
    parser_map = {
        ".docx": parse_docx,
        ".md": parse_markdown,
        ".pdf": parse_pdf,
        ".pptx": parse_pptx,
        ".xlsx": parse_xlsx,
    }
    parser_name_map = {
        ".docx": "docx_parser",
        ".md": "markdown_parser",
        ".pdf": "pdf_parser",
        ".pptx": "pptx_parser",
        ".xlsx": "xlsx_parser",
    }
    parser = parser_map.get(suffix)
    if parser is None:
        return apply_parse_workflow_contract(
            _failed_document(path, manifest, f"Unsupported file type: {suffix}"),
            parser_name="unsupported_parser",
            trace=["W0 context loaded", f"W1 unsupported suffix {suffix}", "E1 capture completeness eval"],
        )

    try:
        canonical = parser(path, manifest)
    except Exception as exc:
        canonical = _failed_document(path, manifest, str(exc))
    return apply_parse_workflow_contract(canonical, parser_name=parser_name_map.get(suffix, f"{suffix.lstrip('.')}_parser"))


def _failed_document(path: Path, manifest: dict, error: str) -> CanonicalDocument:
    meta = DocumentMeta(
        document_id=manifest["document_id"],
        title=manifest.get("title", path.stem),
        source_path=manifest["stored_path"],
        file_name=path.name,
        source_type=path.suffix.lower().lstrip("."),
        doc_type=detect_doc_type(manifest.get("title", path.stem), path.name),
        checksum=manifest.get("checksum", ""),
        metadata={"manifest_path": manifest.get("manifest_path", "")},
    )
    return CanonicalDocument(document=meta, parse_status="failed", errors=[error])
