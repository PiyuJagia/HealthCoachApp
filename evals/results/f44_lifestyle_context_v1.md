# F4.4 Lifestyle context inspection (C1 / C2 / C3)

Deterministic inspection of `get_lifestyle_context`. No Gemini. No causal scoring.

**Default lookback:** 14 days inclusive of as-of date.

**Policy input mapping:** caffeine + unit mg → caffeine_mg (gates R-07); alcohol + unit standard_drinks → alcohol_units (gates R-08). mood / late-work notes do not map to a policy input. cycle_phase is not present in lifestyle_events.

Lifestyle context is user-specific observational context. It is not scientific evidence.
Association claims still require retrieve_authorized_evidence and evidence policy.

## HC-EVAL-C1 — 2026-08-02

Sleep decline with caffeine cluster

- Window: 2026-07-20 → 2026-08-02 (14 days)
- Event count: 17
- Caffeine: n=7 hours=[16, 16, 16, 16, 16, 16, 16] qty=[200.0, 200.0, 200.0, 200.0, 200.0, 200.0, 200.0] units=['mg', 'mg', 'mg', 'mg', 'mg', 'mg', 'mg']
- Alcohol: n=1
- Mood events: n=9; late-work notes=7
- Sleep trend (analytics, not lifestyle): direction=decreasing pct=-18.0
- policy_available_inputs: ['alcohol_units', 'caffeine_mg']
- R-07 if retrieved: {'evaluation_outcome_if_retrieved': 'relationship_detected', 'input_available': True, 'recommendation_authorized_if_retrieved': True}
- R-08 if retrieved: {'evaluation_outcome_if_retrieved': 'relationship_detected', 'input_available': True, 'recommendation_authorized_if_retrieved': False}

Events:

- 2026-07-20 21:15:00 mood qty=3.0 scale_1_5 notes=Synthetic late work evening
- 2026-07-21 12:00:00 mood qty=3.0 scale_1_5 notes=Synthetic self-report
- 2026-07-21 16:30:00 caffeine qty=200.0 mg notes=Synthetic afternoon coffee
- 2026-07-21 20:30:00 alcohol qty=1.0 standard_drinks notes=Synthetic social evening
- 2026-07-22 21:15:00 mood qty=3.0 scale_1_5 notes=Synthetic late work evening
- 2026-07-23 16:45:00 caffeine qty=200.0 mg notes=Synthetic afternoon coffee
- 2026-07-24 21:15:00 mood qty=3.0 scale_1_5 notes=Synthetic late work evening
- 2026-07-25 16:00:00 caffeine qty=200.0 mg notes=Synthetic afternoon coffee
- 2026-07-26 21:15:00 mood qty=3.0 scale_1_5 notes=Synthetic late work evening
- 2026-07-27 16:45:00 caffeine qty=200.0 mg notes=Synthetic afternoon coffee
- 2026-07-28 21:15:00 mood qty=3.0 scale_1_5 notes=Synthetic late work evening
- 2026-07-29 16:30:00 caffeine qty=200.0 mg notes=Synthetic afternoon coffee
- 2026-07-30 12:00:00 mood qty=4.0 scale_1_5 notes=Synthetic self-report
- 2026-07-30 21:15:00 mood qty=3.0 scale_1_5 notes=Synthetic late work evening
- 2026-07-31 16:00:00 caffeine qty=200.0 mg notes=Synthetic afternoon coffee
- 2026-08-01 21:15:00 mood qty=3.0 scale_1_5 notes=Synthetic late work evening
- 2026-08-02 16:00:00 caffeine qty=200.0 mg notes=Synthetic afternoon coffee

## HC-EVAL-C2 — 2026-07-31

Sleep decline with caffeine and late-work context

