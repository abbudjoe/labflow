---
prompt_id: diagnostic_explainer
version: 0.1.0
created_at: 2026-06-09T00:00:00Z
notes: Initial grounded diagnostic explanation prompt.
---

Explain a LabFlow diagnostic using retrieved doctrine and deterministic tool output.

Rules:

- State what the diagnostic means.
- Explain why it blocks or warns.
- Include cited sources when making domain claims.
- Recommend only safe next actions.
- Do not fabricate missing lab data.
