from __future__ import annotations

from Tool.contracts.canonical import CanonicalDocument, DocumentMeta, Fragment, Section


def _canonical(document_id: str, *, title: str, sections: list[Section], fragments: list[Fragment]) -> CanonicalDocument:
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
    )


def test_release0_route_rag_smoke_uses_runtime_query_pack_and_rerank(tmp_dir):
    from Tool.evals.route_rag_smoke import release0_route_rag_smoke_report

    parsed_dir = tmp_dir / "parsed"
    parsed_dir.mkdir()
    _canonical(
        "doc-mi",
        title="MI PEP",
        sections=[
            Section(section_id="sec-purpose", title="1 Purpose and scope / 目的和适用范围", level=1),
            Section(section_id="sec-qmp-contents", title="4.2 QMP / Quality Management Plan", level=1),
            Section(section_id="sec-qmp-owner", title="4.3 QMP responsibility", level=1),
        ],
        fragments=[
            Fragment(
                fragment_id="frag-purpose",
                section_id="sec-purpose",
                fragment_type="paragraph",
                text="This PEP document defines process scope and general procedure applicability.",
                anchors={"page": 5, "heading_path": ["1 Purpose and scope / 目的和适用范围"]},
            ),
            Fragment(
                fragment_id="frag-qmp-content",
                section_id="sec-qmp-contents",
                fragment_type="paragraph",
                text="The QMP shall contain required contents including project quality objectives, deliverable plan, and review records.",
                anchors={"page": 12, "heading_path": ["4.2 QMP / Quality Management Plan"]},
            ),
            Fragment(
                fragment_id="frag-qmp-owner",
                section_id="sec-qmp-owner",
                fragment_type="paragraph",
                text="The Product Owner is responsible to prepare and maintain the QMP as the author of the quality management plan.",
                anchors={"page": 13, "heading_path": ["4.3 QMP responsibility"]},
            ),
        ],
    ).save(parsed_dir / "doc-mi.json")
    _canonical(
        "doc-xp",
        title="XP PEP",
        sections=[
            Section(section_id="sec-purpose", title="1 Purpose and scope/目的和适用范围", level=1),
            Section(section_id="sec-provisional", title="7 Provisional solution and backward method/过渡措施和 补救办法", level=1),
            Section(section_id="sec-agile-tailorable", title="6.5 Agile tailoring review", level=1),
            Section(section_id="sec-agile-mandatory", title="6.6 Mandatory agile review boundary", level=1),
        ],
        fragments=[
            Fragment(
                fragment_id="frag-purpose",
                section_id="sec-purpose",
                fragment_type="paragraph",
                text="This XP PEP document defines process scope and applicability.",
                anchors={"page": 6, "heading_path": ["1 Purpose and scope/目的和适用范围"]},
            ),
            Fragment(
                fragment_id="frag-provisional",
                section_id="sec-provisional",
                fragment_type="paragraph",
                text="This section describes backward method and transitional procedure for ongoing projects.",
                anchors={"page": 31, "heading_path": ["7 Provisional solution and backward method/过渡措施和 补救办法"]},
            ),
            Fragment(
                fragment_id="frag-tailorable",
                section_id="sec-agile-tailorable",
                fragment_type="paragraph",
                text="For agile development, selected review activities may be tailored when the tailoring rationale and approval evidence are recorded.",
                anchors={"page": 21, "heading_path": ["6.5 Agile tailoring review"]},
            ),
            Fragment(
                fragment_id="frag-mandatory",
                section_id="sec-agile-mandatory",
                fragment_type="paragraph",
                text="Mandatory review gates cannot be tailored; the project shall keep review records and approval evidence.",
                anchors={"page": 22, "heading_path": ["6.6 Mandatory agile review boundary"]},
            ),
        ],
    ).save(parsed_dir / "doc-xp.json")

    cases = [
        {
            "case_id": "qmp-route-rag",
            "question": "MI PEP 中 QMP 需要包含哪些内容？谁负责撰写 QMP？",
            "source_scope": {"mode": "selected_docs", "document_aliases": ["mi_pep"]},
            "expected_route_id": "deliverable_detail",
            "expected_evidence": {
                "section_terms_any": ["QMP", "Quality Management Plan", "responsibility"],
                "terms_any": ["QMP", "quality management plan", "content", "owner", "responsible", "author"],
            },
        },
        {
            "case_id": "tailoring-route-rag",
            "question": "XP PEP 采用敏捷方法开发，可以裁剪哪些评审？哪些评审不可被裁剪？",
            "source_scope": {"mode": "selected_docs", "document_aliases": ["xp_pep"]},
            "expected_route_id": "tailoring_policy",
            "expected_evidence": {
                "section_terms_any": ["agile", "tailoring", "review"],
                "terms_any": ["agile", "tailoring", "review", "mandatory", "cannot be tailored"],
            },
        },
    ]

    report = release0_route_rag_smoke_report(parsed_dir=parsed_dir, document_alias_map={"mi_pep": "doc-mi", "xp_pep": "doc-xp"}, cases=cases, top_k=2)

    assert report["schema_version"] == "release0-route-rag-smoke-v0.1"
    assert report["metrics"]["pass_rate"] == 1.0
    diagnostics = {item["case_id"]: item for item in report["case_diagnostics"]}
    assert diagnostics["qmp-route-rag"]["query_pack"]["schema_version"] == "route-query-pack-v0.1"
    assert diagnostics["qmp-route-rag"]["strategy_used"] == "deliverable_detail_route_retrieval"
    assert {hit["section_id"] for hit in diagnostics["qmp-route-rag"]["top_hits"]} == {"sec-qmp-contents", "sec-qmp-owner"}
    assert diagnostics["tailoring-route-rag"]["strategy_used"] == "tailoring_policy_route_retrieval"
    assert {hit["section_id"] for hit in diagnostics["tailoring-route-rag"]["top_hits"]} == {"sec-agile-tailorable", "sec-agile-mandatory"}
