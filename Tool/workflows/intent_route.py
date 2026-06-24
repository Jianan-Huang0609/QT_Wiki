from __future__ import annotations

from copy import deepcopy
from typing import Any

from Tool.workflows.route_catalog import RouteCatalogEntry, get_route_catalog, get_route_entry


INTENT_ROUTE_SCHEMA_VERSION = "intent-route-v0.2"
MIN_ROUTE_MATCH_CONFIDENCE = 0.45


def build_catalog_intent_route(
    entry: RouteCatalogEntry,
    *,
    question_type: str | None = None,
    secondary_routes: list[str] | None = None,
    entities: list[dict[str, Any]] | None = None,
    needs_previous_context: bool = False,
    route_match: float = 1.0,
    evidence_likely: float = 1.0,
    extensions: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": INTENT_ROUTE_SCHEMA_VERSION,
        "primary_route": entry.route_id,
        "secondary_routes": list(secondary_routes or []),
        "question_type": question_type or entry.route_id,
        "needs_previous_context": bool(needs_previous_context),
        "confidence": {
            "route_match": _clamp_confidence(route_match),
            "evidence_likely": _clamp_confidence(evidence_likely),
        },
        "entities": list(entities or []),
        "guardrail": {"status": "passed", "reasons": [], "applied_fallback": False},
        "route_catalog": entry.to_dict(),
        "_extensions": dict(extensions or {}),
    }


def project_rule_route_to_intent_route(
    *,
    route_id: str,
    question_type: str,
    normalized_terms: dict[str, list[str]] | None = None,
    needs_previous_context: bool = False,
    route_match: float = 1.0,
    evidence_likely: float = 1.0,
    extensions: dict[str, Any] | None = None,
) -> dict[str, Any]:
    entry = get_route_entry(route_id) or get_route_entry("generic_rag")
    if entry is None:
        raise ValueError("RouteCatalog must contain generic_rag")
    route = build_catalog_intent_route(
        entry,
        question_type=question_type,
        entities=entities_from_normalized_terms(normalized_terms or {}),
        needs_previous_context=needs_previous_context,
        route_match=route_match,
        evidence_likely=evidence_likely,
        extensions=extensions,
    )
    if route_id != entry.route_id:
        route["_extensions"] = {
            **route["_extensions"],
            "requested_primary_route": route_id,
            "projection_fallback_reason": "route not found while projecting rule route",
        }
    return guard_intent_route_v02(route)


def guard_intent_route_v02(route: dict[str, Any]) -> dict[str, Any]:
    catalog = get_route_catalog()
    guarded = deepcopy(route)
    reasons: list[str] = []
    primary_route = str(guarded.get("primary_route") or "")
    secondary_routes = [str(route_id) for route_id in guarded.get("secondary_routes") or []]
    confidence = guarded.get("confidence") if isinstance(guarded.get("confidence"), dict) else {}
    route_match = _clamp_confidence(confidence.get("route_match", 0.0))
    evidence_likely = _clamp_confidence(confidence.get("evidence_likely", 0.0))

    if guarded.get("schema_version") != INTENT_ROUTE_SCHEMA_VERSION:
        reasons.append("invalid_schema_version")
    if primary_route not in catalog:
        reasons.append("invalid_primary_route")
    invalid_secondary_routes = [route_id for route_id in secondary_routes if route_id not in catalog]
    if invalid_secondary_routes:
        reasons.append("invalid_secondary_route")
    if route_match < MIN_ROUTE_MATCH_CONFIDENCE:
        reasons.append("low_route_match")

    if reasons:
        generic_entry = catalog["generic_rag"]
        guarded["_extensions"] = {
            **dict(guarded.get("_extensions") or {}),
            "guardrail_original_primary_route": primary_route,
            "guardrail_original_secondary_routes": secondary_routes,
        }
        guarded["primary_route"] = "generic_rag"
        guarded["secondary_routes"] = []
        guarded["route_catalog"] = generic_entry.to_dict()
        guarded["confidence"] = {"route_match": route_match, "evidence_likely": evidence_likely}
        guarded["guardrail"] = {"status": "fallback", "reasons": reasons, "applied_fallback": True}
        return guarded

    guarded["secondary_routes"] = secondary_routes
    guarded["confidence"] = {"route_match": route_match, "evidence_likely": evidence_likely}
    guarded["guardrail"] = {"status": "passed", "reasons": [], "applied_fallback": False}
    return guarded


def entities_from_normalized_terms(normalized_terms: dict[str, list[str]]) -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []
    stages = _unique_terms(normalized_terms.get("stage", []))
    if len(stages) >= 2:
        entities.append({"type": "stage_transition", "from_stage": stages[0], "to_stage": stages[1]})
    elif stages:
        entities.append({"type": "stage", "active_stage": stages[0]})

    for deliverable in _unique_terms(normalized_terms.get("deliverable", [])):
        entities.append({"type": "deliverable", "query_target": deliverable})
    for role in _unique_terms(normalized_terms.get("role", [])):
        entities.append({"type": "role", "query_target": role})
    business_units = _unique_terms(normalized_terms.get("bu", []))
    if business_units:
        entities.append({"type": "bu_scope_hint", "values": business_units})
    for section in _unique_terms(normalized_terms.get("section", [])):
        entities.append({"type": "section", "query_target": section})
    for milestone in _unique_terms(normalized_terms.get("milestone", [])):
        entities.append({"type": "milestone", "query_target": milestone})
    return entities


def _clamp_confidence(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return min(max(number, 0.0), 1.0)


def _unique_terms(values: list[str] | tuple[str, ...]) -> list[str]:
    seen: set[str] = set()
    terms: list[str] = []
    for value in values:
        text = str(value).strip()
        key = text.casefold()
        if text and key not in seen:
            seen.add(key)
            terms.append(text)
    return terms