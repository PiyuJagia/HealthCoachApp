# Governance Documentation

This folder documents **controls and guardrails that actually exist** in the Health Coach capstone today.

## Why this exists

The Health Coach deals with health-related insights drawn from curated evidence. That means:

- **Provenance** — we need to know where a claim came from
- **Evidence quality** — not all sources are equally verified
- **Bounded interpretation** — association is not causation; product levels cap what we may say
- **Suppression** — unsupported or contradictory patterns must not be surfaced as insights
- **Testability** — rules should be expressible as code and tests, not tribal knowledge

These are intentional architectural choices, not afterthoughts.

This documentation does **not** make regulatory or compliance claims. It describes engineering controls in our repository.

## Contents

| Document | Purpose |
|----------|---------|
| [controls_and_guardrails.md](controls_and_guardrails.md) | Inventory of implemented, partial, and planned controls by layer |

## Relationship to testing

Each control should ideally map to:

1. A code or config artifact
2. A deterministic test where feasible
3. A future TRACE assertion where human judgment is required

See [../testing/README.md](../testing/README.md) and [../testing/test_history.md](../testing/test_history.md).

## Relationship to evals

The `evals/` directory at the repo root holds **placeholders** for future TRACE datasets, traces, and results. No evaluation pipeline is implemented yet.
