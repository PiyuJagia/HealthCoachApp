"""Minimal Streamlit demo for Assignment 3 Path A — Health Coach ADK agent."""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")

from agent.display import (
    format_activity_lines,
    is_model_quota_exhausted,
    is_temporary_model_unavailable,
    model_quota_exhausted_message,
    policy_summary,
    summarize_trend_signals,
    temporary_unavailable_message,
)
from agent.runner import run_health_review
from agent.scenarios import SCENARIOS, resolve_demo_user_id
from app.agent_tools import get_trend_signals
from data.demo_seed import DEMO_DISPLAY_NAME, DEMO_GOAL

st.set_page_config(page_title="Health Coach Agent Demo", layout="wide")
st.title("HEALTH COACH AGENT DEMO")
st.caption(
    "This is an agent because it does not follow a fixed analysis sequence: "
    "it evaluates deterministic health signals, chooses which patterns warrant investigation, "
    "calls real evidence tools based on those observations, and decides what to surface "
    "within deterministic safety and authorization constraints. Stack: Google ADK + Gemini."
)

scenario_options = {scenario.label: scenario for scenario in SCENARIOS.values()}
selected_label = st.selectbox("Scenario / date", list(scenario_options.keys()))
scenario = scenario_options[selected_label]

st.markdown(f"**Demo user:** {DEMO_DISPLAY_NAME}")
st.markdown(f"**Goal:** {DEMO_GOAL}")
st.markdown(f"**Review date:** {scenario.as_of_date.isoformat()} ({scenario.scenario_id})")

if st.button("Analyze Health", type="primary"):
    with st.spinner("Running Health Coach agent..."):
        user_id = resolve_demo_user_id()
        trends = get_trend_signals(user_id, as_of_date=scenario.as_of_date)
        result = run_health_review(
            scenario_id=scenario.scenario_id,
            user_id=user_id,
            as_of_date=scenario.as_of_date,
        )

    st.subheader("A. HEALTH SIGNALS")
    st.dataframe(summarize_trend_signals(trends), use_container_width=True)

    st.subheader("B. AGENT ACTIVITY")
    for line in format_activity_lines(result.activity_log):
        if line.startswith("ACT:"):
            st.warning(line)
        elif line.startswith("OBSERVE:"):
            st.success(line)
        elif line.startswith("DECISION:"):
            st.info(line)
        else:
            st.markdown(line)

    st.subheader("C. EVIDENCE / POLICY")
    policy = policy_summary(result.structured)
    st.write(
        {
            "policy_verdict": policy["policy_verdict"],
            "recommendation_authorized": policy["recommendation_authorized"],
            "source_refs": policy["source_refs"],
        }
    )

    st.subheader("D. HEALTH COACH RESULT")
    structured = result.structured
    if is_temporary_model_unavailable(structured):
        st.warning(temporary_unavailable_message(structured))
    elif is_model_quota_exhausted(structured):
        st.warning(model_quota_exhausted_message(structured))
    elif structured.get("status") == "NO_SIGNIFICANT_NEW_PATTERN":
        st.write("No significant new pattern")
        summary = structured.get("insight") or structured.get("reason_not_surfaced")
        if summary:
            st.caption(summary)
    else:
        st.write(f"**Status:** {structured.get('status')}")
        if structured.get("theme"):
            st.write(f"**Theme:** {structured['theme']}")
        if structured.get("insight"):
            st.write(f"**Insight:** {structured['insight']}")
        if structured.get("recommendation"):
            st.write(f"**Recommendation:** {structured['recommendation']}")

    st.subheader("E. FINAL GUARD")
    st.write("PASS" if result.guard_passed else "BLOCKED")
    if result.guard_violations:
        st.code("\n".join(result.guard_violations))

    st.subheader("F. TRACE")
    st.write(f"run_id: `{result.trace_path.stem}`")
    st.write(f"trace file: `{result.trace_path}`")
    st.caption(f"latency_ms={result.latency_ms}")

    with st.expander("Debug — sanitized structured trace"):
        st.code(json.dumps(json.loads(result.trace_path.read_text(encoding="utf-8")), indent=2), language="json")
