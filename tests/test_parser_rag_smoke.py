from __future__ import annotations

from Tool.contracts.canonical import CanonicalDocument, DocumentMeta, Fragment, Section, TableData


def _canonical(document_id: str, *, title: str, sections: list[Section], fragments: list[Fragment], tables: list[TableData] | None = None) -> CanonicalDocument:
    return CanonicalDocument(
        document=DocumentMeta(
            document_id=document_id,
            title=title,
            source_path=f"Raw/{document_id}.pdf",
            file_name=f"{title}.pdf",
            source_type="pdf",
            doc_type="pep",
            metadata={"parse_workflow": {"eval_summary": {"pass": 3, "warn": 0, "fail": 0, "na": 0}, "review_items": []}},
        ),
        sections=sections,
        fragments=fragments,
        tables=tables or [],
    )


def test_release0_parser_rag_smoke_resolves_aliases_and_classifies_real_gaps(tmp_dir):
    from Tool.evals.parser_rag_smoke import release0_parser_rag_smoke_report

    parsed_dir = tmp_dir / "parsed"
    parsed_dir.mkdir()
    _canonical(
        "doc-a",
        title="A PEP",
        sections=[
            Section(section_id="sec-purpose", title="Purpose and Scope", level=1),
            Section(section_id="sec-qmp", title="QMP Responsibility", level=1),
        ],
        fragments=[
            Fragment(
                fragment_id="frag-purpose",
                section_id="sec-purpose",
                fragment_type="paragraph",
                text="This document defines the process scope and applicability.",
                anchors={"page": 1, "heading_path": ["Purpose and Scope"]},
            ),
            Fragment(
                fragment_id="frag-qmp",
                section_id="sec-qmp",
                fragment_type="paragraph",
                text="The Product Owner prepares QMP evidence and confirms deliverable readiness.",
                anchors={"page": 3, "heading_path": ["QMP Responsibility"]},
            )
        ],
    ).save(parsed_dir / "doc-a.json")
    _canonical(
        "doc-b",
        title="B PEP",
        sections=[Section(section_id="sec-table", title="Review Matrix", level=1)],
        fragments=[
            Fragment(
                fragment_id="frag-intro",
                section_id="sec-table",
                fragment_type="paragraph",
                text="Review matrix introduction.",
                anchors={"page": 5, "heading_path": ["Review Matrix"]},
            )
        ],
        tables=[TableData(table_id="tbl-review", section_id="sec-table", page=5, rows=[["Review", "Policy"], ["Agile tailoring", "mandatory review cannot be tailored"]], anchors={"page": 5})],
    ).save(parsed_dir / "doc-b.json")

    cases = [
        {
            "case_id": "qmp-pass",
            "question": "QMP evidence Product Owner",
            "source_scope": {"mode": "selected_docs", "document_ids": ["a"]},
            "expected_section_terms_any": ["QMP"],
            "expected_terms_any": ["Product Owner", "QMP"],
        },
        {
            "case_id": "query-gap",
            "question": "unrelated wording",
            "source_scope": {"mode": "selected_docs", "document_ids": ["a"]},
            "expected_section_terms_any": ["QMP"],
            "expected_terms_any": ["Product Owner", "QMP"],
        },
        {
            "case_id": "parser-gap",
            "question": "regulatory approval plan",
            "source_scope": {"mode": "selected_docs", "document_ids": ["a"]},
            "expected_section_terms_any": ["Regulatory Approval Plan"],
            "expected_terms_any": ["submission"],
        },
        {
            "case_id": "table-gap",
            "question": "unrelated wording",
            "source_scope": {"mode": "selected_docs", "document_ids": ["b"]},
            "expected_section_terms_any": ["tailoring"],
            "expected_terms_any": ["mandatory review"],
        },
    ]

    report = release0_parser_rag_smoke_report(parsed_dir=parsed_dir, document_alias_map={"a": "doc-a", "b": "doc-b"}, cases=cases, top_k=1)

    diagnostics = {item["case_id"]: item for item in report["case_diagnostics"]}
    assert report["schema_version"] == "release0-parser-rag-smoke-v0.1"
    assert diagnostics["qmp-pass"]["status"] == "pass"
    assert diagnostics["query-gap"]["failure_category"] == "chat_route_query_answer_gap"
    assert diagnostics["parser-gap"]["failure_category"] == "parser_structure_gap"
    assert diagnostics["table-gap"]["failure_category"] == "table_gap"
    assert report["failure_summary"]["chat_route_query_answer_gap"] == 1
    assert report["failure_summary"]["parser_structure_gap"] == 1
    assert report["failure_summary"]["table_gap"] == 1
