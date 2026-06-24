from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from Tool.workflows.intent_route import INTENT_ROUTE_SCHEMA_VERSION, guard_intent_route_v02


ROUTER_SHADOW_DIFF_SCHEMA_VERSION = "router-shadow-diff-v0.1"


def parse_llm_router_output(output: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(output, dict):
        return guard_intent_route_v02(output)
    text = str(output or "").strip()
    payload = _first_json_object(text)
    return guard_intent_route_v02(payload)


def classify_intent_route_diff(
    *,
    case: dict[str, Any],
    rule_route: dict[str, Any],
    llm_route: dict[str, Any] | None,
) -> dict[str, Any]:
    if llm_route is None:
        return _diff_payload(case, rule_route, None, "not_run", {"reason": "llm router was not executed"})

    expected_route = str(case.get("expected_route_id") or "")
    rule_primary = str(rule_route.get("primary_route") or "")
    llm_primary = str(llm_route.get("primary_route") or "")
    details: dict[str, Any] = {}

    if _is_source_location_risk(case, llm_route):
        return _diff_payload(case, rule_route, llm_route, "source_location_risk", {"reason": "source-location follow-up needs program guardrail"})
    if (rule_primary == "generic_rag") != (llm_primary == "generic_rag"):
        return _diff_payload(case, rule_route, llm_route, "fallback_mismatch", {"rule_primary_route": rule_primary, "llm_primary_route": llm_primary})
    if expected_route and rule_primary != expected_route and llm_primary == expected_route:
        return _diff_payload(case, rule_route, llm_route, "llm_improved", {"expected_route_id": expected_route})
    if expected_route and rule_primary == expected_route and llm_primary != expected_route:
        return _diff_payload(case, rule_route, llm_route, "llm_regressed", {"expected_route_id": expected_route})
    if llm_route.get("guardrail", {}).get("status") == "fallback" and rule_route.get("guardrail", {}).get("status") != "fallback":
        return _diff_payload(case, rule_route, llm_route, "llm_regressed", {"guardrail": llm_route.get("guardrail")})

    missing_entity_types = _missing_entity_types(rule_route, llm_route)
    if rule_primary == llm_primary and missing_entity_types:
        details["missing_entity_types"] = missing_entity_types
        return _diff_payload(case, rule_route, llm_route, "entity_missing", details)
    if rule_primary == llm_primary:
        return _diff_payload(case, rule_route, llm_route, "matched", {})
    return _diff_payload(case, rule_route, llm_route, "llm_regressed", {"rule_primary_route": rule_primary, "llm_primary_route": llm_primary})


def build_llm_router_prompt(case: dict[str, Any], rule_route: dict[str, Any], candidate_routes: list[dict[str, Any]]) -> str:
    prompt_payload = {
        "task": "Return one JSON object only. Project the user's question into intent-route-v0.2 for shadow comparison.",
        "schema_version": INTENT_ROUTE_SCHEMA_VERSION,
        "question": case.get("question", ""),
        "source_scope": case.get("source_scope", {}),
        "previous_context": case.get("previous_context", {}),
        "rule_route_shadow_for_reference": rule_route,
        "candidate_routes": candidate_routes,
        "guardrails": [
            "primary_route must be a candidate route id",
            "secondary_routes must be candidate route ids",
            "use needs_previous_context=true for source-location follow-up questions",
            "entities are structured instances, not copies of dynamic_term_keys",
        ],
        "required_output_fields": [
            "schema_version",
            "primary_route",
            "secondary_routes",
            "question_type",
            "needs_previous_context",
            "confidence.route_match",
            "confidence.evidence_likely",
            "entities",
            "_extensions",
        ],
    }
    return json.dumps(prompt_payload, ensure_ascii=False, indent=2)


def _first_json_object(text: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            payload, _end = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    raise ValueError("LLM router output did not contain a JSON object")


def _diff_payload(
    case: dict[str, Any],
    rule_route: dict[str, Any],
    llm_route: dict[str, Any] | None,
    classification: str,
    details: dict[str, Any],
) -> dict[str, Any]:
    return {
        "case_id": case.get("case_id", "unknown"),
        "question": case.get("question", ""),
        "expected_route_id": case.get("expected_route_id", ""),
        "classification": classification,
        "rule_route": _route_summary(rule_route),
        "llm_route": _route_summary(llm_route) if llm_route else {},
        "details": details,
    }


def _route_summary(route: dict[str, Any]) -> dict[str, Any]:
    payload = deepcopy(route)
    catalog = payload.get("route_catalog")
    if isinstance(catalog, dict):
        payload["route_catalog"] = {
            "route_id": catalog.get("route_id"),
            "evidence_needs": catalog.get("evidence_needs", []),
            "answer_slots": [slot.get("slot_id") for slot in catalog.get("answer_slots", []) if isinstance(slot, dict)],
            "risk_level": catalog.get("risk_level"),
            "citation_policy": catalog.get("citation_policy"),
        }
    return payload


def _is_source_location_risk(case: dict[str, Any], llm_route: dict[str, Any]) -> bool:
    if not case.get("source_location_guardrail_required"):
        return False
    if llm_route.get("primary_route") != "reference_lookup":
        return True
    return not bool(llm_route.get("needs_previous_context"))


def _missing_entity_types(rule_route: dict[str, Any], llm_route: dict[str, Any]) -> list[str]:
    required_types = {str(entity.get("type")) for entity in rule_route.get("entities", []) if isinstance(entity, dict) and entity.get("type")}
    llm_types = {str(entity.get("type")) for entity in llm_route.get("entities", []) if isinstance(entity, dict) and entity.get("type")}
    important_types = {"stage_transition", "stage", "deliverable", "role", "bu_scope_hint", "section"}
    return sorted((required_types & important_types) - llm_types)