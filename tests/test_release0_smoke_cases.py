from __future__ import annotations

from pathlib import Path


def test_release0_smoke_catalog_has_required_case_contract():
    from Tool.evals.release0_smoke import release0_smoke_catalog

    catalog = release0_smoke_catalog()
    cases = catalog["cases"]
    case_ids = [case["case_id"] for case in cases]

    assert catalog["schema_version"] == "release0-smoke-cases-v0.1"
    assert len(cases) >= 8
    assert len(case_ids) == len(set(case_ids))

    for case in cases:
        assert case["priority"] in {"P0", "P1"}
        assert case["question"].strip()
        assert case["source_scope"]["mode"] in {"selected_docs", "multi_docs"}
        assert case["source_scope"]["document_aliases"]
        assert case["expected_route_id"].strip()
        assert case["min_citation_count"] >= 1
        assert case["expected_evidence"]["terms_any"] or case["expected_evidence"]["section_terms_any"]
        assert case["manual_judgement"].strip()
        assert case["failure_record"]["path"] == "Design/review-artifacts/release0-smoke-failures.md"
        assert case["failure_record"]["section"].strip()


def test_release0_smoke_catalog_covers_sources_routes_and_failure_log():
    from Tool.evals.release0_smoke import release0_smoke_catalog

    repo_root = Path(__file__).resolve().parents[1]
    catalog = release0_smoke_catalog()
    cases = catalog["cases"]

    source_aliases = {alias for case in cases for alias in case["source_scope"]["document_aliases"]}
    route_ids = {case["expected_route_id"] for case in cases}
    case_kinds = {case["case_kind"] for case in cases}

    assert {"ct_pep", "mi_pep", "xp_pep"}.issubset(source_aliases)
    assert {
        "process_operation",
        "role_action_guidance",
        "reference_lookup",
        "stage_transition_work",
        "deliverable_detail",
        "tailoring_policy",
        "generic_rag",
        "bu_comparison",
    }.issubset(route_ids)
    assert {"single_doc", "unknown_fallback", "multi_doc_comparison"}.issubset(case_kinds)

    for case in cases:
        assert (repo_root / case["failure_record"]["path"]).exists()