# F8 — Streamlit TRACE Evaluation Dashboard v1

UI / assignment packaging only. No product, prompt, analytics, guard, RAG, CODIFY-grader, or frozen-eval changes. No Gemini from the dashboard.

## Design

The existing Assignment 3 demo (`streamlit_agent_demo.py`) gained a second tab:

- **Health Coach** — unchanged demo flow
- **TRACE Evals** — Assignment 4 evaluation dashboard

One process, one launch command, instructor can screenshot the eval tab without a second app. The Health Coach tab does not call the dashboard loaders.

Above-the-fold target:

1. Title: TRACE Evaluation Dashboard
2. Four `st.metric` cards (baseline / V2 / improvement / CODIFY)
3. Scenario-quality bar chart
4. Failure → remediation examples

## Data sources

| UI element | Source | Kind |
|---|---|---|
| Baseline 5/15 | `baseline_human_review_extract_v1.json` | structured |
| V2 15/15 | `post_remediation_review_bundle_v1.md` V2 labels | artifact parse |
| CODIFY 168/0/102 | `post_remediation_codify_summary_v1.json` | structured |
| Official traces | `post_remediation_trace_index_v1.csv` | structured; excludes leftover B2 503 |
| Taxonomy names / baseline scenarios | `failure_taxonomy_counts_v1.csv` | structured F3 (not mutated) |
| Taxonomy F7.1 status | mapping in `evals/dashboard.py` | no JSON existed |
| Comparison change / remaining issue | `post_remediation_comparison_v1.md` table | F7 artifact |
| Grader catalog | `evals.codify.catalog.DETERMINISTIC_SPECS` | live catalog, not copied |

## Run button

**Run deterministic TRACE checks** calls `run_deterministic_codify()`:

- loads the 15 official V2 traces from the index
- invokes existing `grade_trace_paths` / `summarize_grades`
- does **not** call Gemini
- does **not** write or mutate traces or archived CODIFY JSON
- shows PASS / FAIL / N/A, failed grader IDs, UTC timestamp

## Tests

`tests/test_eval_dashboard.py`

- baseline / V2 / CODIFY counts
- taxonomy status mapping
- comparison row count
- official-trace selection (abandoned 503 excluded)
- missing-artifact error
- live deterministic run (no Gemini)
- mocked runner isolation

## Launch

From the project root, with the existing venv (Streamlit is already in `requirements.txt`):

```
.\.venv\Scripts\python.exe -m streamlit run streamlit_agent_demo.py
```

Then open the **TRACE Evals** tab.

## Maven screenshot

Frame the TRACE Evals tab without scrolling so the instructor sees:

- TRACE Evaluation Dashboard
- Baseline 5/15 · 33.3% → Post-remediation 15/15 · 100%
- CODIFY 168 PASS / 0 FAIL
- Scenario-quality pass rate chart
- First remediation examples (B1, B3, C-family)

Caption if needed: scenario-quality is separate from contract compliance; 100% is not product perfection.
