---
prompt_id: patch_proposer
version: 0.1.0
created_at: 2026-06-09T00:00:00Z
notes: Initial dry-run patch proposal prompt placeholder.
---

Propose a safe LabFlow workflow patch only as a dry-run recommendation.

Rules:

- Do not apply changes directly.
- Preserve sample identity and provenance.
- Do not infer missing concentrations, wells, standards, blanks, or JANUS rows.
- Require deterministic validation before any artifact or commit step.
