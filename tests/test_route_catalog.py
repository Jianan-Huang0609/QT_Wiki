from __future__ import annotations


def test_route_catalog_covers_release0_routes_with_minimum_strategy_fields():
    from Tool.evals.release0_smoke import release0_smoke_cases
    from Tool.workflows.route_catalog import get_route_catalog

    catalog = get_route_catalog()
    release0_routes = {case["expected_route_id"] for case in release0_smoke_cases()}

    assert release0_routes.issubset(set(catalog))
    for route_id in release0_routes:
        entry = catalog[route_id]
        payload = entry.to_dict()
        assert payload["route_id"] == route_id
        assert payload["summary"]
        assert payload["query_terms"]
        assert payload["evidence_needs"]
        assert payload["answer_slots"]
        assert payload["risk_level"] in {"low", "medium", "high"}
        assert payload["citation_policy"] in {"required", "high_density", "per_document_required"}


def test_session_query_rewrite_tool_plan_and_answer_plan_use_route_catalog_fields():
    from App.api import _answer_plan_shape, _answer_plan_slot_defs, _session_query_rewrite, _session_retrieval_top_k, _session_tool_plan
    from Tool.workflows.answer import parse_question_intent
    from Tool.workflows.route_catalog import get_route_entry

    cases = [
        ("PEP 文档的流程如何操作？", "process_operation"),
        ("R4到R5之间需要完成哪些工作？", "stage_transition_work"),
        ("QMP需要包含哪些内容？谁负责撰写QMP？", "deliverable_detail"),
        ("采用敏捷方法开发，可以裁剪哪些评审？哪些评审不可被裁剪？", "tailoring_policy"),
    ]

    for question, route_id in cases:
        intent = parse_question_intent(question)
        entry = get_route_entry(route_id)
        rewrite = _session_query_rewrite(question, intent, {"route_id": route_id})
        tool_plan = _session_tool_plan(
            route_plan={"route_id": route_id},
            query_rewrite=rewrite,
            source_scope={"mode": "selected_docs", "document_ids": ["mi-pep"]},
            use_llm=False,
        )
        slot_defs = _answer_plan_slot_defs(route_id)

        assert entry is not None
        assert set(entry.query_terms).issubset(set(rewrite["route_terms"]))
        assert rewrite["excluded_terms"] == list(entry.excluded_terms)
        assert rewrite["reason"] == entry.rewrite_reason
        assert tool_plan["route_strategy"] == {
            "risk_level": entry.risk_level,
            "citation_policy": entry.citation_policy,
            "evidence_needs": list(entry.evidence_needs),
            "answer_shape": entry.answer_shape,
        }
        assert [slot["slot_id"] for slot in slot_defs] == [slot.slot_id for slot in entry.answer_slots]
        assert _answer_plan_shape(route_id) == entry.answer_shape
        assert _session_retrieval_top_k(4, {"route_id": route_id}) >= 12


def test_session_route_plan_exposes_catalog_policy_metadata():
    from App.api import _session_route_plan
    from Tool.workflows.answer import parse_question_intent
    from Tool.workflows.route_catalog import get_route_entry

    intent = parse_question_intent("QMP需要包含哪些内容？谁负责撰写QMP？")
    route_plan = _session_route_plan("QMP需要包含哪些内容？谁负责撰写QMP？", intent)
    entry = get_route_entry("deliverable_detail")

    assert entry is not None
    assert route_plan["route_id"] == entry.route_id
    assert route_plan["risk_level"] == entry.risk_level
    assert route_plan["citation_policy"] == entry.citation_policy
    assert route_plan["evidence_needs"] == list(entry.evidence_needs)