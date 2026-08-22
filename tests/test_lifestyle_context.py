"""Offline tests for F4.4 lifestyle-context access."""

from __future__ import annotations

import unittest
from datetime import date, datetime
from unittest.mock import patch

from agent.model_observe import extract_lifestyle_context, observe_llm_request
from agent.tools import RunContext, build_tools
from app.lifestyle_tools import (
    DEFAULT_LOOKBACK_DAYS,
    get_lifestyle_context_for_agent,
    policy_inputs_from_events,
)
from data.demo_seed import seed_demo_health_data
from data.models import LifestyleEvent
from data.repository import add_lifestyle_event, create_user
from evals.lifestyle_inspection import inspect_c1_c2_c3
from evals.trace_schema import ORIGIN_LIFESTYLE_TOOL
from google.genai import types
from rag.evidence_policy import AuthorizationVerdict, evaluate_retrieved_evidence
from rag.relationship_policy import EvaluationOutcome, evaluate_relationship_request
from rag.schemas import RetrievalResult
from tests.test_helpers import open_test_session
from tests.test_model_observe import _sample_request


def _r07_result() -> RetrievalResult:
    return RetrievalResult(
        vector_id="r07__chunk_0001",
        score=0.8,
        text="Later caffeine intake is associated with shorter sleep.",
        document_id="healthcoach_correlation_modeling",
        source_title="Correlation modeling",
        section_heading="R-07",
        chunk_index=1,
        version="L2-CR-002",
        evidence_level="curated_evidence_synthesis",
        evidence_grade="verified_with_constraints",
        verification_status="verified_with_constraints",
        relationship_id="R-07",
        relationship_status="active",
        evidence_strength="moderate",
        measurement_transfer_risk="moderate",
        max_product_level="4",
        recommendation_eligible="true",
        modifier_suppressor_only="false",
        mandatory_contradiction_suppression="false",
    )


class LifestyleToolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session = open_test_session()
        self.user = seed_demo_health_data(self.session, reset=True)

    def tearDown(self) -> None:
        self.session.close()

    def test_returns_correct_events_for_user_date_lookback(self) -> None:
        as_of = date(2026, 8, 2)
        payload = get_lifestyle_context_for_agent(self.user.id, as_of_date=as_of, lookback_days=14)
        self.assertEqual(payload["lookback_days"], 14)
        self.assertEqual(payload["window_start"], "2026-07-20")
        self.assertEqual(payload["window_end"], "2026-08-02")
        caffeine = [event for event in payload["events"] if event["event_type"] == "caffeine"]
        self.assertEqual(len(caffeine), 7)
        self.assertTrue(all(event["occurred_on"] >= "2026-07-20" for event in payload["events"]))
        self.assertTrue(all(event["occurred_on"] <= "2026-08-02" for event in payload["events"]))

    def test_another_users_events_are_excluded(self) -> None:
        other = create_user(self.session, display_name="Other User")
        add_lifestyle_event(
            self.session,
            LifestyleEvent(
                user_id=other.id,
                occurred_at=datetime(2026, 8, 2, 16, 0),
                event_type="caffeine",
                quantity=999,
                unit="mg",
                notes="Other user coffee",
            ),
        )
        self.session.commit()
        payload = get_lifestyle_context_for_agent(self.user.id, as_of_date=date(2026, 8, 2))
        notes = {event["notes"] for event in payload["events"]}
        self.assertNotIn("Other user coffee", notes)
        quantities = [event["quantity"] for event in payload["events"] if event["event_type"] == "caffeine"]
        self.assertNotIn(999, quantities)

    def test_empty_lifestyle_window_is_handled(self) -> None:
        empty_user = create_user(self.session, display_name="No Events")
        self.session.commit()
        payload = get_lifestyle_context_for_agent(empty_user.id, as_of_date=date(2026, 8, 2))
        self.assertEqual(payload["event_count"], 0)
        self.assertEqual(payload["events"], [])
        self.assertEqual(payload["policy_available_inputs"], [])
        self.assertEqual(payload["late_work_context_event_count"], 0)

    def test_caffeine_quantity_unit_and_timing_preserved(self) -> None:
        payload = get_lifestyle_context_for_agent(self.user.id, as_of_date=date(2026, 8, 2))
        caffeine = [event for event in payload["events"] if event["event_type"] == "caffeine"]
        self.assertTrue(caffeine)
        self.assertTrue(all(event["quantity"] == 200 for event in caffeine))
        self.assertTrue(all(event["unit"] == "mg" for event in caffeine))
        self.assertTrue(all(event["hour"] == 16 for event in caffeine))

    def test_late_work_and_mood_notes_preserved(self) -> None:
        payload = get_lifestyle_context_for_agent(self.user.id, as_of_date=date(2026, 7, 31))
        notes = [event["notes"] for event in payload["events"] if event["notes"]]
        self.assertTrue(any("late work" in note.lower() for note in notes))
        self.assertTrue(any(event["event_type"] == "mood" for event in payload["events"]))
        self.assertGreater(payload["late_work_context_event_count"], 0)

    def test_lifestyle_data_is_deterministic(self) -> None:
        as_of = date(2026, 8, 2)
        first = get_lifestyle_context_for_agent(self.user.id, as_of_date=as_of)
        second = get_lifestyle_context_for_agent(self.user.id, as_of_date=as_of)
        self.assertEqual(first["events"], second["events"])
        self.assertEqual(first["policy_available_inputs"], second["policy_available_inputs"])

    def test_missing_lifestyle_data_does_not_invent_available_inputs(self) -> None:
        empty_user = create_user(self.session, display_name="Empty Inputs")
        self.session.commit()
        payload = get_lifestyle_context_for_agent(empty_user.id, as_of_date=date(2026, 8, 2))
        self.assertEqual(payload["policy_available_inputs"], [])
        self.assertEqual(policy_inputs_from_events([]), [])

    def test_lifestyle_presence_does_not_authorize_recommendation(self) -> None:
        payload = get_lifestyle_context_for_agent(self.user.id, as_of_date=date(2026, 8, 2))
        self.assertIn("caffeine_mg", payload["policy_available_inputs"])
        self.assertNotIn("recommendation_authorized", payload)
        decision = evaluate_retrieved_evidence(
            [],
            available_inputs=set(payload["policy_available_inputs"]),
        )
        self.assertFalse(decision.recommendation_authorized)
        self.assertEqual(decision.overall_verdict, AuthorizationVerdict.SUPPRESS)

    def test_policy_inputs_from_caffeine_mg(self) -> None:
        payload = get_lifestyle_context_for_agent(self.user.id, as_of_date=date(2026, 8, 2))
        self.assertEqual(set(payload["policy_available_inputs"]), {"alcohol_units", "caffeine_mg"})
        outcome = evaluate_relationship_request(
            "R-07", available_inputs=set(payload["policy_available_inputs"])
        )
        self.assertEqual(outcome, EvaluationOutcome.RELATIONSHIP_DETECTED)

    def test_existing_r07_gate_without_inputs_remains(self) -> None:
        outcome = evaluate_relationship_request("R-07", available_inputs=set())
        self.assertEqual(outcome, EvaluationOutcome.INPUT_UNAVAILABLE)
        decision = evaluate_retrieved_evidence([_r07_result()], available_inputs=None)
        self.assertFalse(decision.relationship_decisions[0].evidence_authorized)
        self.assertFalse(decision.recommendation_authorized)


class LifestyleAgentWiringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session = open_test_session()
        self.user = seed_demo_health_data(self.session, reset=True)
        self.context = RunContext(
            scenario_id="HC-EVAL-C1",
            user_id=self.user.id,
            as_of_date=date(2026, 8, 2),
        )
        self.get_trend_signals, self.get_lifestyle_context, self.retrieve_authorized_evidence = (
            build_tools(self.context)
        )

    def tearDown(self) -> None:
        self.session.close()

    def test_lifestyle_context_is_adk_visible(self) -> None:
        payload = self.get_lifestyle_context()
        self.assertGreater(payload["event_count"], 0)
        self.assertEqual(self.context.tool_calls[-1].tool_name, "get_lifestyle_context")
        phases = [step["phase"] for step in self.context.activity_log]
        self.assertIn("ACT", phases)
        self.assertIn("OBSERVE", phases)
        names = {getattr(tool, "name", getattr(tool, "__name__", "")) for tool in (
            self.get_trend_signals,
            self.get_lifestyle_context,
            self.retrieve_authorized_evidence,
        )}
        self.assertEqual(
            names,
            {"get_trend_signals", "get_lifestyle_context", "retrieve_authorized_evidence"},
        )

    def test_policy_available_inputs_flow_into_evidence_evaluation(self) -> None:
        self.get_lifestyle_context()
        with patch("agent.tools.agent_tools.retrieve_evidence", return_value=[_r07_result()]):
            result = self.retrieve_authorized_evidence("caffeine sleep association")
        self.assertIn("caffeine_mg", result["available_inputs"])
        rel = result["policy"]["relationship_decisions"][0]
        self.assertEqual(rel["relationship_id"], "R-07")
        self.assertTrue(rel["evidence_authorized"])
        self.assertNotEqual(rel["evaluation_outcome"], "input_unavailable")

    def test_missing_lifestyle_lookup_does_not_invent_inputs(self) -> None:
        with patch("agent.tools.agent_tools.retrieve_evidence", return_value=[_r07_result()]):
            result = self.retrieve_authorized_evidence("caffeine sleep association")
        self.assertEqual(result["available_inputs"], [])
        rel = result["policy"]["relationship_decisions"][0]
        self.assertEqual(rel["evaluation_outcome"], "input_unavailable")
        self.assertFalse(rel["recommendation_authorized"])


