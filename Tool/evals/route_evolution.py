from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Callable

from Tool.workflows.router_shadow import parse_llm_router_output

RouterCallable = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any] | str]
DEFAULT_ARTIFACT_PATH = Path("Design/review-artifacts/route-evolution-prep-readiness.md")


def route_evolution_eval_report(*, router: RouterCallable | None = None, cases: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    eval_cases = cases or prep_readiness_route_evolution_cases()
    diagnostics = [_case_diagnostic(case, router=router) for case in eval_cases]
    return {
        "schema_version": "route-evolution-eval-v0.1",
        "target_family": "prep_readiness_questions",
        "purpose": "Track whether open preparation/readiness questions should evolve from generic fallback into process-operation route coverage.",
        "metrics": _metrics(diagnostics),
        "recommendation": _recommendation(diagnostics),
        "case_diagnostics": diagnostics,
        "findings": [item for item in diagnostics if item["classification"] != "matched"],
    }


def prep_readiness_route_evolution_cases() -> list[dict[str, Any]]:
    return [
        {
            "case_id": "prep-quality-gate-omissions",
            "question": "MI PEP 里项目启动前有哪些容易被遗漏但影响后续质量门的准备事项？",
            "expected_family": "prep_readiness_questions",
            "manual_judgement": "Should identify preparation/readiness evidence with bounded uncertainty.",
        },
        {
            "case_id": "prep-before-start",
            "question": "MI PEP 项目启动前需要提前准备什么？",
            "expected_family": "prep_readiness_questions",
            "manual_judgement": "Should route consistently with other preparation questions.",
        },
        {
            "case_id": "prep-attention-items",
            "question": "MI PEP 项目启动前有哪些注意事项？",
            "expected_family": "prep_readiness_questions",
            "manual_judgement": "Should avoid oscillating between overview and fallback for the same intent family.",
        },
        {
            "case_id": "prep-r2-omissions",
            "question": "MI PEP R2 前有哪些容易遗漏的准备事项？",
            "expected_family": "prep_readiness_questions",
            "manual_judgement": "Should preserve stage entity while deciding whether process_operation or generic_rag owns this family.",
        },
    ]


def write_route_evolution_artifact(report: dict[str, Any], *, output_path: str | Path = DEFAULT_ARTIFACT_PATH) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_route_evolution_markdown(report), encoding="utf-8")
    return path


def render_route_evolution_markdown(report: dict[str, Any]) -> str:
    metrics = report.get("metrics", {})
    recommendation = report.get("recommendation", {})
    lines = [
        "# Route Evolution: Prep Readiness Questions",
        "",
        f"Schema: `{report.get('schema_version', '')}`",
        "",
        "## Summary",
        "",
        f"- Cases: {metrics.get('case_count', 0)}",
        f"- Rule route count: {metrics.get('rule_route_count', 0)}",
        f"- Rule routes: `{metrics.get('rule_route_distribution', {})}`",
        f"- LLM routes: `{metrics.get('llm_route_distribution', {})}`",
        f"- Recommendation: `{recommendation.get('status', '')}`",
        "",
        "## Cases",
        "",
    ]
    for item in report.get("case_diagnostics", []):
        lines.extend(
            [
                f"### {item.get('case_id', 'unknown')}",
                "",
                f"- Classification: `{item.get('classification', '')}`",
                f"- Rule route: `{item.get('rule_route', {}).get('primary_route', '')}`",
                f"- LLM route: `{item.get('llm_route', {}).get('primary_route', '')}`",
                f"- Question: {item.get('question', '')}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _case_diagnostic(case: dict[str, Any], *, router: RouterCallable | None) -> dict[str, Any]:
    from App.api import _session_intent_route_shadow, _session_query_rewrite, _session_route_plan
    from Tool.workflows.answer import parse_question_intent

    question = str(case.get("question", ""))
    intent = parse_question_intent(question)
    route_plan = _session_route_plan(question, intent)
    query_rewrite = _session_query_rewrite(question, intent, route_plan)
    route_plan = {**route_plan, "query_pack": query_rewrite.get("query_pack", {})}
    rule_route = _session_intent_route_shadow(route_plan=route_plan, intent=intent, follow_up_context={})
    llm_route = None
    router_error = ""
    if router is not None:
        try:
            llm_route = parse_llm_router_output(router(case, rule_route))
        except Exception as exc:  # pragma: no cover - defensive artifact path
            router_error = str(exc)
    classification = _classification(rule_route, llm_route)
    return {
        "case_id": case.get("case_id", "unknown"),
        "question": question,
        "rule_route": rule_route,
        "llm_route": llm_route or {},
        "classification": classification,
        "router_error": router_error,
    }


def _classification(rule_route: dict[str, Any], llm_route: dict[str, Any] | None) -> str:
    if llm_route is None:
        return "not_run"
    if rule_route.get("primary_route") == llm_route.get("primary_route"):
        return "matched"
    return "route_mismatch"


def _metrics(diagnostics: list[dict[str, Any]]) -> dict[str, Any]:
    rule_routes = Counter(str(item.get("rule_route", {}).get("primary_route", "")) for item in diagnostics)
    llm_routes = Counter(str(item.get("llm_route", {}).get("primary_route", "")) for item in diagnostics if item.get("llm_route"))
    return {
        "case_count": len(diagnostics),
        "rule_route_distribution": dict(rule_routes),
        "rule_route_count": len(rule_routes),
        "llm_route_distribution": dict(llm_routes),
    }


def _recommendation(diagnostics: list[dict[str, Any]]) -> dict[str, Any]:
    rule_routes = {str(item.get("rule_route", {}).get("primary_route", "")) for item in diagnostics}
    status = "needs_route_decision" if len(rule_routes) > 1 else "stable_rule_route"
    return {
        "status": status,
        "candidate_routes": ["process_operation", "generic_rag"],
        "reason": "prep/readiness variants currently oscillate across rule routes" if status == "needs_route_decision" else "prep/readiness variants currently share one rule route",
    }