from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Callable

from Tool.evals.release0_smoke import release0_smoke_cases
from Tool.llm.client import ask_llm
from Tool.workflows.route_catalog import get_route_catalog
from Tool.workflows.router_shadow import (
    ROUTER_SHADOW_DIFF_SCHEMA_VERSION,
    build_llm_router_prompt,
    classify_intent_route_diff,
    parse_llm_router_output,
)

RouterCallable = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any] | str]
DEFAULT_ARTIFACT_PATH = Path("Design/review-artifacts/router-shadow-diff.md")


def build_azure_llm_router(*, config_path: str = "config/azure_gpt5_4_config.json") -> RouterCallable:
    def route(case: dict[str, Any], _rule_route: dict[str, Any]) -> str:
        return ask_llm(
            str(case.get("router_prompt") or ""),
            config_path=config_path,
            max_tokens=2500,
            temperature=0.2,
            top_p=0.6,
            system="Return only one valid JSON object. Do not include Markdown fences or explanations.",
        )

    return route


def release0_router_shadow_diff_report(
    *,
    router: RouterCallable | None = None,
    cases: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    eval_cases = cases or router_shadow_cases()
    diagnostics = [_case_diagnostic(case, router=router) for case in eval_cases]
    return {
        "schema_version": ROUTER_SHADOW_DIFF_SCHEMA_VERSION,
        "purpose": "Compare current rule route projection with LLM Router shadow output without changing production routing.",
        "metrics": _metrics(diagnostics),
        "classification_summary": _classification_summary(diagnostics),
        "case_diagnostics": diagnostics,
        "findings": [item for item in diagnostics if item["classification"] not in {"matched"}],
    }


def router_shadow_cases() -> list[dict[str, Any]]:
    selected_ids = {
        "r0-mi-r4-r5-transition",
        "r0-mi-qmp-deliverable",
        "r0-xp-agile-tailoring",
        "r0-mi-unknown-fallback",
        "r0-ct-mi-xp-stage-comparison",
    }
    cases = [case for case in release0_smoke_cases() if case.get("case_id") in selected_ids]
    cases.append(
        {
            "case_id": "r0-source-location-follow-up",
            "priority": "P0",
            "case_kind": "source_location_follow_up",
            "question": "在原文的哪里？",
            "source_scope": {"mode": "selected_docs", "document_aliases": ["ct_pep"]},
            "expected_route_id": "reference_lookup",
            "previous_context": {
                "is_follow_up": True,
                "is_source_location_follow_up": True,
                "previous_question": "R4到R5之间需要完成哪些工作？",
                "previous_citation_count": 3,
            },
            "source_location_guardrail_required": True,
            "manual_judgement": "Source-location follow-up must stay on previous citations and use program guardrail if LLM drifts.",
        }
    )
    return cases


def write_router_shadow_diff_artifact(
    report: dict[str, Any],
    *,
    output_path: str | Path = DEFAULT_ARTIFACT_PATH,
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_router_shadow_diff_markdown(report), encoding="utf-8")
    return path


def render_router_shadow_diff_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Router Shadow Diff",
        "",
        f"Schema: `{report.get('schema_version', '')}`",
        "",
        "## Summary",
        "",
        f"- Cases: {report.get('metrics', {}).get('case_count', 0)}",
        f"- Matched: {report.get('classification_summary', {}).get('matched', 0)}",
        f"- Findings: {len(report.get('findings', []))}",
        "",
        "## Cases",
        "",
    ]
    for item in report.get("case_diagnostics", []):
        rule_route = item.get("rule_route", {})
        llm_route = item.get("llm_route", {})
        lines.extend(
            [
                f"### {item.get('case_id', 'unknown')}",
                "",
                f"- Classification: `{item.get('classification', '')}`",
                f"- Expected: `{item.get('expected_route_id', '')}`",
                f"- Rule route: `{rule_route.get('primary_route', '')}`",
                f"- LLM route: `{llm_route.get('primary_route', '')}`",
                f"- Question: {item.get('question', '')}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _case_diagnostic(case: dict[str, Any], *, router: RouterCallable | None) -> dict[str, Any]:
    from App.api import _session_intent_route_shadow, _session_query_rewrite, _session_route_plan, _source_location_follow_up_route_plan
    from Tool.workflows.answer import parse_question_intent

    question = str(case.get("question", ""))
    intent = parse_question_intent(question)
    follow_up_context = dict(case.get("previous_context") or {})
    route_plan = _session_route_plan(question, intent)
    route_plan = _source_location_follow_up_route_plan(route_plan, follow_up_context)
    query_rewrite = _session_query_rewrite(question, intent, route_plan)
    route_plan = {**route_plan, "query_pack": query_rewrite.get("query_pack", {})}
    rule_route = _session_intent_route_shadow(route_plan=route_plan, intent=intent, follow_up_context=follow_up_context)
    llm_route = None
    router_error = ""
    prompt = build_llm_router_prompt(case, rule_route, _candidate_routes())
    if router is not None:
        try:
            llm_route = parse_llm_router_output(router({**case, "router_prompt": prompt}, rule_route))
        except Exception as exc:  # pragma: no cover - defensive runtime report path
            router_error = str(exc)
    diff = classify_intent_route_diff(case=case, rule_route=rule_route, llm_route=llm_route)
    return {
        **diff,
        "router_error": router_error,
        "prompt_preview": prompt[:1200],
    }


def _candidate_routes() -> list[dict[str, Any]]:
    return [
        {
            "route_id": entry.route_id,
            "summary": entry.summary,
            "evidence_needs": list(entry.evidence_needs),
            "answer_slots": [slot.slot_id for slot in entry.answer_slots],
            "risk_level": entry.risk_level,
            "citation_policy": entry.citation_policy,
        }
        for entry in get_route_catalog().values()
    ]


def _metrics(diagnostics: list[dict[str, Any]]) -> dict[str, Any]:
    case_count = len(diagnostics)
    matched = len([item for item in diagnostics if item.get("classification") == "matched"])
    return {
        "case_count": case_count,
        "matched_count": matched,
        "finding_count": case_count - matched,
        "match_rate": round(matched / case_count, 4) if case_count else 0.0,
    }


def _classification_summary(diagnostics: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(str(item.get("classification", "unknown")) for item in diagnostics)
    keys = ("matched", "llm_improved", "llm_regressed", "entity_missing", "fallback_mismatch", "source_location_risk", "not_run")
    return {key: int(counts.get(key, 0)) for key in keys}