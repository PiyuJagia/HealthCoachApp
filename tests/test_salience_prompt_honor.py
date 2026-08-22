"""Local tests that the prompt/output contract honors F4.6 insight_worthy."""

from __future__ import annotations

import inspect
import unittest
from datetime import date, timedelta

from agent.agent import build_health_coach_agent
from agent.instructions import HEALTH_COACH_INSTRUCTIONS
from agent.model_observe import observe_llm_request
from agent.tools import RunContext, build_tools
from analytics.maturity import STATE_EARLY_PATTERN
from analytics.trends import get_health_trends
from app.health_tools import get_health_trends_for_agent
from app.lifestyle_tools import get_lifestyle_context_for_agent
from app.output_guard import check_final_output
from data.demo_seed import seed_demo_health_data
from data.models import HealthDaily
from data.repository import create_user, upsert_health_daily
from evals.trace_schema import ORIGIN_SALIENCE_ANALYTICS
from rag.evidence_policy import AuthorizationVerdict, EvidencePolicyDecision
from tests.test_helpers import open_test_session
from tests.test_model_observe import _sample_request

B1 = date(2026, 6, 18)
A1 = date(2026, 8, 2)
B3 = date(2026, 8, 17)
C3 = date(2026, 6, 29)


def _empty_policy() -> EvidencePolicyDecision:
    return EvidencePolicyDecision(
        overall_verdict=AuthorizationVerdict.SURFACE,
        evidence_authorized=True,
        recommendation_authorized=False,
        reasons=("general_corpus_evidence_only",),
        relationship_decisions=(),
        general_evidence=(),
        authorized_results=(),
        suppressed_relationship_ids=(),
    )


class PromptHonorContractTests(unittest.TestCase):
    def test_instructions_require_deterministic_insight_worthy(self) -> None:
        text = HEALTH_COACH_INSTRUCTIONS
        self.assertIn("insight_salience.insight_worthy", text)
        self.assertIn("deterministic authority", text)
        self.assertIn("not by itself permission to emit INSIGHT", text)
        self.assertIn("Use INSIGHT only when insight_salience.insight_worthy is true", text)
        self.assertIn("maintenance_of_gain even when recent direction is stable", text)
        self.assertIn("Do not infer salience from lifestyle events", text)
        self.assertIn("recommendation_worthy is a product/salience flag, not recommendation authorization", text)
        self.assertIn("final_recommendation_allowed=true", text)
        self.assertIn("established personalized trend", text)
        self.assertIn("Do not recompute salience", text)
        self.assertIn("Do not expose hidden chain-of-thought", text)

    def test_agent_instruction_is_the_honor_contract(self) -> None:
        context = RunContext(scenario_id="HC-EVAL-B1", user_id=1, as_of_date=B1)
        agent = build_health_coach_agent(context)
        self.assertEqual(agent.instruction, HEALTH_COACH_INSTRUCTIONS)

    def test_trend_tool_docstring_forbids_promoting_non_worthy_direction(self) -> None:
        context = RunContext(scenario_id="HC-EVAL-B1", user_id=1, as_of_date=B1)
        get_trend_signals, _, _ = build_tools(context)
        doc = inspect.getdoc(get_trend_signals) or ""
        self.assertIn("insight_worthy is false", doc)
        self.assertIn("do not return INSIGHT status", doc)
        self.assertIn("improving or declining", doc)

    def test_guard_does_not_enforce_insight_worthy(self) -> None:
        result = check_final_output(
            "Daily step counts have increased over the past week to an average of nearly 10,900 steps.",
            decision=_empty_policy(),
        )
        self.assertTrue(result.passed)
        source = inspect.getsource(check_final_output)
        self.assertNotIn("insight_worthy", source)


class PromptHonorScenarioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.session = open_test_session()
        cls.user = seed_demo_health_data(cls.session, reset=True)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.session.close()

    def _payload(self, as_of: date) -> dict:
        return get_health_trends_for_agent(self.user.id, as_of_date=as_of)

    def test_b1_improving_remains_visible_but_not_insight_worthy(self) -> None:
        payload = self._payload(B1)
        by_metric = {item["metric"]: item for item in payload["trends"]}
        self.assertEqual(by_metric["steps"]["direction"], "improving")
        self.assertEqual(by_metric["exercise_minutes"]["direction"], "improving")
        self.assertFalse(payload["insight_salience"]["insight_worthy"])
        self.assertIn("same_family_weak_corroboration", payload["insight_salience"]["reasons"])
        self.assertIn("Use INSIGHT only when insight_salience.insight_worthy is true", HEALTH_COACH_INSTRUCTIONS)
        self.assertIn("even if they are improving or declining", HEALTH_COACH_INSTRUCTIONS)

    def test_a1_strong_sleep_decline_remains_insight_eligible(self) -> None:
        payload = self._payload(A1)
        sleep = next(item for item in payload["trends"] if item["metric"] == "sleep_duration_hours")
        self.assertTrue(payload["insight_salience"]["insight_worthy"])
        self.assertTrue(sleep["salience"]["insight_candidate"])
        self.assertEqual(sleep["salience"]["magnitude_band"], "strong")
        self.assertIn("sleep_duration_hours", payload["insight_salience"]["primary_metrics"])

    def test_b3_stable_maintenance_remains_insight_eligible(self) -> None:
        payload = self._payload(B3)
        rhr = next(item for item in payload["trends"] if item["metric"] == "resting_hr_bpm")
        self.assertEqual(rhr["direction"], "stable")
        self.assertTrue(rhr["longitudinal"]["maintenance_of_gain"])
        self.assertTrue(payload["insight_salience"]["insight_worthy"])
        self.assertFalse(payload["insight_salience"]["recommendation_worthy"])
        self.assertIn("maintenance_of_gain even when recent direction is stable", HEALTH_COACH_INSTRUCTIONS)
        self.assertIn("recommendation_worthy is a product/salience flag, not recommendation authorization", HEALTH_COACH_INSTRUCTIONS)

    def test_c3_lifestyle_cannot_promote_non_salient_sleep(self) -> None:
        payload = self._payload(C3)
        sleep = next(item for item in payload["trends"] if item["metric"] == "sleep_duration_hours")
        lifestyle = get_lifestyle_context_for_agent(self.user.id, as_of_date=C3)
        self.assertEqual(sleep["direction"], "stable")
        self.assertFalse(sleep["salience"]["insight_candidate"])
        self.assertGreater(lifestyle["event_count"], 0)
        self.assertIn("caffeine_mg", lifestyle["policy_available_inputs"])
        self.assertIn("Do not infer salience from lifestyle events", HEALTH_COACH_INSTRUCTIONS)
        self.assertIn("do not promote a metric that is not insight_candidate", HEALTH_COACH_INSTRUCTIONS)

    def test_early_pattern_may_surface_without_mature_trend_claim(self) -> None:
        start = date(2026, 6, 1)
        user = create_user(self.session, display_name="Prompt Honor Early")
        self.session.flush()
        for offset in range(12):
            sleep = 7.5 if offset < 5 else 5.4
            upsert_health_daily(
                self.session,
                HealthDaily(
                    user_id=user.id,
                    date=start + timedelta(days=offset),
                    sleep_duration_hours=sleep,
                    resting_hr_bpm=70.0,
                    hrv_sdnn_ms=24.0 if offset >= 5 else 32.0,
                    exercise_minutes=12.0,
                    workout_count=0,
                    steps=8000,
                    vo2_max=40.0,
                ),
            )
        self.session.commit()
        as_of = start + timedelta(days=11)
        trend = next(
            item
            for item in get_health_trends(self.session, user.id, as_of_date=as_of)
            if item.metric == "sleep_duration_hours"
        )
        self.assertEqual(trend.data_maturity_state, STATE_EARLY_PATTERN)
        self.assertFalse(trend.claim_eligibility.trend_allowed)
        self.assertTrue(trend.claim_eligibility.early_pattern_allowed)
        self.assertEqual(trend.direction, "unknown")
        self.assertTrue(trend.salience.insight_candidate)
        self.assertIn("early_pattern_observation", trend.salience.reasons)
        self.assertIn("established personalized trend", HEALTH_COACH_INSTRUCTIONS)

    def test_trace_still_exposes_salience_without_cot(self) -> None:
        request = _sample_request()
        payload = request.contents[2].parts[0].function_response.response
        payload["insight_salience"] = {
            "insight_worthy": False,
            "recommendation_worthy": False,
            "primary_metrics": [],
            "reasons": ["same_family_weak_corroboration"],
        }
        payload["trends"][0]["salience"] = {
            "salience_level": "low",
            "magnitude_band": "barely_directional",
            "insight_candidate": False,
            "recommendation_candidate": False,
            "corroborating_metrics": [],
            "reasons": ["detectable_but_small_absolute"],
        }
        captured = observe_llm_request(request, call_index=0)
        self.assertIn("insight_salience.insight_worthy", captured.system_instruction or "")
        self.assertIn("Do not expose hidden chain-of-thought", captured.system_instruction or "")
        self.assertEqual(captured.omitted_thought_parts, 1)
        serialized = str(captured.to_dict())
        self.assertNotIn("hidden chain of thought", serialized)
        assert captured.insight_salience_visible is not None
        self.assertEqual(captured.insight_salience_visible["origin"], ORIGIN_SALIENCE_ANALYTICS)
        self.assertFalse(captured.insight_salience_visible["summary"]["insight_worthy"])


if __name__ == "__main__":
    unittest.main()
