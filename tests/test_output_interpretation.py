"""Offline tests for F5.1 T7/T8 output + interpretation MVP."""

from __future__ import annotations

import unittest
from datetime import date

from agent.display import format_health_coach_output
from agent.instructions import HEALTH_COACH_INSTRUCTIONS
from agent.runner import _apply_output_guard, _apply_output_interpretation_contract, _guard_text
from agent.schemas import HealthCoachResult, HealthCoachStatus, health_coach_result_from_payload
from agent.tools import RunContext
from app.health_tools import get_health_trends_for_agent
from app.lifestyle_tools import get_lifestyle_context_for_agent
from app.output_contract import (
    ROLE_CONTROL,
    ROLE_PRIMARY,
    ROLE_SPREAD_CONTEXT,
    ROLE_SUPPORTING,
    apply_output_interpretation_contract,
    stamp_supporting_metric_facts,
)
from app.output_guard import check_final_output
from app.recommendation_boundary import apply_recommendation_boundary
from data.demo_seed import seed_demo_health_data
from evals.trace_schema import (
    ORIGIN_DETERMINISTIC_ANALYTICS,
    ORIGIN_OUTPUT_CONTRACT,
    ORIGIN_SPREAD_ANALYTICS,
    empty_trace,
)
from rag.evidence_policy import AuthorizationVerdict, EvidencePolicyDecision
from tests.test_helpers import open_test_session

A1 = date(2026, 8, 2)
B1 = date(2026, 6, 18)
B3 = date(2026, 8, 17)
C2 = date(2026, 7, 31)
C4 = date(2026, 7, 28)
E1 = date(2026, 8, 2)


def _empty_policy(*, authorized: bool = False) -> EvidencePolicyDecision:
    return EvidencePolicyDecision(
        overall_verdict=AuthorizationVerdict.SURFACE,
        evidence_authorized=True,
        recommendation_authorized=authorized,
        reasons=("authorized_evidence_present",),
        relationship_decisions=(),
        general_evidence=(),
        authorized_results=(),
        suppressed_relationship_ids=(),
    )


