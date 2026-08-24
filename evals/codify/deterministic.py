"""Deterministic TRACE graders for validated F4/F5 contracts."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from evals.codify.schema import (
    GRADER_DETERMINISTIC,
    OUTCOME_FAIL,
    OUTCOME_NOT_APPLICABLE,
    OUTCOME_PASS,
    GraderResult,
)
from evals.codify.trace_access import (
    CONTROL_METRIC_NAME,
    ELEVATED_STATUSES,
    ESTABLISHED_TREND,
    HRV_METRIC,
    OUTPUT_CONTRACT_ORIGIN,
    boundary_flags,
    claim_eligibility,
    contains_existing_recommendation_phrase,
    final_status,
    insight_salience,
    lifestyle_policy_inputs,
    lifestyle_tool_called,
    longitudinal,
    output_contract,
    supporting_metric_facts,
    text_present,
    trend_by_metric,
    trends,
    user_facing_fields,
    user_facing_text,
    weekly_coverage_rows,
)
from app.recommendation_boundary import INSIGHT_STATUS, NO_PATTERN_STATUS, RECOMMENDATION_STATUS

GraderFn = Callable[[dict[str, Any]], GraderResult]


def _result(
    trace: dict[str, Any],
    *,
    grader_id: str,
    contract: str,
    taxonomy: str | None,
    expected_behavior: str,
    outcome: str,
    observed_value: Any,
    reason: str,
    evidence: dict[str, Any] | None = None,
) -> GraderResult:
    return GraderResult(
        scenario_id=str(trace.get("scenario_id") or ""),
        grader_id=grader_id,
        grader_type=GRADER_DETERMINISTIC,
        contract=contract,
        taxonomy=taxonomy,
        outcome=outcome,
        observed_value=observed_value,
        expected_behavior=expected_behavior,
        evidence=evidence or {},
        reason=reason,
        trace_run_id=str(trace.get("run_id") or "") or None,
    )


def f41_established_trend_requires_trend_allowed(trace: dict[str, Any]) -> GraderResult:
    rows = trends(trace)
    if not rows:
        return _result(
            trace,
            grader_id="f41_established_trend_requires_trend_allowed",
            contract="F4.1",
            taxonomy="T2/T3",
            expected_behavior="ESTABLISHED_TREND implies trend_allowed; blocked trends are not established.",
            outcome=OUTCOME_NOT_APPLICABLE,
            observed_value=None,
            reason="No candidate_signals.trends in TRACE.",
        )
    violations: list[str] = []
    observed: list[dict[str, Any]] = []
    for row in rows:
        metric = row.get("metric")
        maturity = row.get("data_maturity_state")
        allowed = bool(claim_eligibility(row).get("trend_allowed"))
        observed.append({"metric": metric, "data_maturity_state": maturity, "trend_allowed": allowed})
        if maturity == ESTABLISHED_TREND and not allowed:
            violations.append(f"{metric}: ESTABLISHED_TREND without trend_allowed")
        if not allowed and maturity == ESTABLISHED_TREND:
            violations.append(f"{metric}: trend_allowed=false marked established")
    return _result(
        trace,
        grader_id="f41_established_trend_requires_trend_allowed",
        contract="F4.1",
        taxonomy="T2/T3",
        expected_behavior="ESTABLISHED_TREND implies trend_allowed; blocked trends are not established.",
        outcome=OUTCOME_FAIL if violations else OUTCOME_PASS,
        observed_value=observed,
        reason="; ".join(violations) if violations else "Maturity and trend_allowed are consistent.",
        evidence={"source": "candidate_signals.trends"},
    )


def f41_gap_and_as_of_flags_present(trace: dict[str, Any]) -> GraderResult:
    rows = trends(trace)
    if not rows:
        return _result(
            trace,
            grader_id="f41_gap_and_as_of_flags_present",
            contract="F4.1",
            taxonomy="T2",
            expected_behavior="Each trend exposes as_of_date_available and gap_caveat_required.",
            outcome=OUTCOME_NOT_APPLICABLE,
            observed_value=None,
            reason="No candidate_signals.trends in TRACE.",
        )
    missing: list[str] = []
    observed: list[dict[str, Any]] = []
    for row in rows:
        metric = str(row.get("metric"))
        as_of = row.get("as_of_date_available")
        gap = row.get("gap_caveat_required")
        observed.append({"metric": metric, "as_of_date_available": as_of, "gap_caveat_required": gap})
        if not isinstance(as_of, bool):
            missing.append(f"{metric}: as_of_date_available not boolean")
        if not isinstance(gap, bool):
            missing.append(f"{metric}: gap_caveat_required not boolean")
    return _result(
        trace,
        grader_id="f41_gap_and_as_of_flags_present",
        contract="F4.1",
        taxonomy="T2",
        expected_behavior="Each trend exposes as_of_date_available and gap_caveat_required.",
        outcome=OUTCOME_FAIL if missing else OUTCOME_PASS,
        observed_value=observed,
        reason="; ".join(missing) if missing else "As-of and gap flags are present.",
        evidence={"source": "candidate_signals.trends"},
    )


def f43_weekly_cannot_bypass_trend_eligibility(trace: dict[str, Any]) -> GraderResult:
    coverage = weekly_coverage_rows(trace)
    lookup = trend_by_metric(trace)
    if not coverage or not lookup:
        return _result(
            trace,
            grader_id="f43_weekly_cannot_bypass_trend_eligibility",
            contract="F4.3",
            taxonomy="T2/T3",
            expected_behavior="Weekly comparison/recommendation semantics cannot exceed as-of trend gates.",
            outcome=OUTCOME_NOT_APPLICABLE,
            observed_value=None,
            reason="Weekly summaries or trends missing.",
        )
    violations: list[str] = []
    observed: list[dict[str, Any]] = []
    for row in coverage:
        metric = str(row.get("metric") or "")
        trend = lookup.get(metric)
        if trend is None:
            continue
        semantics = row.get("claim_semantics") if isinstance(row.get("claim_semantics"), dict) else {}
        trend_allowed = bool(claim_eligibility(trend).get("trend_allowed"))
        trend_rec = bool(claim_eligibility(trend).get("recommendation_support_allowed"))
        weekly_compare = bool(semantics.get("summary_comparison_allowed"))
        weekly_rec = bool(semantics.get("summary_recommendation_support_allowed"))
        observed.append(
            {
                "metric": metric,
                "summary_comparison_allowed": weekly_compare,
                "trend_allowed": trend_allowed,
                "summary_recommendation_support_allowed": weekly_rec,
                "trend_recommendation_support_allowed": trend_rec,
            }
        )
        if weekly_compare and not trend_allowed:
            violations.append(f"{metric}: weekly comparison without trend_allowed")
        if weekly_rec and not trend_rec:
            violations.append(f"{metric}: weekly rec support without trend rec support")
    return _result(
        trace,
        grader_id="f43_weekly_cannot_bypass_trend_eligibility",
        contract="F4.3",
        taxonomy="T2/T3",
        expected_behavior="Weekly comparison/recommendation semantics cannot exceed as-of trend gates.",
        outcome=OUTCOME_FAIL if violations else OUTCOME_PASS,
        observed_value=observed,
        reason="; ".join(violations) if violations else "Weekly claim_semantics stay within trend gates.",
        evidence={"source": "candidate_signals.weekly_summaries.coverage"},
    )


def f44_lifestyle_inputs_require_lookup(trace: dict[str, Any]) -> GraderResult:
    inputs = sorted(lifestyle_policy_inputs(trace))
    called = lifestyle_tool_called(trace)
    if not inputs:
        return _result(
            trace,
            grader_id="f44_lifestyle_inputs_require_lookup",
            contract="F4.4",
            taxonomy="T1",
            expected_behavior="Lifestyle policy inputs must originate from a lifestyle lookup.",
            outcome=OUTCOME_NOT_APPLICABLE,
            observed_value={"policy_inputs": inputs, "lifestyle_tool_called": called},
            reason="No lifestyle-derived policy inputs on this TRACE.",
        )
    ok = called
    return _result(
        trace,
        grader_id="f44_lifestyle_inputs_require_lookup",
        contract="F4.4",
        taxonomy="T1",
        expected_behavior="Lifestyle policy inputs must originate from a lifestyle lookup.",
        outcome=OUTCOME_PASS if ok else OUTCOME_FAIL,
        observed_value={"policy_inputs": inputs, "lifestyle_tool_called": called},
        reason=(
            "Lifestyle lookup preceded lifestyle policy inputs."
            if ok
            else "Lifestyle policy inputs present without get_lifestyle_context."
        ),
        evidence={"source": "model_calls.lifestyle_context_visible / rag_evidence_visible"},
    )


def f45_maintenance_of_gain_may_surface(trace: dict[str, Any]) -> GraderResult:
    salience = insight_salience(trace)
    if not salience:
        return _result(
            trace,
            grader_id="f45_maintenance_of_gain_may_surface",
            contract="F4.5",
            taxonomy="T4",
            expected_behavior="Valid maintenance_of_gain may surface as INSIGHT; recent stability must not erase it.",
            outcome=OUTCOME_NOT_APPLICABLE,
            observed_value=None,
            reason="insight_salience missing.",
        )
    reasons = [str(item) for item in (salience.get("reasons") or [])]
    any_gain = any(longitudinal(row).get("maintenance_of_gain") for row in trends(trace))
    worthy = bool(salience.get("insight_worthy"))
    if not (worthy and (any_gain or "maintenance_of_gain" in reasons)):
        return _result(
            trace,
            grader_id="f45_maintenance_of_gain_may_surface",
            contract="F4.5",
            taxonomy="T4",
            expected_behavior="Valid maintenance_of_gain may surface as INSIGHT; recent stability must not erase it.",
            outcome=OUTCOME_NOT_APPLICABLE,
            observed_value={"insight_worthy": worthy, "maintenance_of_gain": any_gain, "reasons": reasons},
            reason="No insight-worthy maintenance_of_gain signal.",
        )
    status = final_status(trace)
    ok = status in ELEVATED_STATUSES
    return _result(
        trace,
        grader_id="f45_maintenance_of_gain_may_surface",
        contract="F4.5",
        taxonomy="T4",
        expected_behavior="Valid maintenance_of_gain may surface as INSIGHT; recent stability must not erase it.",
        outcome=OUTCOME_PASS if ok else OUTCOME_FAIL,
        observed_value={"status": status, "insight_worthy": worthy, "maintenance_of_gain": any_gain},
        reason=(
            "Maintenance signal surfaced."
            if ok
            else "insight_worthy maintenance_of_gain was quieted."
        ),
        evidence={"source": "insight_salience + trends.longitudinal"},
    )


def f46_t5_unworthy_not_elevated(trace: dict[str, Any]) -> GraderResult:
    salience = insight_salience(trace)
    if "insight_worthy" not in salience:
        return _result(
            trace,
            grader_id="f46_t5_unworthy_not_elevated",
            contract="F4.6",
            taxonomy="T5",
            expected_behavior="insight_worthy=false must not produce INSIGHT or RECOMMENDATION.",
            outcome=OUTCOME_NOT_APPLICABLE,
            observed_value=None,
            reason="insight_worthy missing.",
        )
    worthy = bool(salience.get("insight_worthy"))
    status = final_status(trace)
    if worthy:
        return _result(
            trace,
            grader_id="f46_t5_unworthy_not_elevated",
            contract="F4.6",
            taxonomy="T5",
            expected_behavior="insight_worthy=false must not produce INSIGHT or RECOMMENDATION.",
            outcome=OUTCOME_NOT_APPLICABLE,
            observed_value={"insight_worthy": True, "status": status},
            reason="insight_worthy=true; T5 quiet-path rule does not apply.",
        )
    ok = status not in ELEVATED_STATUSES
    return _result(
        trace,
        grader_id="f46_t5_unworthy_not_elevated",
        contract="F4.6",
        taxonomy="T5",
        expected_behavior="insight_worthy=false must not produce INSIGHT or RECOMMENDATION.",
        outcome=OUTCOME_PASS if ok else OUTCOME_FAIL,
        observed_value={"insight_worthy": False, "status": status},
        reason="Quiet path honored." if ok else f"Unworthy run surfaced as {status}.",
        evidence={"source": "insight_salience.insight_worthy + structured_result.status"},
    )


def f47_recommendation_requires_both_gates(trace: dict[str, Any]) -> GraderResult:
    flags = boundary_flags(trace)
    status = final_status(trace)
    rec_present = text_present(user_facing_fields(trace).get("recommendation"))
    computed = bool(flags["recommendation_worthy"]) and bool(flags["recommendation_authorized"])
    allowed = flags["final_recommendation_allowed"]
    violations: list[str] = []
    if allowed != computed:
        violations.append("stamped allowed != worthy AND authorized")
    if not allowed and rec_present:
        violations.append("recommendation present while allowed=false")
    if not allowed and status == RECOMMENDATION_STATUS:
        violations.append("RECOMMENDATION status while allowed=false")
    if status == RECOMMENDATION_STATUS and not allowed:
        violations.append("status/gate mismatch")
    return _result(
        trace,
        grader_id="f47_recommendation_requires_both_gates",
        contract="F4.7",
        taxonomy=None,
        expected_behavior="Recommendation output requires worthy AND authorized; otherwise recommendation is null.",
        outcome=OUTCOME_FAIL if violations else OUTCOME_PASS,
        observed_value={**flags, "status": status, "recommendation_present": rec_present},
        reason="; ".join(violations) if violations else "Combined F4.7 gate holds.",
        evidence={"source": "recommendation_boundary + structured_result"},
    )


def f47_rec_phrase_leak_when_blocked(trace: dict[str, Any]) -> GraderResult:
    flags = boundary_flags(trace)
    if flags["final_recommendation_allowed"]:
        return _result(
            trace,
            grader_id="f47_rec_phrase_leak_when_blocked",
            contract="F4.7",
            taxonomy=None,
            expected_behavior="Existing rec phrases must not leak into non-rec fields when allowed=false.",
            outcome=OUTCOME_NOT_APPLICABLE,
            observed_value={"final_recommendation_allowed": True},
            reason="Recommendation is allowed; leak scan applies to the blocked path.",
        )
    text = user_facing_text(trace, include_recommendation=True)
    leaked = contains_existing_recommendation_phrase(text)
    return _result(
        trace,
        grader_id="f47_rec_phrase_leak_when_blocked",
        contract="F4.7",
        taxonomy=None,
        expected_behavior="Existing rec phrases must not leak into non-rec fields when allowed=false.",
        outcome=OUTCOME_FAIL if leaked else OUTCOME_PASS,
        observed_value={"final_recommendation_allowed": False, "phrase_leak": leaked},
        reason="Existing rec-phrase list fired on a blocked path." if leaked else "No existing rec-phrase leak.",
        evidence={"source": "app.output_guard.RECOMMENDATION_PHRASES"},
    )


def f48_t6_control_not_primary(trace: dict[str, Any]) -> GraderResult:
    salience = insight_salience(trace)
    lookup = trend_by_metric(trace)
    rr = lookup.get(CONTROL_METRIC_NAME)
    if not salience and rr is None:
        return _result(
            trace,
            grader_id="f48_t6_control_not_primary",
            contract="F4.8",
            taxonomy="T6",
            expected_behavior="Control metrics cannot be primary insights or independently authorize recommendations.",
            outcome=OUTCOME_NOT_APPLICABLE,
            observed_value=None,
            reason="No control metric or salience payload.",
        )
    primary = {str(item) for item in (salience.get("primary_metrics") or [])}
    controls = {str(item) for item in (salience.get("control_metrics") or [])}
    if rr is not None:
        controls.add(CONTROL_METRIC_NAME)
    overlap = sorted(primary & controls)
    violations: list[str] = []
    if overlap:
        violations.append(f"control in primary_metrics: {overlap}")
    if rr is not None:
        if not bool(rr.get("control_metric")):
            violations.append("respiratory_rate missing control_metric=true")
        salience_row = rr.get("salience") if isinstance(rr.get("salience"), dict) else {}
        insight_candidate = rr.get("insight_candidate")
        if insight_candidate is None:
            insight_candidate = salience_row.get("insight_candidate")
        if insight_candidate:
            violations.append("respiratory_rate insight_candidate=true")
    if flags_rec_from_control_only(trace, controls, primary):
        violations.append("recommendation_worthy with only control recommendation_candidates")
    return _result(
        trace,
        grader_id="f48_t6_control_not_primary",
        contract="F4.8",
        taxonomy="T6",
        expected_behavior="Control metrics cannot be primary insights or independently authorize recommendations.",
        outcome=OUTCOME_FAIL if violations else OUTCOME_PASS,
        observed_value={
            "primary_metrics": sorted(primary),
            "control_metrics": sorted(controls),
            "respiratory_rate_present": rr is not None,
        },
        reason="; ".join(violations) if violations else "Control role preserved.",
        evidence={"source": "insight_salience + trends"},
    )


def flags_rec_from_control_only(
    trace: dict[str, Any],
    controls: set[str],
    primary: set[str],
) -> bool:
    if not insight_salience(trace).get("recommendation_worthy"):
        return False
    if primary - controls:
        return False
    candidates = [
        str(row.get("metric"))
        for row in trends(trace)
        if str(row.get("metric")) not in controls
        and (
            row.get("recommendation_candidate")
            or row.get("insight_candidate")
            or (row.get("salience") if isinstance(row.get("salience"), dict) else {}).get(
                "insight_candidate"
            )
        )
    ]
    return not candidates


def f49_t12_spread_distinct_from_level(trace: dict[str, Any]) -> GraderResult:
    spread_rows: list[dict[str, Any]] = []
    for row in trends(trace):
        spread = row.get("within_window_spread")
        if isinstance(spread, dict):
            spread_rows.append({"metric": row.get("metric"), "direction": row.get("direction"), "spread": spread})
    facts = [item for item in supporting_metric_facts(trace) if item.get("role") == "spread_context"]
    if not spread_rows and not facts:
        return _result(
            trace,
            grader_id="f49_t12_spread_distinct_from_level",
            contract="F4.9",
            taxonomy="T12",
            expected_behavior="Spread remains distinct from level; higher spread is not a decline.",
            outcome=OUTCOME_NOT_APPLICABLE,
            observed_value=None,
            reason="No within_window_spread objects.",
        )
    violations: list[str] = []
    primary = {str(item) for item in (insight_salience(trace).get("primary_metrics") or [])}
    for item in spread_rows:
        direction = item.get("direction")
        metric = str(item.get("metric"))
        trend = trend_by_metric(trace).get(metric) or {}
        insight_candidate = trend.get("insight_candidate")
        if metric == HRV_METRIC and direction == "decreasing":
            ratio = item["spread"].get("spread_ratio")
            if isinstance(ratio, (int, float)) and ratio > 1 and insight_candidate is False:
                violations.append("HRV spread interpreted as decline")
        if insight_candidate is False and metric in primary and metric == HRV_METRIC:
            violations.append("HRV spread promoted into primary_metrics")
    for fact in facts:
        if fact.get("role") != "spread_context":
            violations.append(f"{fact.get('metric')}: spread fact role={fact.get('role')}")
        if fact.get("direction") == "decreasing" and str(fact.get("metric")) == HRV_METRIC:
            hrv = trend_by_metric(trace).get(HRV_METRIC) or {}
            if hrv.get("direction") in {"improving", "stable"}:
                violations.append("spread fact direction contradicts published HRV level")
    return _result(
        trace,
        grader_id="f49_t12_spread_distinct_from_level",
        contract="F4.9",
        taxonomy="T12",
        expected_behavior="Spread remains distinct from level; higher spread is not a decline.",
        outcome=OUTCOME_FAIL if violations else OUTCOME_PASS,
        observed_value={
            "spread_metrics": [item.get("metric") for item in spread_rows],
            "spread_fact_roles": [item.get("role") for item in facts],
        },
        reason="; ".join(violations) if violations else "Spread remains context, not a level decline.",
        evidence={"source": "trends.within_window_spread + supporting_metric_facts"},
    )


def f51_output_contract_shape(trace: dict[str, Any]) -> GraderResult:
    payload = user_facing_fields(trace)
    status = final_status(trace)
    if not status:
        return _result(
            trace,
            grader_id="f51_output_contract_shape",
            contract="F5.1",
            taxonomy="T7",
            expected_behavior="Elevated status requires primary_message; quiet path has null primary and quote.",
            outcome=OUTCOME_NOT_APPLICABLE,
            observed_value=None,
            reason="No structured status.",
        )
    primary = text_present(payload.get("primary_message"))
    quote = text_present(payload.get("motivational_quote"))
    violations: list[str] = []
    if status in ELEVATED_STATUSES and not primary:
        violations.append("elevated status without primary_message")
    if status == NO_PATTERN_STATUS and primary:
        violations.append("primary_message on quiet path")
    if status == NO_PATTERN_STATUS and quote:
        violations.append("motivational_quote on quiet path")
    if not primary and quote:
        violations.append("quote present without primary_message")
    return _result(
        trace,
        grader_id="f51_output_contract_shape",
        contract="F5.1",
        taxonomy="T7",
        expected_behavior="Elevated status requires primary_message; quiet path has null primary and quote.",
        outcome=OUTCOME_FAIL if violations else OUTCOME_PASS,
        observed_value={"status": status, "primary_present": primary, "quote_present": quote},
        reason="; ".join(violations) if violations else "Output-contract shape holds.",
        evidence={"source": "structured_result"},
    )


def f51_facts_are_system_stamped(trace: dict[str, Any]) -> GraderResult:
    contract = output_contract(trace)
    facts = supporting_metric_facts(trace)
    if not contract and not facts:
        return _result(
            trace,
            grader_id="f51_facts_are_system_stamped",
            contract="F5.1",
            taxonomy="T7",
            expected_behavior="supporting_metric_facts are system-stamped.",
            outcome=OUTCOME_NOT_APPLICABLE,
            observed_value=None,
            reason="No output_contract or stamped facts (pre-F5 TRACE).",
        )
    origin = contract.get("supporting_metric_facts_origin")
    violations: list[str] = []
    if contract and origin != OUTPUT_CONTRACT_ORIGIN:
        violations.append(f"facts origin={origin}")
    for fact in facts:
        if fact.get("origin") not in {
            "deterministic_analytics",
            "deterministic_spread_analytics",
            OUTPUT_CONTRACT_ORIGIN,
        } and fact.get("source") != "get_trend_signals":
            violations.append(f"{fact.get('metric')}: unexpected fact origin")
    return _result(
        trace,
        grader_id="f51_facts_are_system_stamped",
        contract="F5.1",
        taxonomy="T7",
        expected_behavior="supporting_metric_facts are system-stamped.",
        outcome=OUTCOME_FAIL if violations else OUTCOME_PASS,
        observed_value={"supporting_metric_facts_origin": origin, "fact_count": len(facts)},
        reason="; ".join(violations) if violations else "Facts are system-stamped.",
        evidence={"source": "output_contract"},
    )


def f51a_quote_null_on_quiet_path(trace: dict[str, Any]) -> GraderResult:
    payload = user_facing_fields(trace)
    status = final_status(trace)
    if not status:
        return _result(
            trace,
            grader_id="f51a_quote_null_on_quiet_path",
            contract="F5.1A",
            taxonomy="T7",
            expected_behavior="Quote is a separate field and is null on the quiet path.",
            outcome=OUTCOME_NOT_APPLICABLE,
            observed_value=None,
            reason="No structured status.",
        )
    quote = payload.get("motivational_quote")
    quote_present = text_present(quote)
    primary = text_present(payload.get("primary_message"))
    quiet = status == NO_PATTERN_STATUS or not primary
    if not quiet:
        return _result(
            trace,
            grader_id="f51a_quote_null_on_quiet_path",
            contract="F5.1A",
            taxonomy="T7",
            expected_behavior="Quote is a separate field and is null on the quiet path.",
            outcome=OUTCOME_PASS,
            observed_value={"status": status, "quote_present": quote_present, "separate_field": "motivational_quote" in payload or quote is None},
            reason="Non-quiet path; quote presence is not deterministically required.",
            evidence={"accepted_limitation": "C4 quote-as-advice is not graded here."},
        )
    return _result(
        trace,
        grader_id="f51a_quote_null_on_quiet_path",
        contract="F5.1A",
        taxonomy="T7",
        expected_behavior="Quote is a separate field and is null on the quiet path.",
        outcome=OUTCOME_FAIL if quote_present else OUTCOME_PASS,
        observed_value={"status": status, "quote_present": quote_present},
        reason="Quote leaked onto quiet path." if quote_present else "Quiet-path quote is null.",
        evidence={"accepted_limitation": "C4 quote-as-advice is not graded here."},
    )


def scenario_b1_quiet_path(trace: dict[str, Any]) -> GraderResult:
    if trace.get("scenario_id") != "HC-EVAL-B1":
        return _result(
            trace,
            grader_id="scenario_b1_quiet_path",
            contract="F4.6",
            taxonomy="T5",
            expected_behavior="B1 remains quiet despite detectable small movement.",
            outcome=OUTCOME_NOT_APPLICABLE,
            observed_value=None,
            reason="Not B1.",
        )
    fields = user_facing_fields(trace)
    status = final_status(trace)
    worthy = insight_salience(trace).get("insight_worthy")
    ok = (
        status == NO_PATTERN_STATUS
        and worthy is False
        and not text_present(fields.get("primary_message"))
        and not text_present(fields.get("motivational_quote"))
        and not text_present(fields.get("recommendation"))
    )
    return _result(
        trace,
        grader_id="scenario_b1_quiet_path",
        contract="F4.6",
        taxonomy="T5",
        expected_behavior="B1 remains quiet despite detectable small movement.",
        outcome=OUTCOME_PASS if ok else OUTCOME_FAIL,
        observed_value={"status": status, "insight_worthy": worthy},
        reason="B1 quiet path protected." if ok else "B1 regression: card was manufactured.",
        evidence={"source": "structured_result + insight_salience"},
    )


def scenario_b3_maintenance_without_rec(trace: dict[str, Any]) -> GraderResult:
    if trace.get("scenario_id") != "HC-EVAL-B3":
        return _result(
            trace,
            grader_id="scenario_b3_maintenance_without_rec",
            contract="F4.5/F4.7",
            taxonomy="T4",
            expected_behavior="B3 surfaces maintained gains without a recommendation.",
            outcome=OUTCOME_NOT_APPLICABLE,
            observed_value=None,
            reason="Not B3.",
        )
    flags = boundary_flags(trace)
    status = final_status(trace)
    rec_present = text_present(user_facing_fields(trace).get("recommendation"))
    any_gain = any(longitudinal(row).get("maintenance_of_gain") for row in trends(trace))
    ok = (
        flags["insight_worthy"]
        and any_gain
        and status == INSIGHT_STATUS
        and flags["final_recommendation_allowed"] is False
        and not rec_present
    )
    return _result(
        trace,
        grader_id="scenario_b3_maintenance_without_rec",
        contract="F4.5/F4.7",
        taxonomy="T4",
        expected_behavior="B3 surfaces maintained gains without a recommendation.",
        outcome=OUTCOME_PASS if ok else OUTCOME_FAIL,
        observed_value={
            "status": status,
            "maintenance_of_gain": any_gain,
            **flags,
            "recommendation_present": rec_present,
        },
        reason="B3 maintenance INSIGHT without rec." if ok else "B3 regression.",
        evidence={"source": "insight_salience + recommendation_boundary"},
    )


def scenario_e1_rr_control(trace: dict[str, Any]) -> GraderResult:
    if trace.get("scenario_id") != "HC-EVAL-E1":
        return _result(
            trace,
            grader_id="scenario_e1_rr_control",
            contract="F4.8",
            taxonomy="T6",
            expected_behavior="E1 respiratory rate remains control context; sleep may remain primary.",
            outcome=OUTCOME_NOT_APPLICABLE,
            observed_value=None,
            reason="Not E1.",
        )
    salience = insight_salience(trace)
    primary = {str(item) for item in (salience.get("primary_metrics") or [])}
    controls = {str(item) for item in (salience.get("control_metrics") or [])}
    rr = trend_by_metric(trace).get(CONTROL_METRIC_NAME)
    ok = (
        rr is not None
        and bool(rr.get("control_metric"))
        and CONTROL_METRIC_NAME in controls
        and CONTROL_METRIC_NAME not in primary
        and "sleep_duration_hours" in primary
    )
    return _result(
        trace,
        grader_id="scenario_e1_rr_control",
        contract="F4.8",
        taxonomy="T6",
        expected_behavior="E1 respiratory rate remains control context; sleep may remain primary.",
        outcome=OUTCOME_PASS if ok else OUTCOME_FAIL,
        observed_value={"primary_metrics": sorted(primary), "control_metrics": sorted(controls)},
        reason="E1 RR control preserved." if ok else "E1 RR control regression.",
        evidence={"note": "Cardiorespiratory reassurance prose is a semantic grader, not this check."},
    )


def scenario_c4_spread_distinct(trace: dict[str, Any]) -> GraderResult:
    if trace.get("scenario_id") != "HC-EVAL-C4":
        return _result(
            trace,
            grader_id="scenario_c4_spread_distinct",
            contract="F4.9",
            taxonomy="T12",
            expected_behavior="C4 HRV level stays distinct from spread_context.",
            outcome=OUTCOME_NOT_APPLICABLE,
            observed_value=None,
            reason="Not C4.",
        )
    hrv = trend_by_metric(trace).get(HRV_METRIC) or {}
    spread = hrv.get("within_window_spread") if isinstance(hrv.get("within_window_spread"), dict) else {}
    primary = {str(item) for item in (insight_salience(trace).get("primary_metrics") or [])}
    facts = [item for item in supporting_metric_facts(trace) if item.get("metric") == HRV_METRIC]
    spread_fact = next((item for item in facts if item.get("role") == "spread_context"), None)
    ok = (
        hrv.get("direction") in {"improving", "stable"}
        and bool(spread)
        and HRV_METRIC not in primary
        and spread_fact is not None
    )
    return _result(
        trace,
        grader_id="scenario_c4_spread_distinct",
        contract="F4.9",
        taxonomy="T12",
        expected_behavior="C4 HRV level stays distinct from spread_context.",
        outcome=OUTCOME_PASS if ok else OUTCOME_FAIL,
        observed_value={
            "hrv_direction": hrv.get("direction"),
            "spread_ratio": spread.get("spread_ratio"),
            "in_primary_metrics": HRV_METRIC in primary,
            "spread_fact_role": None if spread_fact is None else spread_fact.get("role"),
        },
        reason="C4 level/spread split preserved." if ok else "C4 spread regression.",
        evidence={"source": "trends.hrv_sdnn_ms + supporting_metric_facts"},
    )


def scenario_a_family_mature_data(trace: dict[str, Any]) -> GraderResult:
    scenario_id = str(trace.get("scenario_id") or "")
    if not scenario_id.startswith("HC-EVAL-A"):
        return _result(
            trace,
            grader_id="scenario_a_family_mature_data",
            contract="F4.1",
            taxonomy=None,
            expected_behavior="A-family mature-data traces keep an established allowed trend.",
            outcome=OUTCOME_NOT_APPLICABLE,
            observed_value=None,
            reason="Not an A-family scenario.",
        )
    established = [
        row.get("metric")
        for row in trends(trace)
        if row.get("data_maturity_state") == ESTABLISHED_TREND
        and claim_eligibility(row).get("trend_allowed")
    ]
    ok = bool(established)
    return _result(
        trace,
        grader_id="scenario_a_family_mature_data",
        contract="F4.1",
        taxonomy=None,
        expected_behavior="A-family mature-data traces keep an established allowed trend.",
        outcome=OUTCOME_PASS if ok else OUTCOME_FAIL,
        observed_value={"established_allowed_metrics": established},
        reason="A-family mature data preserved." if ok else "A-family lost established-trend eligibility.",
        evidence={"source": "candidate_signals.trends"},
    )


DETERMINISTIC_GRADERS: tuple[GraderFn, ...] = (
    f41_established_trend_requires_trend_allowed,
    f41_gap_and_as_of_flags_present,
    f43_weekly_cannot_bypass_trend_eligibility,
    f44_lifestyle_inputs_require_lookup,
    f45_maintenance_of_gain_may_surface,
    f46_t5_unworthy_not_elevated,
    f47_recommendation_requires_both_gates,
    f47_rec_phrase_leak_when_blocked,
    f48_t6_control_not_primary,
    f49_t12_spread_distinct_from_level,
    f51_output_contract_shape,
    f51_facts_are_system_stamped,
    f51a_quote_null_on_quiet_path,
    scenario_b1_quiet_path,
    scenario_b3_maintenance_without_rec,
    scenario_e1_rr_control,
    scenario_c4_spread_distinct,
    scenario_a_family_mature_data,
)
