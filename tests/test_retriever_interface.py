from __future__ import annotations

from Tool.chunking.section_chunks import SectionChunk


def _chunk(
    chunk_id: str,
    *,
    document_id: str = "ct-pep",
    section_id: str = "sec-r2",
    section_title: str = "5.3.2 R2 Responsibilities",
    text: str = "At R2, the Product Owner prepares QMP evidence.",
    signals: list[str] | None = None,
) -> SectionChunk:
    return SectionChunk(
        chunk_id=chunk_id,
        document_id=document_id,
        document_title=document_id.upper(),
        file_name=f"{document_id}.pdf",
        section_id=section_id,
        section_title=section_title,
        section_path=[section_title],
        chunk_type="section",
        text=text,
        quote=text[:500],
        source_refs=[
            {
                "document_id": document_id,
                "fragment_id": f"frag-{chunk_id}",
                "file_name": f"{document_id}.pdf",
                "section_id": section_id,
                "section_title": section_title,
                "anchor_label": "p.21",
                "anchors": {"page": 21},
                "quote": text,
            }
        ],
        anchors={"pages": [21]},
        signals=signals or ["stage_r2", "role_product_owner", "deliverable_qmp"],
    )


def test_rule_section_retriever_preserves_existing_retrieval_result_contract():
    from Tool.retrieval.retrievers import RuleSectionRetriever

    chunks = [
        _chunk("ct-r2"),
        _chunk(
            "mi-r2",
            document_id="mi-pep",
            text="At R2, the Project Manager confirms system readiness.",
            signals=["stage_r2", "role_project_manager"],
        ),
    ]

    result = RuleSectionRetriever().retrieve(
        "R2 Product Owner QMP evidence",
        chunks,
        source_scope={"mode": "selected_docs", "document_ids": ["ct-pep"]},
        top_k=3,
    )

    assert result.strategy_used == "scoped_section_retrieval"
    assert result.source_scope == {"mode": "selected_docs", "document_ids": ["ct-pep"]}
    assert result.hits[0].chunk.chunk_id == "ct-r2"
    assert result.evidence_coverage["documents"] == ["ct-pep"]
    assert "rule_section_retriever" in result.trace[-1]


def test_full_text_retriever_returns_same_retrieval_result_shape_for_keyword_questions():
    from Tool.retrieval.retrievers import FullTextRetriever

    chunks = [
        _chunk(
            "regulatory-plan",
            section_id="sec-716",
            section_title="7.16 Regulatory Approval Plan",
            text="The regulatory approval plan contains submission evidence and authority milestones.",
            signals=["section_7_16", "deliverable_submission_package"],
        ),
        _chunk("r2-general"),
    ]

    result = FullTextRetriever().retrieve("7.16 regulatory approval evidence", chunks, top_k=2)

    assert result.strategy_used == "full_text_retrieval"
    assert result.hits[0].chunk.chunk_id == "regulatory-plan"
    assert "regulatory" in result.hits[0].matched_terms
    assert result.to_dict()["hits"][0]["chunk"]["source_refs"]


def test_vector_retriever_uses_injected_embedding_similarity_without_new_dependencies():
    from Tool.retrieval.retrievers import VectorRetriever

    chunks = [
        _chunk("ct-r2"),
        _chunk(
            "regulatory-plan",
            section_id="sec-716",
            section_title="7.16 Regulatory Approval Plan",
            text="The regulatory approval plan contains submission evidence and authority milestones.",
            signals=["section_7_16", "deliverable_submission_package"],
        ),
    ]

    def fake_embed(text: str) -> list[float]:
        normalized = text.casefold()
        if "role guidance" in normalized or "product owner" in normalized or "qmp" in normalized:
            return [1.0, 0.0]
        if "regulatory" in normalized:
            return [0.0, 1.0]
        return [0.0, 0.0]

    result = VectorRetriever(embed_text=fake_embed).retrieve("role guidance for QMP", chunks, top_k=2)

    assert result.strategy_used == "vector_retrieval"
    assert result.hits[0].chunk.chunk_id == "ct-r2"
    assert result.hits[0].score == 1.0
    assert "qmp" in result.hits[0].matched_terms
    assert "vector similarity scoring" in result.trace[-1]


def test_hybrid_retriever_fuses_backends_with_deterministic_trace():
    from Tool.retrieval.retrievers import FullTextRetriever, HybridRetriever, RuleSectionRetriever

    chunks = [
        _chunk("ct-r2"),
        _chunk(
            "regulatory-plan",
            section_id="sec-716",
            section_title="7.16 Regulatory Approval Plan",
            text="The regulatory approval plan contains submission evidence and authority milestones.",
            signals=["section_7_16", "deliverable_submission_package"],
        ),
    ]
    retriever = HybridRetriever([RuleSectionRetriever(), FullTextRetriever()])

    result = retriever.retrieve("7.16 regulatory approval evidence", chunks, top_k=2)

    assert result.strategy_used == "hybrid_retrieval"
    assert result.hits[0].chunk.chunk_id == "regulatory-plan"
    assert result.evidence_coverage["hit_count"] == 2
    assert "rrf fusion" in result.trace[-1]
    assert result.trace[0] == "hybrid retriever fanout: rule_section, full_text"


def test_retrieval_eval_can_run_against_a_pluggable_retriever():
    from Tool.evals.retrieval_eval import evaluate_retrieval_cases
    from Tool.retrieval.retrievers import FullTextRetriever, HybridRetriever, RuleSectionRetriever

    chunks = [
        _chunk("ct-r2"),
        _chunk(
            "regulatory-plan",
            section_id="sec-716",
            section_title="7.16 Regulatory Approval Plan",
            text="The regulatory approval plan contains submission evidence and authority milestones.",
            signals=["section_7_16", "deliverable_submission_package"],
        ),
    ]
    report = evaluate_retrieval_cases(
        chunks,
        [
            {
                "case_id": "regulatory-plan",
                "question": "7.16 regulatory approval evidence",
                "expected_section_terms_any": ["Regulatory Approval Plan"],
                "expected_terms_any": ["submission evidence"],
            }
        ],
        top_k=2,
        retriever=HybridRetriever([RuleSectionRetriever(), FullTextRetriever()]),
    )

    assert report["eval_summary"]["fail"] == 0
    assert report["cases"][0]["strategy_used"] == "hybrid_retrieval"