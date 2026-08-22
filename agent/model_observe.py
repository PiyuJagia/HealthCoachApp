"""Capture ADK pre-model LlmRequest snapshots for TRACE observability.

Does not mutate the request. Does not capture hidden thought parts, API keys,
or HTTP headers. Capture fidelity is adk_pre_model_request, not the wire payload.
"""

from __future__ import annotations

from typing import Any

from evals.trace_schema import (
    CAPTURE_FIDELITY_ADK_PRE_MODEL,
    GENERATION_CONFIG_KEEP,
    ORIGIN_DETERMINISTIC_ANALYTICS,
    ORIGIN_EVIDENCE_POLICY,
    ORIGIN_EVIDENCE_RAG,
    ORIGIN_GENERATION_CONFIG,
    ORIGIN_HEALTH_TREND_TOOL,
    ORIGIN_LIFESTYLE_TOOL,
    ORIGIN_LONGITUDINAL_ANALYTICS,
    ORIGIN_RECOMMENDATION_BOUNDARY,
    ORIGIN_SALIENCE_ANALYTICS,
    ORIGIN_SPREAD_ANALYTICS,
    ORIGIN_PRIOR_MODEL_TOOL,
    ORIGIN_SYSTEM_INSTRUCTIONS,
    ORIGIN_USER_SCENARIO_INPUT,
    ORIGIN_WEEKLY_SUMMARY,
    TOOL_ORIGIN_BY_NAME,
    ContextComponentProvenance,
    ModelCallContextTrace,
    ObservableMessage,
    sanitize_for_trace,
)

TREND_TOOL = "get_trend_signals"
EVIDENCE_TOOL = "retrieve_authorized_evidence"
LIFESTYLE_TOOL = "get_lifestyle_context"

WEEKLY_VALUE_FIELDS = (
    "average_sleep_hours",
    "total_exercise_minutes",
    "total_workouts",
    "average_resting_hr_bpm",
    "average_hrv_sdnn_ms",
    "average_steps",
    "average_respiratory_rate",
)


def _part_is_thought(part: Any) -> bool:
    return bool(getattr(part, "thought", False))


