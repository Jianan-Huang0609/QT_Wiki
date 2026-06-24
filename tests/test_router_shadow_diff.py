from __future__ import annotations


def test_router_shadow_diff_report_classifies_injected_llm_outputs():
    from Tool.evals.router_shadow import release0_router_shadow_diff_report
    from Tool.workflows.intent_route import project_rule_route_to_intent_route

    def fake_router(case, rule_route):
        case_id = case["case_id"]
        if case_id == "r0-mi-qmp-deliverable":
            return project_rule_route_to_intent_route(
                route_id="generic_rag",
                question_type="deliverable_detail",
                normalized_terms={"deliverable": ["QMP"]},
                route_match=0.9,
                evidence_likely=0.5,
            )
        if case_id == "r0-source-location-follow-up":
            return project_rule_route_to_intent_route(
                route_id="process_operation",
                question_type="reference_lookup",
                normalized_terms={},
                needs_previous_context=False,
                route_match=0.88,
                evidence_likely=0.7,
            )
        return rule_route

    report = release0_router_shadow_diff_report(router=fake_router)
    diagnostics = {item["case_id"]: item for item in report["case_diagnostics"]}

    assert report["schema_version"] == "router-shadow-diff-v0.1"
    assert report["metrics"]["case_count"] == 6
    assert diagnostics["r0-mi-r4-r5-transition"]["classification"] == "matched"
    assert diagnostics["r0-mi-qmp-deliverable"]["classification"] == "fallback_mismatch"
    assert diagnostics["r0-source-location-follow-up"]["classification"] == "source_location_risk"
    assert report["classification_summary"]["matched"] >= 1
    assert report["classification_summary"]["fallback_mismatch"] == 1
    assert report["classification_summary"]["source_location_risk"] == 1


def test_router_shadow_diff_extracts_json_and_marks_entity_missing():
    from Tool.workflows.router_shadow import classify_intent_route_diff, parse_llm_router_output
    from Tool.workflows.intent_route import project_rule_route_to_intent_route

    rule_route = project_rule_route_to_intent_route(
        route_id="stage_transition_work",
        question_type="stage_transition_work",
        normalized_terms={"stage": ["R4", "R5"]},
    )
    llm_route = parse_llm_router_output(
        "prefix {\"schema_version\": \"intent-route-v0.2\", \"primary_route\": \"stage_transition_work\", \"secondary_routes\": [], \"question_type\": \"stage_transition_work\", \"needs_previous_context\": false, \"confidence\": {\"route_match\": 0.91, \"evidence_likely\": 0.7}, \"entities\": [], \"_extensions\": {}} suffix"
    )
    diff = classify_intent_route_diff(
        case={"case_id": "demo", "expected_route_id": "stage_transition_work"},
        rule_route=rule_route,
        llm_route=llm_route,
    )

    assert llm_route["guardrail"]["status"] == "passed"
    assert diff["classification"] == "entity_missing"
    assert "stage_transition" in diff["details"]["missing_entity_types"]