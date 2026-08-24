"""Streamlit TRACE Evaluation Dashboard (Assignment 4). Display + CODIFY only."""

from __future__ import annotations

from typing import Any

import streamlit as st

from evals.dashboard import DashboardDataError, load_dashboard_bundle, run_deterministic_codify


def _chart_frame(baseline_pct: float, v2_pct: float) -> Any:
    try:
        import pandas as pd
    except ImportError:
        return None
    return pd.DataFrame(
        {"Scenario-quality pass rate (%)": [round(baseline_pct, 1), round(v2_pct, 1)]},
        index=["Baseline", "Post-remediation"],
    )


def render_trace_eval_dashboard() -> None:
    st.title("TRACE Evaluation Dashboard")
    st.caption(
        "Assignment 4 · baseline vs post-remediation measurement · "
        "READY WITH ACCEPTED MVP LIMITATIONS"
    )

    try:
        bundle = load_dashboard_bundle()
    except DashboardDataError as exc:
        st.error(str(exc))
        return

    score = bundle.scorecard

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("BASELINE", f"{score.baseline_pass} / {score.baseline_total} PASS", f"{score.baseline_pass_rate:.1f}%")
    c2.metric("POST-REMEDIATION", f"{score.v2_pass} / {score.v2_total} PASS", f"{score.v2_pass_rate:.1f}%")
    c3.metric("IMPROVEMENT", f"+{score.improvement_pp:.1f} pp")
    c4.metric("CODIFY", f"{score.codify_pass} PASS", f"{score.codify_fail} FAIL · {score.codify_na} N/A")

    st.caption(
        "Scenario-quality score is separate from deterministic contract compliance. "
        "100% V2 quality does not mean the product is perfect."
    )

    st.subheader("Scenario-quality pass rate")
    chart = _chart_frame(score.baseline_pass_rate, score.v2_pass_rate)
    if chart is not None:
        st.bar_chart(chart, height=220)
    else:
        st.write(f"Baseline {score.baseline_pass_rate:.1f}% → Post-remediation {score.v2_pass_rate:.1f}%")

    st.subheader("Failure → remediation")
    st.dataframe(list(bundle.remediation_examples), width="stretch", hide_index=True)

    st.subheader("Failure taxonomy")
    st.dataframe(
        [
            {
                "ID": row["id"],
                "Name": row["name"],
                "F7.1 status": row["status"],
                "Baseline scenarios": row["baseline_scenarios"],
            }
            for row in bundle.taxonomy_rows
        ],
        width="stretch",
        hide_index=True,
    )

    st.subheader("CODIFY deterministic checks")
    st.write(
        f"{score.deterministic_grader_count} graders · "
        f"archived run: {score.codify_pass} PASS / {score.codify_fail} FAIL / {score.codify_na} N/A "
        f"({score.codify_evaluations} evaluations)"
    )
    with st.expander("Grader catalog"):
        st.dataframe(bundle.grader_rows, width="stretch", hide_index=True)

    if st.button("Run deterministic TRACE checks", type="primary"):
        with st.spinner("Grading official post-remediation traces (no Gemini)..."):
            live = run_deterministic_codify()
        if not live["ok"]:
            st.error(live["error"] or "CODIFY run failed.")
        else:
            summary = live["summary"]
            st.success(
                f"PASS {summary.get('deterministic_pass', 0)} · "
                f"FAIL {summary.get('deterministic_fail', 0)} · "
                f"N/A {summary.get('deterministic_not_applicable', 0)}"
            )
            failed = live.get("failed_grader_ids") or []
            st.write("Failed grader IDs: none" if not failed else f"Failed grader IDs: {', '.join(failed)}")
            st.caption(f"{live['timestamp_utc']} · {live['trace_count']} official traces · in-memory only")

    st.subheader("Scenario comparison")
    st.dataframe(bundle.comparison_rows, width="stretch", hide_index=True)

    with st.expander("Known MVP limitations"):
        for item in bundle.known_limitations:
            st.write(f"- {item}")

    with st.expander("TRACE Assignment Evidence"):
        st.write("Target → Run → Analyze → Cluster → Evaluate / Codify → Remediate → Rerun")
        st.dataframe(list(bundle.evidence_rows), width="stretch", hide_index=True)
        st.caption("Frozen baseline labels were not overwritten. CODIFY does not call Gemini.")