def _facts_by_role(facts: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for fact in facts:
        grouped.setdefault(str(fact.get("role")), []).append(fact)
    return grouped


class SchemaCompatibilityTests(unittest.TestCase):
    def test_legacy_payload_still_parses(self) -> None:
        result = health_coach_result_from_payload(
            {
                "scenario_id": "HC-EVAL-A1",
                "user_id": 1,
                "as_of_date": "2026-08-02",
                "status": "INSIGHT",
                "theme": "Sleep",
                "insight": "Sleep declined.",
            },
            scenario_id="HC-EVAL-A1",
            user_id=1,
            as_of_date="2026-08-02",
        )
        self.assertIsNone(result.primary_message)
        self.assertIsNone(result.subtext)
        self.assertIsNone(result.motivational_quote)
        self.assertEqual(result.supporting_metric_facts, [])
        self.assertEqual(result.insight, "Sleep declined.")

    def test_new_fields_round_trip(self) -> None:
        result = HealthCoachResult(
            scenario_id="HC-EVAL-A1",
            user_id=1,
            as_of_date="2026-08-02",
            status="INSIGHT",
            primary_message="Sleep duration declined.",
            subtext="Down about 18% across the available week.",
            motivational_quote="Prioritize rest — it's the foundation of performance.",
            insight="Average sleep moved from about 7.1 to 5.8 hours.",
            supporting_metric_facts=[{"metric": "sleep_duration_hours", "role": "primary"}],
        )
        payload = result.to_dict()
        parsed = health_coach_result_from_payload(
            payload, scenario_id="x", user_id=1, as_of_date="2026-08-02"
        )
        self.assertEqual(parsed.primary_message, "Sleep duration declined.")
        self.assertEqual(parsed.subtext, "Down about 18% across the available week.")
        self.assertEqual(
            parsed.motivational_quote,
            "Prioritize rest — it's the foundation of performance.",
        )
        self.assertEqual(parsed.supporting_metric_facts[0]["role"], "primary")


class GuardAndQuietPathTests(unittest.TestCase):
    def test_insight_requires_primary_message(self) -> None:
        result = check_final_output(
            "Sleep declined.",
            decision=_empty_policy(),
            structured={"status": "INSIGHT", "insight": "Sleep declined.", "primary_message": None},
        )
        self.assertFalse(result.passed)
        self.assertIn("elevated_status_without_primary_message", result.violations)

    def test_quiet_path_cannot_keep_primary_message(self) -> None:
        result = check_final_output(
            "Steps ticked up.",
            decision=_empty_policy(),
            structured={
                "status": "NO_SIGNIFICANT_NEW_PATTERN",
                "primary_message": "Steps ticked up.",
            },
        )
        self.assertFalse(result.passed)
        self.assertIn("primary_message_on_quiet_path", result.violations)

    def test_blocked_recommendation_cannot_hide_in_primary(self) -> None:
        result = check_final_output(
            _guard_text(
                {
                    "status": "INSIGHT",
                    "primary_message": "You should overhaul your bedtime.",
                    "insight": "Sleep declined.",
                    "recommendation": None,
                }
            ),
            decision=_empty_policy(authorized=False),
            recommendation_worthy=False,
            structured={
                "status": "INSIGHT",
                "primary_message": "You should overhaul your bedtime.",
                "insight": "Sleep declined.",
                "recommendation": None,
            },
        )
        self.assertFalse(result.passed)
        self.assertIn("unauthorized_recommendation_language", result.violations)

    def test_guard_text_includes_primary_and_subtext(self) -> None:
        text = _guard_text(
            {
                "primary_message": "Sleep duration declined.",
                "subtext": "Down about 18%.",
                "insight": "Rationale here.",
            }
        )
        self.assertIn("Sleep duration declined.", text)
        self.assertIn("Down about 18%.", text)


class PromptHonorTests(unittest.TestCase):
    def test_instructions_separate_primary_from_rationale(self) -> None:
        text = HEALTH_COACH_INSTRUCTIONS
        self.assertIn("primary_message", text)
        self.assertIn("Fill primary_message separately from insight", text)
        self.assertIn("named multi-metric summary", text)
        self.assertIn("Do not invent supporting_metric_facts", text)
        self.assertIn("A control metric must not become primary_message", text)
        self.assertIn("When metric directions disagree", text)


class DisplayOrderTests(unittest.TestCase):
    def test_display_order_is_primary_subtext_quote_rationale_rec_facts(self) -> None:
        rendered = format_health_coach_output(
            {
                "status": "RECOMMENDATION",
                "primary_message": "Sleep duration declined.",
                "subtext": "Down about 18% across the available week.",
                "motivational_quote": "Prioritize rest — it's the foundation of performance.",
                "insight": "Other observations were mixed.",
                "recommendation": "Consider shifting caffeine earlier.",
                "supporting_metric_facts": [
                    {"metric": "sleep_duration_hours", "role": "primary", "direction": "decreasing", "percent_change": -18.0}
                ],
            }
        )
        primary_at = rendered.index("PRIMARY MESSAGE")
        self.assertLess(primary_at, rendered.index("SUBTEXT"))
        self.assertLess(rendered.index("SUBTEXT"), rendered.index("MOTIVATIONAL QUOTE"))
        self.assertLess(rendered.index("MOTIVATIONAL QUOTE"), rendered.index("RATIONALE"))
        self.assertLess(rendered.index("RATIONALE"), rendered.index("RECOMMENDATION"))
        self.assertLess(rendered.index("RECOMMENDATION"), rendered.index("SUPPORTING FACTS"))
        self.assertNotIn("Theme:", rendered)
        self.assertNotIn("Insight:", rendered)

    def test_quiet_path_display_uses_reason_not_surfaced(self) -> None:
        rendered = format_health_coach_output(
            {
                "status": "NO_SIGNIFICANT_NEW_PATTERN",
                "reason_not_surfaced": "Detectable changes stayed below insight salience.",
                "primary_message": None,
            }
        )
        self.assertEqual(rendered, "Detectable changes stayed below insight salience.")
        self.assertNotIn("PRIMARY MESSAGE", rendered)


class SeededContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.session = open_test_session()
        cls.user = seed_demo_health_data(cls.session)

    def tearDown(self) -> None:
        self.session.rollback()

    def _signals(self, as_of: date) -> dict:
        return get_health_trends_for_agent(self.user.id, as_of_date=as_of)

    def test_a1_stamps_sleep_primary_and_keeps_rationale_separate(self) -> None:
        signals = self._signals(A1)
        self.assertTrue(signals["insight_salience"]["insight_worthy"])
        facts = stamp_supporting_metric_facts(signals)
        sleep = next(item for item in facts if item["metric"] == "sleep_duration_hours")
        self.assertEqual(sleep["role"], ROLE_PRIMARY)
        self.assertEqual(sleep["direction"], "decreasing")
        self.assertLess(sleep["percent_change"], -10)
        updated, decision = apply_output_interpretation_contract(
            {
                "status": "INSIGHT",
                "primary_message": "Sleep duration declined.",
                "subtext": "Down about 18% across the available week.",
                "motivational_quote": "Prioritize rest — it's the foundation of performance.",
                "insight": "Average sleep moved from about 7.1 to 5.8 hours while other observations were mixed.",
                "recommendation": None,
                "supporting_metric_facts": [{"metric": "invented", "role": "primary"}],
            },
            signals=signals,
        )
        self.assertEqual(updated["status"], "INSIGHT")
        self.assertEqual(updated["primary_message"], "Sleep duration declined.")
        self.assertEqual(
            updated["motivational_quote"],
            "Prioritize rest — it's the foundation of performance.",
        )
        self.assertIn("7.1", updated["insight"])
        self.assertNotEqual(updated["motivational_quote"], updated["insight"])
        self.assertNotEqual(updated["motivational_quote"], updated["recommendation"])
        self.assertNotEqual(updated["primary_message"], updated["insight"])
        self.assertFalse(any(item.get("metric") == "invented" for item in updated["supporting_metric_facts"]))
        self.assertTrue(decision.insight_worthy)
        self.assertEqual(sleep["origin"], ORIGIN_DETERMINISTIC_ANALYTICS)

    def test_b1_quiet_path_clears_primary_card(self) -> None:
        signals = self._signals(B1)
        self.assertFalse(signals["insight_salience"]["insight_worthy"])
        facts = stamp_supporting_metric_facts(signals)
        self.assertFalse(any(item["role"] == ROLE_PRIMARY for item in facts))
        updated, decision = apply_output_interpretation_contract(
            {
                "status": "INSIGHT",
                "primary_message": "Daily steps increased.",
                "subtext": "A small activity bump.",
                "motivational_quote": "Keep moving forward.",
                "insight": "Steps and exercise ticked up slightly.",
            },
            signals=signals,
        )
        self.assertEqual(updated["status"], HealthCoachStatus.NO_SIGNIFICANT_NEW_PATTERN.value)
        self.assertIsNone(updated["primary_message"])
        self.assertIsNone(updated["subtext"])
        self.assertIsNone(updated["motivational_quote"])
        self.assertTrue(decision.quiet_path_applied)
        self.assertTrue(decision.motivational_quote_removed_on_quiet_path)
        self.assertIn("elevated_status_without_insight_worthiness", decision.violations)

    def test_b3_maintenance_facts_without_recommendation(self) -> None:
        signals = self._signals(B3)
        salience = signals["insight_salience"]
        self.assertTrue(salience["insight_worthy"])
        self.assertFalse(salience["recommendation_worthy"])
        facts = stamp_supporting_metric_facts(signals)
        by_metric = {item["metric"]: item for item in facts if item["role"] == ROLE_PRIMARY}
        for metric in ("resting_hr_bpm", "hrv_sdnn_ms", "vo2_max"):
            self.assertIn(metric, by_metric)
            self.assertTrue(by_metric[metric]["maintenance_of_gain"])
        structured, _boundary = apply_recommendation_boundary(
            {
                "status": "INSIGHT",
                "primary_message": "Resting heart rate, HRV, and VO2 remain improved versus the earlier baseline.",
                "motivational_quote": "Consistency is what turns progress into habit.",
                "insight": "Those named metrics are still better than the older personal reference.",
                "recommendation": "Maintain your regular aerobic exercise habit.",
            },
            insight_worthy=True,
            recommendation_worthy=False,
            recommendation_authorized=True,
        )
        stamped, _decision = apply_output_interpretation_contract(structured, signals=signals)
        self.assertEqual(stamped["status"], "INSIGHT")
        self.assertIsNone(stamped["recommendation"])
        self.assertFalse(stamped["final_recommendation_allowed"])
        self.assertTrue(stamped["primary_message"])
        self.assertEqual(
            stamped["motivational_quote"],
            "Consistency is what turns progress into habit.",
        )

    def test_c2_does_not_stamp_a_lifestyle_cause(self) -> None:
        signals = self._signals(C2)
        facts = stamp_supporting_metric_facts(signals)
        sleep = next(item for item in facts if item["metric"] == "sleep_duration_hours")
        self.assertEqual(sleep["role"], ROLE_PRIMARY)
        self.assertEqual(sleep["direction"], "decreasing")
        self.assertFalse(any("cause" in item for item in facts))
        self.assertFalse(any(item.get("metric") in {"caffeine", "alcohol", "late_work"} for item in facts))
        lifestyle = get_lifestyle_context_for_agent(self.user.id, as_of_date=C2)
        self.assertGreaterEqual(lifestyle["event_count"], 1)
        types = {item.get("event_type") for item in lifestyle.get("events") or []}
        self.assertTrue({"caffeine", "alcohol"} & types or lifestyle.get("late_work_context_event_count"))

    def test_e1_sleep_primary_respiratory_control_only(self) -> None:
        facts = stamp_supporting_metric_facts(self._signals(E1))
        grouped = _facts_by_role(facts)
        sleep = next(item for item in grouped[ROLE_PRIMARY] if item["metric"] == "sleep_duration_hours")
        self.assertEqual(sleep["direction"], "decreasing")
        rr = next(item for item in grouped[ROLE_CONTROL] if item["metric"] == "respiratory_rate")
        self.assertEqual(rr["direction"], "stable")
        self.assertTrue(rr["control_metric"])
        self.assertNotEqual(rr["role"], ROLE_PRIMARY)
        hrv = next((item for item in facts if item["metric"] == "hrv_sdnn_ms" and item["role"] != ROLE_SPREAD_CONTEXT), None)
        if hrv is not None:
            self.assertEqual(hrv["direction"], "improving")
            self.assertNotEqual(hrv["direction"], sleep["direction"])

    def test_c4_keeps_hrv_level_and_spread_distinct(self) -> None:
        facts = stamp_supporting_metric_facts(self._signals(C4))
        sleep = next(item for item in facts if item["metric"] == "sleep_duration_hours")
        self.assertEqual(sleep["role"], ROLE_PRIMARY)
        self.assertEqual(sleep["direction"], "decreasing")
        hrv_level = next(
            item
            for item in facts
            if item["metric"] == "hrv_sdnn_ms" and item["role"] == ROLE_SUPPORTING
        )
        hrv_spread = next(
            item
            for item in facts
            if item["metric"] == "hrv_sdnn_ms" and item["role"] == ROLE_SPREAD_CONTEXT
        )
        self.assertEqual(hrv_level["direction"], "improving")
        self.assertNotEqual(hrv_level["direction"], "declining")
        self.assertGreater(hrv_spread["spread_ratio"], 2.0)
        self.assertEqual(hrv_spread["origin"], ORIGIN_SPREAD_ANALYTICS)
        self.assertTrue(hrv_spread["spread_comparison_allowed"])

    def test_mixed_signal_facts_keep_separate_directions(self) -> None:
        facts = stamp_supporting_metric_facts(self._signals(E1))
        directions = {
            item["metric"]: item["direction"]
            for item in facts
            if item["role"] != ROLE_SPREAD_CONTEXT and item.get("direction")
        }
        self.assertEqual(directions["sleep_duration_hours"], "decreasing")
        self.assertEqual(directions["respiratory_rate"], "stable")
        self.assertIn(directions.get("hrv_sdnn_ms"), {None, "improving"})
        self.assertNotEqual(len(set(directions.values())), 1)

    def test_runner_stamps_facts_and_trace_fields(self) -> None:
        context = RunContext(scenario_id="HC-EVAL-A1", user_id=self.user.id, as_of_date=A1)
        context.candidate_signals = self._signals(A1)
        context.last_policy_decision = _empty_policy(authorized=False)
        structured = {
            "status": "INSIGHT",
            "primary_message": "Sleep duration declined.",
            "subtext": "Down about 18%.",
            "insight": "Sleep moved from about 7.1 to 5.8 hours.",
            "recommendation": None,
        }
        updated = _apply_output_interpretation_contract(context=context, structured=structured)
        self.assertTrue(any(item["role"] == ROLE_PRIMARY for item in updated["supporting_metric_facts"]))
        self.assertEqual(context.output_contract["supporting_metric_facts_origin"], ORIGIN_OUTPUT_CONTRACT)
        guarded = _apply_output_guard(
            context=context,
            structured=updated,
            scenario_id="HC-EVAL-A1",
            user_id=self.user.id,
            as_of_date="2026-08-02",
        )
        self.assertEqual(guarded["status"], "INSIGHT")
        self.assertTrue(context.final_guard.passed)
        trace = empty_trace(scenario_id="HC-EVAL-A1", user_id=self.user.id, as_of_date="2026-08-02")
        trace.output_contract = context.output_contract
        trace.raw_model_output = {"status": "INSIGHT", "primary_message": "Sleep duration declined."}
        payload = trace.to_dict()
        self.assertEqual(payload["raw_model_output"]["primary_message"], "Sleep duration declined.")
        self.assertIn("supporting_metric_facts", payload["output_contract"])
        self.assertTrue(any(item["role"] == ROLE_CONTROL for item in updated["supporting_metric_facts"]))


class MotivationalQuoteContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.session = open_test_session()
        cls.user = seed_demo_health_data(cls.session)

    def tearDown(self) -> None:
        self.session.rollback()

    def _signals(self, as_of: date) -> dict:
        return get_health_trends_for_agent(self.user.id, as_of_date=as_of)

    def test_prompt_treats_quote_as_optional_encouragement(self) -> None:
        text = HEALTH_COACH_INSTRUCTIONS
        self.assertIn("motivational_quote", text)
        self.assertIn("optional product encouragement", text)
        self.assertIn("Do not invent an author", text)
        self.assertIn("Do not add physiological-state", text)

    def test_a1_quote_may_exist_without_new_health_claim(self) -> None:
        updated, decision = apply_output_interpretation_contract(
            {
                "status": "INSIGHT",
                "primary_message": "Sleep needs attention.",
                "motivational_quote": "Prioritize rest — it's the foundation of performance.",
                "insight": "Average sleep moved from about 7.1 to 5.8 hours.",
                "recommendation": None,
            },
            signals=self._signals(A1),
        )
        self.assertEqual(updated["status"], "INSIGHT")
        self.assertTrue(updated["motivational_quote"])
        self.assertNotIn("cardiovascular", updated["motivational_quote"].lower())
        self.assertIsNone(updated["recommendation"])
        self.assertTrue(decision.motivational_quote_present)
        self.assertFalse(decision.motivational_quote_removed_on_quiet_path)

    def test_quiet_path_guard_rejects_leftover_quote(self) -> None:
        result = check_final_output(
            "Keep moving forward.",
            decision=_empty_policy(),
            structured={
                "status": "NO_SIGNIFICANT_NEW_PATTERN",
                "primary_message": None,
                "motivational_quote": "Keep moving forward.",
            },
        )
        self.assertFalse(result.passed)
        self.assertIn("motivational_quote_on_quiet_path", result.violations)

    def test_blocked_recommendation_cannot_hide_in_quote(self) -> None:
        result = check_final_output(
            _guard_text(
                {
                    "status": "INSIGHT",
                    "primary_message": "Sleep needs attention.",
                    "motivational_quote": "You should take a 45-minute walk today.",
                    "recommendation": None,
                }
            ),
            decision=_empty_policy(authorized=False),
            recommendation_worthy=False,
            structured={
                "status": "INSIGHT",
                "primary_message": "Sleep needs attention.",
                "motivational_quote": "You should take a 45-minute walk today.",
                "recommendation": None,
            },
        )
        self.assertFalse(result.passed)
        self.assertIn("unauthorized_recommendation_language", result.violations)

    def test_e1_quote_does_not_mint_respiratory_interpretation(self) -> None:
        updated, _decision = apply_output_interpretation_contract(
            {
                "status": "INSIGHT",
                "primary_message": "Sleep duration declined.",
                "motivational_quote": "Prioritize rest — it's the foundation of performance.",
                "insight": "Sleep is the more specific change; respiratory rate remained stable as control context.",
            },
            signals=self._signals(E1),
        )
        quote = updated["motivational_quote"] or ""
        self.assertNotIn("respiratory", quote.lower())
        self.assertNotIn("cardiovascular", quote.lower())
        self.assertNotIn("nervous system", quote.lower())

    def test_c4_quote_does_not_interpret_spread(self) -> None:
        updated, _decision = apply_output_interpretation_contract(
            {
                "status": "INSIGHT",
                "primary_message": "Sleep duration declined.",
                "motivational_quote": "Rest well tonight and start fresh tomorrow.",
                "insight": "Average HRV has not declined, although nightly readings varied more than the recent baseline.",
            },
            signals=self._signals(C4),
        )
        quote = (updated["motivational_quote"] or "").lower()
        self.assertNotIn("stress", quote)
        self.assertNotIn("recovery", quote)
        self.assertNotIn("hrv", quote)

    def test_trace_records_raw_and_removed_quote(self) -> None:
        context = RunContext(scenario_id="HC-EVAL-B1", user_id=self.user.id, as_of_date=B1)
        context.candidate_signals = self._signals(B1)
        raw = {
            "status": "INSIGHT",
            "primary_message": "Steps ticked up.",
            "motivational_quote": "Keep moving forward.",
        }
        updated = _apply_output_interpretation_contract(context=context, structured=raw)
        self.assertIsNone(updated["motivational_quote"])
        self.assertTrue(context.output_contract["model_motivational_quote_present"])
        self.assertFalse(context.output_contract["motivational_quote_present"])
        self.assertTrue(context.output_contract["motivational_quote_removed_on_quiet_path"])
        trace = empty_trace(scenario_id="HC-EVAL-B1", user_id=self.user.id, as_of_date="2026-06-18")
        trace.raw_model_output = raw
        trace.output_contract = context.output_contract
        payload = trace.to_dict()
        self.assertEqual(payload["raw_model_output"]["motivational_quote"], "Keep moving forward.")
        self.assertTrue(payload["output_contract"]["motivational_quote_removed_on_quiet_path"])


if __name__ == "__main__":
    unittest.main()
