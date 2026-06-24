from __future__ import annotations


def test_route_evolution_eval_tracks_preparation_question_route_instability():
    from Tool.evals.route_evolution import route_evolution_eval_report

    report = route_evolution_eval_report()

    assert report["schema_version"] == "route-evolution-eval-v0.1"
    assert report["target_family"] == "prep_readiness_questions"
    assert report["metrics"]["case_count"] >= 3
    assert report["metrics"]["rule_route_count"] >= 2
    assert report["recommendation"]["status"] == "needs_route_decision"
    assert "process_operation" in report["recommendation"]["candidate_routes"]


def test_route_evolution_eval_records_injected_llm_shadow_preference():
    from Tool.evals.route_evolution import route_evolution_eval_report
    from Tool.workflows.intent_route import project_rule_route_to_intent_route

    def fake_router(case, _rule_route):
        return project_rule_route_to_intent_route(
            route_id="process_operation",
            question_type="prep_readiness_questions",
            normalized_terms={"stage": ["R2"], "deliverable": ["QMP"]},
            route_match=0.82,
            evidence_likely=0.72,
            extensions={"case_id": case["case_id"]},
        )

    report = route_evolution_eval_report(router=fake_router)

    assert report["metrics"]["llm_route_distribution"] == {"process_operation": report["metrics"]["case_count"]}
    assert all(item["llm_route"]["primary_route"] == "process_operation" for item in report["case_diagnostics"])
    assert any(item["classification"] == "route_mismatch" for item in report["case_diagnostics"])