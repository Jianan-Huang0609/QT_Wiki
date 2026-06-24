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


def test_query_rewrite_outputs_route_query_pack_for_evidence_patterns():
    from App.api import _session_query_rewrite, _session_route_plan
    from Tool.workflows.answer import parse_question_intent

    cases = [
        (
            "CT PEP 中 R4 到 R5 之间需要完成哪些工作？",
            "stage_transition_work",
            {"work_items", "reviews_deliverables", "exit_readiness"},
            {"product validation", "reliability engineering report", "system stability test summary", "GSPR", "STED"},
            {"PEP", "document", "procedure"},
            {"purpose and scope", "provisional solution"},
        ),
        (
            "MI PEP 中 QMP 需要包含哪些内容？谁负责撰写 QMP？",
            "deliverable_detail",
            {"required_contents", "owner_author", "review_approval"},
            {"QMP", "quality management plan", "required contents", "owner", "author"},
            {"PEP", "document", "procedure"},
            {"purpose and scope", "provisional solution"},
        ),
        (
            "XP PEP 采用敏捷方法开发，可以裁剪哪些评审？哪些评审不可被裁剪？",
            "tailoring_policy",
            {"agile_applicability", "tailorable_reviews", "non_tailorable_reviews"},
            {"agile", "tailoring", "review", "mandatory review", "cannot be tailored"},
            {"PEP", "document", "procedure"},
            {"purpose and scope", "provisional solution", "task and responsibilities"},
        ),
    ]

    for question, route_id, required_slot_ids, expected_terms, weak_terms, downrank_terms in cases:
        intent = parse_question_intent(question)
        route_plan = _session_route_plan(question, intent)
        rewrite = _session_query_rewrite(question, intent, route_plan)
        query_pack = rewrite["query_pack"]

        assert route_plan["route_id"] == route_id
        assert query_pack["schema_version"] == "route-query-pack-v0.1"
        assert query_pack["primary_query"] == rewrite["rewritten_query"]
        assert required_slot_ids.issubset({item["slot_id"] for item in query_pack["slot_queries"]})
        assert expected_terms.intersection(set(query_pack["route_terms"] + query_pack["must_terms"] + query_pack["support_terms"]))
        assert weak_terms.issubset(set(query_pack["weak_terms"]))
        assert downrank_terms.issubset(set(query_pack["downrank_terms"]))
        for slot_query in query_pack["slot_queries"]:
            assert slot_query["query"].startswith(question)
            assert slot_query["terms"]


def test_intent_route_v02_round_trips_every_catalog_entry_and_guardrails_invalid_routes():
    from Tool.workflows.intent_route import build_catalog_intent_route, guard_intent_route_v02
    from Tool.workflows.route_catalog import get_route_catalog

    catalog = get_route_catalog()

    assert len(catalog) == 13
    for route_id, entry in catalog.items():
        route = build_catalog_intent_route(entry)

        assert route["schema_version"] == "intent-route-v0.2"
        assert route["primary_route"] == route_id
        assert route["route_catalog"] == entry.to_dict()
        assert route["confidence"] == {"route_match": 1.0, "evidence_likely": 1.0}
        assert guard_intent_route_v02(route)["guardrail"]["status"] == "passed"

    invalid = build_catalog_intent_route(catalog["process_operation"])
    invalid["primary_route"] = "not_registered"
    guarded = guard_intent_route_v02(invalid)

    assert guarded["primary_route"] == "generic_rag"
    assert guarded["guardrail"]["status"] == "fallback"
    assert "invalid_primary_route" in guarded["guardrail"]["reasons"]

    low_confidence = build_catalog_intent_route(catalog["process_operation"])
    low_confidence["confidence"]["route_match"] = 0.2
    guarded_low = guard_intent_route_v02(low_confidence)

    assert guarded_low["primary_route"] == "generic_rag"
    assert "low_route_match" in guarded_low["guardrail"]["reasons"]


def test_intent_route_v02_projects_rule_route_entities_without_changing_route_choice():
    from App.api import _session_intent_route_shadow, _session_route_plan
    from Tool.workflows.answer import parse_question_intent

    question = "CT PEP 中 R4 到 R5 之间需要完成哪些工作？"
    intent = parse_question_intent(question)
    route_plan = _session_route_plan(question, intent)
    shadow = _session_intent_route_shadow(route_plan=route_plan, intent=intent, follow_up_context={})

    assert route_plan["route_id"] == "stage_transition_work"
    assert shadow["schema_version"] == "intent-route-v0.2"
    assert shadow["primary_route"] == "stage_transition_work"
    assert shadow["question_type"] == "stage_transition_work"
    assert {entity["type"] for entity in shadow["entities"]}.issuperset({"stage_transition", "bu_scope_hint"})
    assert shadow["entities"][0]["from_stage"] == "R4"
    assert shadow["entities"][0]["to_stage"] == "R5"
    assert shadow["route_catalog"]["route_id"] == "stage_transition_work"
    assert shadow["guardrail"] == {"status": "passed", "reasons": [], "applied_fallback": False}