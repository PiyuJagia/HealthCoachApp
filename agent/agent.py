"""Build the Google ADK Health Coach agent."""

from __future__ import annotations

from datetime import date

from google.adk.agents import Agent

from agent.instructions import HEALTH_COACH_INSTRUCTIONS
from agent.model_observe import bind_model_observation_callbacks
from agent.tools import RunContext, build_tools

MODEL = "gemini-3.6-flash"
AGENT_NAME = "health_coach_agent"
MAX_LLM_CALLS = 8


def build_health_coach_agent(context: RunContext) -> Agent:
    get_trend_signals, get_lifestyle_context, retrieve_authorized_evidence = build_tools(context)
    return Agent(
        name=AGENT_NAME,
        model=MODEL,
        instruction=HEALTH_COACH_INSTRUCTIONS,
        tools=[get_trend_signals, get_lifestyle_context, retrieve_authorized_evidence],
        **bind_model_observation_callbacks(context),
    )


def build_review_prompt(*, scenario_id: str, user_id: int, as_of_date: date) -> str:
    return (
        f"Perform a bounded health review.\n"
        f"scenario_id={scenario_id}\n"
        f"user_id={user_id}\n"
        f"as_of_date={as_of_date.isoformat()}\n"
        "Inspect deterministic signals, investigate only meaningful patterns, "
        "use authorized evidence when needed, and return the required JSON object."
    )