def _as_mapping(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    if hasattr(value, "items") and not isinstance(value, (str, bytes, list)):
        try:
            return dict(value)
        except (TypeError, ValueError):
            return None
    return None


def unwrap_tool_payload(response: Any) -> Any:
    mapping = _as_mapping(response)
    if mapping is None:
        return response
    nested = mapping.get("result")
    nested_map = _as_mapping(nested)
    if nested_map is not None and any(
        key in nested_map for key in ("trends", "weekly_summaries", "retrieval", "policy")
    ):
        return nested_map
    return mapping


def assess_weekly_summary_bypass(payload: Any) -> dict[str, Any]:
    mapping = unwrap_tool_payload(payload) if not isinstance(payload, dict) else payload
    if not isinstance(mapping, dict):
        return {
            "bypass_possible": False,
            "present": False,
            "reason": "no_tool_payload",
        }
    summaries = mapping.get("weekly_summaries") or []
    trends = mapping.get("trends") or []
    if not summaries:
        return {
            "bypass_possible": False,
            "present": False,
            "has_claim_semantics": False,
            "reason": "weekly_summaries_absent",
        }
    trend_eligibility = {
        str(item.get("metric")): (item.get("claim_eligibility") or {})
        for item in trends
        if isinstance(item, dict)
    }
    missing_semantics: list[str] = []
    inconsistent_comparison: list[str] = []
    inconsistent_recommendation: list[str] = []
    weeks_with_values = 0
    for week in summaries:
        if not isinstance(week, dict):
            continue
        if any(week.get(field) is not None for field in WEEKLY_VALUE_FIELDS):
            weeks_with_values += 1
        coverage = week.get("coverage") or {}
        as_of_aligned = bool(week.get("as_of_aligned"))
        for metric_name, coverage_row in coverage.items():
            if not isinstance(coverage_row, dict):
                continue
            semantics = coverage_row.get("claim_semantics")
            if not isinstance(semantics, dict):
                if coverage_row.get("observation_count") or week.get(
                    "average_hrv_sdnn_ms"
                ) is not None:
                    if metric_name not in missing_semantics:
                        missing_semantics.append(metric_name)
                continue
            trend_flags = trend_eligibility.get(str(metric_name)) or {}
            if as_of_aligned and semantics.get("summary_comparison_allowed") and not trend_flags.get(
                "trend_allowed"
            ):
                inconsistent_comparison.append(str(metric_name))
            if as_of_aligned and semantics.get("summary_recommendation_support_allowed") and not trend_flags.get(
                "recommendation_support_allowed"
            ):
                inconsistent_recommendation.append(str(metric_name))
    bypass_possible = bool(missing_semantics or inconsistent_comparison or inconsistent_recommendation)
    return {
        "bypass_possible": bypass_possible,
        "present": True,
        "week_count": len(summaries),
        "weeks_with_numeric_values": weeks_with_values,
        "has_claim_semantics": not missing_semantics,
        "coverage_without_claim_semantics": missing_semantics,
        "inconsistent_comparison": inconsistent_comparison,
        "inconsistent_recommendation": inconsistent_recommendation,
        "trend_metrics_with_eligibility": sorted(
            name for name, flags in trend_eligibility.items() if flags
        ),
        "reason": (
            "weekly summaries missing claim_semantics or contradict the trend contract"
            if bypass_possible
            else "weekly summaries expose observed values with claim_semantics gated by the trend contract"
        ),
        "recommended_remediation": "none" if not bypass_possible else "align_weekly_claim_semantics",
    }



def extract_trend_maturity(payload: Any) -> dict[str, Any] | None:
    mapping = unwrap_tool_payload(payload)
    if not isinstance(mapping, dict) or not mapping.get("trends"):
        return None
    metrics = []
    for item in mapping.get("trends") or []:
        if not isinstance(item, dict):
            continue
        metrics.append(
            {
                "metric": item.get("metric"),
                "cadence": item.get("cadence"),
                "direction": item.get("direction"),
                "percent_change": item.get("percent_change"),
                "as_of_date_available": item.get("as_of_date_available"),
                "coverage_ratio": item.get("coverage_ratio"),
                "data_maturity_state": item.get("data_maturity_state"),
                "gap_caveat_required": item.get("gap_caveat_required"),
                "claim_eligibility": item.get("claim_eligibility"),
                "partial_coverage": item.get("partial_coverage"),
                "current_value": item.get("current_value"),
                "control_metric": item.get("control_metric")
                or (item.get("salience") or {}).get("control_metric"),
            }
        )
    return {
        "origin": ORIGIN_DETERMINISTIC_ANALYTICS,
        "source_id": TREND_TOOL,
        "as_of_date": mapping.get("as_of_date"),
        "gap_caveat_required": mapping.get("gap_caveat_required"),
        "as_of_any_daily_metric_available": mapping.get("as_of_any_daily_metric_available"),
        "metrics": metrics,
    }


def extract_longitudinal_context(payload: Any) -> dict[str, Any] | None:
    mapping = unwrap_tool_payload(payload)
    if not isinstance(mapping, dict):
        return None
    trends = mapping.get("trends") or []
    has_longitudinal = any(
        isinstance(item, dict) and isinstance(item.get("longitudinal"), dict)
        for item in trends
    )
    summary = mapping.get("longitudinal_summary")
    if not has_longitudinal and not isinstance(summary, dict):
        return None
    metrics = []
    for item in trends:
        if not isinstance(item, dict) or not isinstance(item.get("longitudinal"), dict):
            continue
        long = item["longitudinal"]
        metrics.append(
            {
                "metric": item.get("metric"),
                "recent_state": long.get("recent_state"),
                "long_term_reference_value": long.get("long_term_reference_value"),
                "prior_significant_change_direction": long.get("prior_significant_change_direction"),
                "prior_significant_change_percent": long.get("prior_significant_change_percent"),
                "current_vs_long_term_percent": long.get("current_vs_long_term_percent"),
                "maintenance_of_gain": long.get("maintenance_of_gain"),
                "maintenance_of_decline": long.get("maintenance_of_decline"),
                "longitudinal_context_available": long.get("longitudinal_context_available"),
                "reason": long.get("reason"),
            }
        )
    return {
        "origin": ORIGIN_LONGITUDINAL_ANALYTICS,
        "source_id": TREND_TOOL,
        "summary": summary,
        "metrics": metrics,
    }


def extract_insight_salience(payload: Any) -> dict[str, Any] | None:
    mapping = unwrap_tool_payload(payload)
    if not isinstance(mapping, dict):
        return None
    summary = mapping.get("insight_salience")
    trends = mapping.get("trends") or []
    metrics = []
    for item in trends:
        if not isinstance(item, dict) or not isinstance(item.get("salience"), dict):
            continue
        salience = item["salience"]
        long = item.get("longitudinal") if isinstance(item.get("longitudinal"), dict) else {}
        eligibility = item.get("claim_eligibility") if isinstance(item.get("claim_eligibility"), dict) else {}
        metrics.append(
            {
                "metric": item.get("metric"),
                "direction": item.get("direction"),
                "salience_level": salience.get("salience_level"),
                "magnitude_band": salience.get("magnitude_band"),
                "insight_candidate": salience.get("insight_candidate"),
                "recommendation_candidate": salience.get("recommendation_candidate"),
                "corroborating_metrics": list(salience.get("corroborating_metrics") or []),
                "reasons": list(salience.get("reasons") or []),
                "maintenance_of_gain": long.get("maintenance_of_gain"),
                "maintenance_of_decline": long.get("maintenance_of_decline"),
                "data_maturity_state": item.get("data_maturity_state"),
                "trend_allowed": eligibility.get("trend_allowed"),
                "early_pattern_allowed": eligibility.get("early_pattern_allowed"),
                "control_metric": salience.get("control_metric") or item.get("control_metric"),
            }
        )
    if not isinstance(summary, dict) and not metrics:
        return None
    return {
        "origin": ORIGIN_SALIENCE_ANALYTICS,
        "source_id": TREND_TOOL,
        "summary": summary,
        "metrics": metrics,
    }


def extract_within_window_spread(payload: Any) -> dict[str, Any] | None:
    mapping = unwrap_tool_payload(payload)
    if not isinstance(mapping, dict):
        return None
    metrics = []
    for item in mapping.get("trends") or []:
        if not isinstance(item, dict) or not isinstance(item.get("within_window_spread"), dict):
            continue
        spread = item["within_window_spread"]
        eligibility = item.get("claim_eligibility") if isinstance(item.get("claim_eligibility"), dict) else {}
        metrics.append(
            {
                "metric": item.get("metric"),
                "direction": item.get("direction"),
                "data_maturity_state": item.get("data_maturity_state"),
                "trend_allowed": eligibility.get("trend_allowed"),
                "baseline_ready": item.get("baseline_ready"),
                "partial_coverage": item.get("partial_coverage"),
                "gap_caveat_required": item.get("gap_caveat_required"),
                "observation_count": spread.get("observation_count"),
                "mean": spread.get("mean"),
                "sample_standard_deviation": spread.get("sample_standard_deviation"),
                "min": spread.get("min"),
                "max": spread.get("max"),
                "range": spread.get("range"),
                "baseline_standard_deviation": spread.get("baseline_standard_deviation"),
                "spread_ratio": spread.get("spread_ratio"),
                "spread_observation_allowed": spread.get("spread_observation_allowed"),
                "spread_comparison_allowed": spread.get("spread_comparison_allowed"),
            }
        )
    if not metrics:
        return None
    return {
        "origin": ORIGIN_SPREAD_ANALYTICS,
        "source_id": TREND_TOOL,
        "metrics": metrics,
    }


def extract_weekly_summaries(payload: Any) -> dict[str, Any] | None:
    mapping = unwrap_tool_payload(payload)
    if not isinstance(mapping, dict) or not mapping.get("weekly_summaries"):
        return None
    weeks = mapping.get("weekly_summaries") or []
    latest = weeks[-1] if weeks else {}
    coverage = (latest or {}).get("coverage") or {}
    return {
        "origin": ORIGIN_WEEKLY_SUMMARY,
        "source_id": TREND_TOOL,
        "weeks": sanitize_for_trace(weeks),
        "as_of_aligned": (latest or {}).get("as_of_aligned"),
        "claim_semantics_by_metric": {
            metric: (row.get("claim_semantics") if isinstance(row, dict) else None)
            for metric, row in coverage.items()
        },
        "bypass": assess_weekly_summary_bypass(mapping),
    }


def extract_rag_evidence(payload: Any) -> dict[str, Any] | None:
    mapping = unwrap_tool_payload(payload)
    if not isinstance(mapping, dict):
        return None
    if not any(key in mapping for key in ("retrieval", "policy", "overall_verdict")):
        return None
    return {
        "origin": ORIGIN_EVIDENCE_RAG,
        "source_id": EVIDENCE_TOOL,
        "query": mapping.get("query"),
        "overall_verdict": mapping.get("overall_verdict"),
        "evidence_authorized": mapping.get("evidence_authorized"),
        "recommendation_authorized": mapping.get("recommendation_authorized"),
        "recommendation_worthy": mapping.get("recommendation_worthy"),
        "final_recommendation_allowed": mapping.get("final_recommendation_allowed"),
        "available_inputs": list(mapping.get("available_inputs") or []),
        "retrieval_count": mapping.get("retrieval_count"),
        "authorized_count": mapping.get("authorized_count"),
        "relationship_ids": [
            item.get("relationship_id")
            for item in mapping.get("retrieval") or []
            if isinstance(item, dict) and item.get("relationship_id")
        ],
        "policy_reasons": list((mapping.get("policy") or {}).get("reasons") or [])
        if isinstance(mapping.get("policy"), dict)
        else [],
    }


def extract_recommendation_boundary(payload: Any) -> dict[str, Any] | None:
    mapping = unwrap_tool_payload(payload)
    if not isinstance(mapping, dict):
        return None
    if "final_recommendation_allowed" not in mapping and "recommendation_authorized" not in mapping:
        return None
    return {
        "origin": ORIGIN_RECOMMENDATION_BOUNDARY,
        "recommendation_worthy": mapping.get("recommendation_worthy"),
        "recommendation_worthy_origin": ORIGIN_SALIENCE_ANALYTICS,
        "recommendation_authorized": mapping.get("recommendation_authorized"),
        "recommendation_authorized_origin": ORIGIN_EVIDENCE_POLICY,
        "final_recommendation_allowed": mapping.get("final_recommendation_allowed"),
        "final_recommendation_allowed_origin": ORIGIN_RECOMMENDATION_BOUNDARY,
    }


def extract_lifestyle_context(payload: Any) -> dict[str, Any] | None:
    mapping = unwrap_tool_payload(payload)
    if not isinstance(mapping, dict):
        return None
    lifestyle_keys = {
        "lifestyle_events",
        "events",
        "by_type",
        "lookback_days",
        "policy_available_inputs",
        "caffeine",
        "alcohol",
        "mood",
    }
    if not lifestyle_keys.intersection(mapping.keys()):
        return None
    event_types = []
    if isinstance(mapping.get("by_type"), list):
        event_types = [
            item.get("event_type")
            for item in mapping["by_type"]
            if isinstance(item, dict) and item.get("event_type")
        ]
    return {
        "origin": ORIGIN_LIFESTYLE_TOOL,
        "source_id": LIFESTYLE_TOOL,
        "lookback_days": mapping.get("lookback_days"),
        "window_start": mapping.get("window_start"),
        "window_end": mapping.get("window_end"),
        "event_count": mapping.get("event_count"),
        "event_types": event_types,
        "policy_available_inputs": list(mapping.get("policy_available_inputs") or []),
        "late_work_context_event_count": mapping.get("late_work_context_event_count"),
    }


def _system_instruction_text(llm_request: Any) -> str | None:
    config = getattr(llm_request, "config", None)
    instruction = getattr(config, "system_instruction", None) if config is not None else None
    if instruction is None:
        return None
    if isinstance(instruction, str):
        return instruction
    text_parts: list[str] = []
    parts = getattr(instruction, "parts", None)
    if parts:
        for part in parts:
            if _part_is_thought(part):
                continue
            text = getattr(part, "text", None)
            if text:
                text_parts.append(text)
        return "\n".join(text_parts) if text_parts else str(instruction)
    return str(instruction)


def _generation_config(llm_request: Any) -> dict[str, Any] | None:
    config = getattr(llm_request, "config", None)
    if config is None:
        return None
    dumped: dict[str, Any]
    if hasattr(config, "model_dump"):
        dumped = config.model_dump(exclude={"http_options", "tools"}, exclude_none=True)
    else:
        dumped = {
            key: getattr(config, key)
            for key in GENERATION_CONFIG_KEEP
            if getattr(config, key, None) is not None
        }
    kept = {key: dumped[key] for key in GENERATION_CONFIG_KEEP if key in dumped and dumped[key] is not None}
    return sanitize_for_trace(kept) or None


def _function_call_record(part: Any) -> dict[str, Any]:
    call = getattr(part, "function_call", None)
    name = str(getattr(call, "name", "") or "")
    args = dict(getattr(call, "args", None) or {})
    return {
        "tool_name": name,
        "arguments": sanitize_for_trace(args),
        "origin": ORIGIN_PRIOR_MODEL_TOOL,
    }


def _function_response_record(part: Any) -> dict[str, Any]:
    response_part = getattr(part, "function_response", None)
    name = str(getattr(response_part, "name", "") or "")
    raw = getattr(response_part, "response", None)
    payload = unwrap_tool_payload(raw)
    origin = TOOL_ORIGIN_BY_NAME.get(name, ORIGIN_PRIOR_MODEL_TOOL)
    return {
        "tool_name": name,
        "origin": origin,
        "payload": sanitize_for_trace(payload),
    }


def observe_llm_request(llm_request: Any, *, call_index: int) -> ModelCallContextTrace:
    omitted_thoughts = 0
    messages: list[ObservableMessage] = []
    tool_calls: list[dict[str, Any]] = []
    tool_results: list[dict[str, Any]] = []
    user_scenario: str | None = None
    trend_maturity = None
    weekly = None
    rag = None
    lifestyle = None
    longitudinal = None
    insight_salience = None
    within_window_spread = None
    recommendation_boundary = None
    bypass = None

    contents = list(getattr(llm_request, "contents", None) or [])
    for content in contents:
        role = str(getattr(content, "role", "") or "unknown")
        for part in getattr(content, "parts", None) or []:
            if _part_is_thought(part):
                omitted_thoughts += 1
                continue
            function_call = getattr(part, "function_call", None)
            function_response = getattr(part, "function_response", None)
            text = getattr(part, "text", None)
            if function_call:
                record = _function_call_record(part)
                tool_calls.append(record)
                messages.append(
                    ObservableMessage(
                        role=role,
                        kind="function_call",
                        origin=ORIGIN_PRIOR_MODEL_TOOL,
                        tool_name=record["tool_name"],
                        structured={"arguments": record["arguments"]},
                    )
                )
                continue
            if function_response:
                record = _function_response_record(part)
                tool_results.append(record)
                payload = record["payload"]
                origin = str(record["origin"])
                if record["tool_name"] == TREND_TOOL:
                    trend_maturity = extract_trend_maturity(payload)
                    weekly = extract_weekly_summaries(payload)
                    longitudinal = extract_longitudinal_context(payload)
                    insight_salience = extract_insight_salience(payload)
                    within_window_spread = extract_within_window_spread(payload)
                    bypass = assess_weekly_summary_bypass(payload)
                    origin = ORIGIN_HEALTH_TREND_TOOL
                elif record["tool_name"] == EVIDENCE_TOOL:
                    rag = extract_rag_evidence(payload)
                    recommendation_boundary = extract_recommendation_boundary(payload)
                    origin = ORIGIN_EVIDENCE_RAG
                elif record["tool_name"] == LIFESTYLE_TOOL:
                    lifestyle = extract_lifestyle_context(payload)
                    origin = ORIGIN_LIFESTYLE_TOOL
                messages.append(
                    ObservableMessage(
                        role=role,
                        kind="function_response",
                        origin=origin,
                        tool_name=record["tool_name"],
                    )
                )
                continue
            if text:
                origin = ORIGIN_USER_SCENARIO_INPUT if role == "user" else ORIGIN_PRIOR_MODEL_TOOL
                if role == "user" and user_scenario is None:
                    user_scenario = text
                messages.append(
                    ObservableMessage(
                        role=role,
                        kind="text",
                        origin=origin,
                        text=text,
                    )
                )

    system_instruction = _system_instruction_text(llm_request)
    generation_config = _generation_config(llm_request)
    provenance = [
        ContextComponentProvenance(
            component="system_instruction",
            origin=ORIGIN_SYSTEM_INSTRUCTIONS,
            present=bool(system_instruction),
        ),
        ContextComponentProvenance(
            component="user_scenario_input",
            origin=ORIGIN_USER_SCENARIO_INPUT,
            present=bool(user_scenario),
        ),
        ContextComponentProvenance(
            component="trend_maturity",
            origin=ORIGIN_DETERMINISTIC_ANALYTICS,
            source_id=TREND_TOOL,
            present=trend_maturity is not None,
            notes="claim_eligibility and data_maturity_state from get_trend_signals",
        ),
        ContextComponentProvenance(
            component="weekly_summaries",
            origin=ORIGIN_WEEKLY_SUMMARY,
            source_id=TREND_TOOL,
            present=weekly is not None,
            notes="weekly observed values with claim_semantics gated by the as-of trend" if weekly else "",
        ),
        ContextComponentProvenance(
            component="longitudinal_context",
            origin=ORIGIN_LONGITUDINAL_ANALYTICS,
            source_id=TREND_TOOL,
            present=longitudinal is not None,
            notes="older personal reference vs recent stable state; maintenance_of_gain is observational",
        ),
        ContextComponentProvenance(
            component="insight_salience",
            origin=ORIGIN_SALIENCE_ANALYTICS,
            source_id=TREND_TOOL,
            present=insight_salience is not None,
            notes="product surfacing contract; detectable direction is not automatically insight-worthy",
        ),
        ContextComponentProvenance(
            component="within_window_spread",
            origin=ORIGIN_SPREAD_ANALYTICS,
            source_id=TREND_TOOL,
            present=within_window_spread is not None,
            notes="day-to-day spread of readings; distinct from F4.1 level/direction; HRV-only MVP",
        ),
        ContextComponentProvenance(
            component="rag_evidence",
            origin=ORIGIN_EVIDENCE_RAG,
            source_id=EVIDENCE_TOOL,
            present=rag is not None,
        ),
        ContextComponentProvenance(
            component="recommendation_boundary",
            origin=ORIGIN_RECOMMENDATION_BOUNDARY,
            source_id=EVIDENCE_TOOL,
            present=recommendation_boundary is not None,
            notes="final_recommendation_allowed = recommendation_worthy AND recommendation_authorized",
        ),
        ContextComponentProvenance(
            component="lifestyle_context",
            origin=ORIGIN_LIFESTYLE_TOOL,
            source_id=LIFESTYLE_TOOL,
            present=lifestyle is not None,
            notes="user-specific observational context from get_lifestyle_context; not scientific evidence",
        ),
        ContextComponentProvenance(
            component="generation_config",
            origin=ORIGIN_GENERATION_CONFIG,
            present=generation_config is not None,
        ),
    ]
    model_name = str(getattr(llm_request, "model", None) or "")
    return ModelCallContextTrace(
        call_index=call_index,
        model=model_name,
        capture_fidelity=CAPTURE_FIDELITY_ADK_PRE_MODEL,
        system_instruction=system_instruction,
        user_scenario_input=user_scenario,
        conversation_messages=messages,
        tool_calls_preceding=tool_calls,
        tool_results_visible=tool_results,
        trend_maturity_visible=trend_maturity,
        weekly_summaries_visible=weekly,
        rag_evidence_visible=rag,
        lifestyle_context_visible=lifestyle,
        longitudinal_context_visible=longitudinal,
        insight_salience_visible=insight_salience,
        within_window_spread_visible=within_window_spread,
        recommendation_boundary_visible=recommendation_boundary,
        generation_config=generation_config,
        provenance=provenance,
        weekly_summary_bypass_risk=bypass,
        omitted_thought_parts=omitted_thoughts,
    )


def observe_llm_response(llm_response: Any) -> dict[str, Any]:
    omitted_thoughts = 0
    kinds: list[str] = []
    function_calls: list[str] = []
    text_parts: list[str] = []
    content = getattr(llm_response, "content", None)
    parts = getattr(content, "parts", None) or []
    for part in parts:
        if _part_is_thought(part):
            omitted_thoughts += 1
            continue
        function_call = getattr(part, "function_call", None)
        text = getattr(part, "text", None)
        if function_call:
            kinds.append("function_call")
            function_calls.append(str(getattr(function_call, "name", "") or ""))
        elif text:
            kinds.append("text")
            text_parts.append(text)
    preview = "\n".join(text_parts)
    if len(preview) > 500:
        preview = preview[:500]
    return sanitize_for_trace(
        {
            "kinds": kinds,
            "function_calls": function_calls,
            "visible_text_preview": preview or None,
            "omitted_thought_parts": omitted_thoughts,
        }
    )


def capture_before_model(*, callback_context: Any, llm_request: Any, context: Any) -> None:
    """ADK before_model_callback body. Returns None so the model call proceeds unchanged."""
    del callback_context
    snapshot_len = len(getattr(llm_request, "contents", None) or [])
    call = observe_llm_request(llm_request, call_index=len(context.model_calls))
    context.model_calls.append(call)
    if len(getattr(llm_request, "contents", None) or []) != snapshot_len:
        raise RuntimeError("model observation mutated llm_request.contents")
    return None


def capture_after_model(*, callback_context: Any, llm_response: Any, context: Any) -> None:
    del callback_context
    if context.model_calls:
        context.model_calls[-1].visible_response = observe_llm_response(llm_response)
    return None


def bind_model_observation_callbacks(context: Any) -> dict[str, Any]:
    def before_model_callback(*, callback_context: Any, llm_request: Any):
        return capture_before_model(
            callback_context=callback_context,
            llm_request=llm_request,
            context=context,
        )

    def after_model_callback(*, callback_context: Any, llm_response: Any):
        return capture_after_model(
            callback_context=callback_context,
            llm_response=llm_response,
            context=context,
        )

    return {
        "before_model_callback": before_model_callback,
        "after_model_callback": after_model_callback,
    }
