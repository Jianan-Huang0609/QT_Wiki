from __future__ import annotations

from Tool.chunking.section_chunks import SectionChunk
from Tool.parsers.fusion import FusionDecision, VisualCandidate, build_parser_fusion_metadata


def _chunk(
    chunk_id: str,
    *,
    section_id: str = "sec-r2",
    section_title: str = "5.3.2 R2 Responsibilities",
    text: str = "At R2, the Product Owner prepares QMP evidence.",
    signals: list[str] | None = None,
) -> SectionChunk:
    return SectionChunk(
        chunk_id=chunk_id,
        document_id="ct-pep",
        document_title="CT PEP",
        file_name="ct.pdf",
        section_id=section_id,
        section_title=section_title,
        section_path=[section_title],
        chunk_type="section",
        text=text,
        quote=text[:500],
        source_refs=[
            {
                "document_id": "ct-pep",
                "fragment_id": f"frag-{chunk_id}",
                "file_name": "ct.pdf",
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


def test_fusion_eval_reports_provider_contribution_and_low_confidence_decisions():
    from Tool.evals.fusion_eval import evaluate_parser_fusion_metadata

    metadata = build_parser_fusion_metadata(
        providers=["pypdf_fast_text", "docling", "vlm"],
        visual_candidates=[
            VisualCandidate(
                candidate_id="visual-1",
                provider="vlm",
                candidate_type="figure_description",
                text="R2 flow diagram.",
                anchors={"page": 18, "bbox": [1, 2, 3, 4]},
                confidence=0.93,
                review_status="auto_accepted",
            )
        ],
        fusion_decisions=[
            FusionDecision(
                decision_id="fusion-low",
                decision_type="merge_blocks",
                selected_block_ids=["a", "b"],
                confidence=0.48,
                output_target="section_candidate",
            )
        ],
        canonical_output={"sections": 1, "fragments": 1, "tables": 0, "figures": 1},
    )

    report = evaluate_parser_fusion_metadata(metadata)

    assert report["metrics"]["provider_count"] == 3
    assert report["metrics"]["visual_candidate_count"] == 1
    assert report["metrics"]["low_confidence_decision_count"] == 1
    assert report["eval_summary"]["warn"] == 1
    assert report["findings"][0]["eval_id"] == "F1-01"
    assert report["findings"][1]["eval_id"] == "F2-01"
    assert report["findings"][1]["details"]["low_confidence_decision_ids"] == ["fusion-low"]


def test_retrieval_eval_compares_pluggable_backends():
    from Tool.evals.retrieval_eval import compare_retrieval_backends
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
    report = compare_retrieval_backends(
        chunks,
        [
            {
                "case_id": "r2-po",
                "question": "R2 Product Owner QMP evidence",
                "expected_section_terms_any": ["R2 Responsibilities"],
                "expected_terms_any": ["Product Owner", "QMP"],
            },
            {
                "case_id": "regulatory-plan",
                "question": "7.16 regulatory approval evidence",
                "expected_section_terms_any": ["Regulatory Approval Plan"],
                "expected_terms_any": ["submission evidence"],
            },
        ],
        retrievers={
            "rule": RuleSectionRetriever(),
            "hybrid": HybridRetriever([RuleSectionRetriever(), FullTextRetriever()]),
        },
        top_k=2,
    )

    assert report["schema_version"] == "retrieval-backend-comparison-v0.1"
    assert set(report["backends"]) == {"rule", "hybrid"}
    assert report["backends"]["hybrid"]["metrics"]["case_count"] == 2
    assert report["best_backend"]["name"] in {"rule", "hybrid"}
    assert report["findings"][0]["eval_id"] == "R2-01"


def test_answer_eval_flags_missing_citations_and_unsupported_claims():
    from Tool.evals.answer_eval import evaluate_answer_grounding

    package = {
        "evidence_items": [
            {
                "evidence_id": "ev-1",
                "document_id": "ct-pep",
                "anchor_label": "p.21",
                "quote": "At R2, the Product Owner prepares QMP evidence.",
                "source_refs": [{"document_id": "ct-pep", "anchor_label": "p.21"}],
            }
        ],
        "missing_evidence": [],
    }

    cited = evaluate_answer_grounding("Product Owner prepares QMP evidence. [ev-1]", package)
    uncited = evaluate_answer_grounding("Product Owner prepares QMP evidence.", package)
    unsupported = evaluate_answer_grounding("Product Owner approves every deliverable.", {"evidence_items": []})

    assert cited["eval_summary"]["fail"] == 0
    assert uncited["eval_summary"]["fail"] == 1
    assert uncited["findings"][0]["eval_id"] == "A1-01"
    assert unsupported["findings"][0]["eval_id"] == "A2-01"