class LifestyleTraceTests(unittest.TestCase):
    def test_trace_records_origin_lifestyle_context(self) -> None:
        request = _sample_request()
        request.contents.append(
            types.Content(
                role="model",
                parts=[
                    types.Part(function_call=types.FunctionCall(name="get_lifestyle_context", args={}))
                ],
            )
        )
        request.contents.append(
            types.Content(
                role="user",
                parts=[
                    types.Part(
                        function_response=types.FunctionResponse(
                            name="get_lifestyle_context",
                            response={
                                "events": [
                                    {
                                        "event_type": "caffeine",
                                        "occurred_at": "2026-08-02 16:00:00",
                                        "quantity": 200,
                                        "unit": "mg",
                                    }
                                ],
                                "lookback_days": 14,
                                "window_start": "2026-07-20",
                                "window_end": "2026-08-02",
                                "event_count": 1,
                                "by_type": [{"event_type": "caffeine", "count": 1}],
                                "policy_available_inputs": ["caffeine_mg"],
                                "late_work_context_event_count": 0,
                            },
                        )
                    )
                ],
            )
        )
        captured = observe_llm_request(request, call_index=2)
        lifestyle_results = [
            item for item in captured.tool_results_visible if item["tool_name"] == "get_lifestyle_context"
        ]
        self.assertEqual(len(lifestyle_results), 1)
        self.assertEqual(lifestyle_results[0]["origin"], ORIGIN_LIFESTYLE_TOOL)
        self.assertEqual(ORIGIN_LIFESTYLE_TOOL, "lifestyle_context")
        assert captured.lifestyle_context_visible is not None
        self.assertEqual(captured.lifestyle_context_visible["origin"], "lifestyle_context")
        self.assertEqual(captured.lifestyle_context_visible["policy_available_inputs"], ["caffeine_mg"])
        provenance = next(item for item in captured.provenance if item.component == "lifestyle_context")
        self.assertTrue(provenance.present)
        extracted = extract_lifestyle_context(lifestyle_results[0]["payload"])
        assert extracted is not None
        self.assertEqual(extracted["lookback_days"], 14)


class LifestyleInspectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.session = open_test_session()
        cls.user = seed_demo_health_data(cls.session, reset=True)
        cls.report = inspect_c1_c2_c3(cls.session, cls.user.id)
        cls.by_id = {item["scenario_id"]: item for item in cls.report["scenarios"]}

    @classmethod
    def tearDownClass(cls) -> None:
        cls.session.close()

    def test_c1_matches_seed_caffeine_cluster(self) -> None:
        c1 = self.by_id["HC-EVAL-C1"]
        self.assertEqual(c1["lookback_days"], DEFAULT_LOOKBACK_DAYS)
        self.assertEqual(c1["caffeine_count"], 7)
        self.assertEqual(c1["caffeine_hours"], [16] * 7)
        self.assertEqual(c1["caffeine_quantities"], [200] * 7)
        self.assertGreater(c1["late_work_context_event_count"], 0)
        self.assertIn("caffeine_mg", c1["policy_available_inputs"])
        self.assertEqual(
            c1["relationship_preview_if_retrieved"]["R-07"]["evaluation_outcome_if_retrieved"],
            "relationship_detected",
        )

    def test_c2_keeps_caffeine_and_late_work(self) -> None:
        c2 = self.by_id["HC-EVAL-C2"]
        self.assertGreater(c2["caffeine_count"], 0)
        self.assertGreater(c2["late_work_context_event_count"], 0)
        self.assertTrue(c2["late_work_notes_preserved"])
        self.assertTrue(self.report["controls"]["c2_multiple_cooccurring_factors"])

    def test_c3_caffeine_with_stable_sleep_does_not_invent_a_problem(self) -> None:
        c3 = self.by_id["HC-EVAL-C3"]
        self.assertGreater(c3["caffeine_count"], 0)
        self.assertEqual(c3["sleep_direction"], "stable")
        self.assertIn("caffeine_mg", c3["policy_available_inputs"])
        self.assertFalse(c3["manufactures_problem"])
        self.assertTrue(self.report["controls"]["c3_does_not_manufacture_caffeine_problem"])
        self.assertTrue(self.report["controls"]["no_causal_scoring"])


if __name__ == "__main__":
    unittest.main()