- Window: 2026-07-18 → 2026-07-31 (14 days)
- Event count: 16
- Caffeine: n=7 hours=[16, 16, 16, 16, 16, 16, 16] qty=[200.0, 200.0, 200.0, 200.0, 200.0, 200.0, 200.0] units=['mg', 'mg', 'mg', 'mg', 'mg', 'mg', 'mg']
- Alcohol: n=1
- Mood events: n=8; late-work notes=6
- Sleep trend (analytics, not lifestyle): direction=decreasing pct=-15.42
- policy_available_inputs: ['alcohol_units', 'caffeine_mg']
- R-07 if retrieved: {'evaluation_outcome_if_retrieved': 'relationship_detected', 'input_available': True, 'recommendation_authorized_if_retrieved': True}
- R-08 if retrieved: {'evaluation_outcome_if_retrieved': 'relationship_detected', 'input_available': True, 'recommendation_authorized_if_retrieved': False}

Events:

- 2026-07-19 16:00:00 caffeine qty=200.0 mg notes=Synthetic afternoon coffee
- 2026-07-20 21:15:00 mood qty=3.0 scale_1_5 notes=Synthetic late work evening
- 2026-07-21 12:00:00 mood qty=3.0 scale_1_5 notes=Synthetic self-report
- 2026-07-21 16:30:00 caffeine qty=200.0 mg notes=Synthetic afternoon coffee
- 2026-07-21 20:30:00 alcohol qty=1.0 standard_drinks notes=Synthetic social evening
- 2026-07-22 21:15:00 mood qty=3.0 scale_1_5 notes=Synthetic late work evening
- 2026-07-23 16:45:00 caffeine qty=200.0 mg notes=Synthetic afternoon coffee
- 2026-07-24 21:15:00 mood qty=3.0 scale_1_5 notes=Synthetic late work evening
- 2026-07-25 16:00:00 caffeine qty=200.0 mg notes=Synthetic afternoon coffee
- 2026-07-26 21:15:00 mood qty=3.0 scale_1_5 notes=Synthetic late work evening
- 2026-07-27 16:45:00 caffeine qty=200.0 mg notes=Synthetic afternoon coffee
- 2026-07-28 21:15:00 mood qty=3.0 scale_1_5 notes=Synthetic late work evening
- 2026-07-29 16:30:00 caffeine qty=200.0 mg notes=Synthetic afternoon coffee
- 2026-07-30 12:00:00 mood qty=4.0 scale_1_5 notes=Synthetic self-report
- 2026-07-30 21:15:00 mood qty=3.0 scale_1_5 notes=Synthetic late work evening
- 2026-07-31 16:00:00 caffeine qty=200.0 mg notes=Synthetic afternoon coffee

## HC-EVAL-C3 — 2026-06-29

Caffeine present while sleep remains reasonable

- Window: 2026-06-16 → 2026-06-29 (14 days)
- Event count: 4
- Caffeine: n=2 hours=[15, 15] qty=[180.0, 180.0] units=['mg', 'mg']
- Alcohol: n=1
- Mood events: n=1; late-work notes=0
- Sleep trend (analytics, not lifestyle): direction=stable pct=2.06
- policy_available_inputs: ['alcohol_units', 'caffeine_mg']
- R-07 if retrieved: {'evaluation_outcome_if_retrieved': 'relationship_detected', 'input_available': True, 'recommendation_authorized_if_retrieved': True}
- R-08 if retrieved: {'evaluation_outcome_if_retrieved': 'relationship_detected', 'input_available': True, 'recommendation_authorized_if_retrieved': False}

Events:

- 2026-06-19 12:00:00 mood qty=4.0 scale_1_5 notes=Synthetic self-report
- 2026-06-24 20:30:00 alcohol qty=1.0 standard_drinks notes=Synthetic social evening
- 2026-06-26 15:00:00 caffeine qty=180.0 mg notes=Synthetic afternoon coffee
- 2026-06-29 15:30:00 caffeine qty=180.0 mg notes=Synthetic afternoon coffee

## Negative / cherry-pick controls

- C1 caffeine present for investigation: True
- C2 multiple co-occurring factors: True
- C3 caffeine with stable sleep: True
- C3 does not manufacture a caffeine problem: True
- No causal scoring in tool payload: True
