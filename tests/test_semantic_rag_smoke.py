from __future__ import annotations

from unittest.mock import patch


def test_azure_embedding_adapter_posts_to_embeddings_endpoint():
    from Tool.retrieval.embeddings import AzureEmbeddingAdapter

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {"data": [{"embedding": [0.1, 0.2, 0.3]}]}

    with patch("Tool.retrieval.embeddings.requests.post", return_value=Response()) as post:
        adapter = AzureEmbeddingAdapter(
            endpoint="https://example.test",
            deployment="text-embedding-3-small",
            api_key="test-key",
            api_version="2024-02-01",
        )
        vector = adapter.embed_text("QMP owner responsibility")

    assert vector == [0.1, 0.2, 0.3]
    args, kwargs = post.call_args
    assert args[0] == "https://example.test/openai/deployments/text-embedding-3-small/embeddings"
    assert kwargs["json"] == {"input": "QMP owner responsibility"}
    assert kwargs["headers"]["api-key"] == "test-key"
    assert kwargs["params"] == {"api-version": "2024-02-01"}


def test_semantic_rag_smoke_compares_lexical_and_semantic_with_injected_embeddings():
    from Tool.evals.semantic_rag_smoke import semantic_rag_smoke_report
    from Tool.chunking.section_chunks import SectionChunk

    def chunk(chunk_id: str, text: str) -> SectionChunk:
        return SectionChunk(
            chunk_id=chunk_id,
            document_id="mi-pep",
            document_title="MI PEP",
            file_name="MI PEP.pdf",
            section_id=chunk_id,
            section_title=text.split(".")[0],
            section_path=[text.split(".")[0]],
            chunk_type="section",
            text=text,
            quote=text,
            source_refs=[{"document_id": "mi-pep", "fragment_id": f"frag-{chunk_id}", "file_name": "MI PEP.pdf", "anchor_label": "p.1", "quote": text}],
            anchors={"page": 1},
            signals=[],
        )

    chunks = [
        chunk("generic", "Purpose and scope. This process document describes general workflow."),
        chunk("qmp-owner", "Quality management plan. The project manager is responsible for authoring the QMP and maintaining required contents."),
    ]
    cases = [
        {
            "case_id": "semantic-qmp-owner",
            "question": "MI PEP 中 QMP 谁负责撰写？",
            "source_scope": {"mode": "selected_docs", "document_ids": ["mi-pep"]},
            "expected_route_id": "deliverable_detail",
            "expected_terms_any": ["authoring", "responsible"],
            "expected_section_terms_any": ["Quality management plan"],
        }
    ]

    def fake_embed(text: str) -> list[float]:
        normalized = text.casefold()
        if "谁负责" in normalized or "authoring" in normalized or "responsible" in normalized or "quality management plan" in normalized:
            return [1.0, 0.0]
        return [0.0, 1.0]

    report = semantic_rag_smoke_report(chunks=chunks, cases=cases, embed_text=fake_embed)

    assert report["schema_version"] == "semantic-rag-smoke-v0.1"
    assert report["embedding"]["status"] == "available"
    assert set(report["backend_reports"]) == {"lexical_baseline", "semantic_hybrid", "route_gated_semantic"}
    assert report["backend_reports"]["semantic_hybrid"]["metrics"]["recall_at_8"] == 1.0
    assert report["backend_reports"]["route_gated_semantic"]["metrics"]["recall_at_8"] == 1.0
    assert report["case_diagnostics"][0]["semantic_top_hit"]["chunk_id"] == "qmp-owner"
    assert report["case_diagnostics"][0]["route_gated_semantic_enabled"] is True


def test_route_gated_semantic_keeps_role_and_reference_routes_on_lexical_baseline():
    from Tool.chunking.section_chunks import SectionChunk
    from Tool.evals.semantic_rag_smoke import semantic_rag_smoke_report

    def chunk(chunk_id: str, text: str) -> SectionChunk:
        return SectionChunk(
            chunk_id=chunk_id,
            document_id="mi-pep",
            document_title="MI PEP",
            file_name="MI PEP.pdf",
            section_id=chunk_id,
            section_title=text.split(".")[0],
            section_path=[text.split(".")[0]],
            chunk_type="section",
            text=text,
            quote=text,
            source_refs=[{"document_id": "mi-pep", "fragment_id": f"frag-{chunk_id}", "file_name": "MI PEP.pdf", "anchor_label": "p.1", "quote": text}],
            anchors={"page": 1},
            signals=[],
        )

    chunks = [
        chunk("lexical-role", "R2 Planning Product Owner PO responsible deliverable."),
        chunk("semantic-distractor", "General preparation quality gate readiness review evidence."),
    ]
    cases = [
        {
            "case_id": "role-route-stays-lexical",
            "question": "MI PEP 里 R2 阶段作为 PO 应该做什么？",
            "source_scope": {"mode": "selected_docs", "document_ids": ["mi-pep"]},
            "expected_route_id": "role_action_guidance",
            "expected_terms_any": ["Product Owner", "responsible"],
            "expected_section_terms_any": ["R2"],
        }
    ]
    embedded_texts: list[str] = []

    def fake_embed(text: str) -> list[float]:
        embedded_texts.append(text)
        if "semantic rag smoke probe" in text:
            return [1.0, 0.0]
        if "preparation" in text.casefold() or "quality gate" in text.casefold():
            return [1.0, 0.0]
        return [0.0, 1.0]

    report = semantic_rag_smoke_report(chunks=chunks, cases=cases, embed_text=fake_embed)
    item = report["case_diagnostics"][0]

    assert item["actual_route_id"] == "role_action_guidance"
    assert item["route_gated_semantic_enabled"] is False
    assert item["route_gated_top_hit"]["chunk_id"] == item["lexical_top_hit"]["chunk_id"] == "lexical-role"
    assert embedded_texts[0] == "semantic rag smoke probe"
    assert len(embedded_texts) == 4


def test_semantic_rag_smoke_falls_back_when_embedding_endpoint_fails():
    from Tool.evals.semantic_rag_smoke import semantic_rag_smoke_report

    def failing_embed(_text: str) -> list[float]:
        raise RuntimeError("embedding endpoint unavailable")

    report = semantic_rag_smoke_report(chunks=[], cases=[], embed_text=failing_embed)

    assert report["embedding"]["status"] == "failed"
    assert "embedding endpoint unavailable" in report["embedding"]["error"]
    assert report["backend_reports"]["semantic_hybrid"]["fallback_used"] is True
    assert report["backend_reports"]["route_gated_semantic"]["fallback_used"] is True