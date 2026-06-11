# Threat Model

This threat model is scoped to the LabFlow portfolio demo. It identifies the
main ways an AI-assisted LIMS workflow tool can fail and the controls LabFlow
uses or would need before production.

## Assets

- Synthetic workflow YAML.
- Synthetic knowledge corpus.
- Deterministic validation results.
- JANUS-style dry-run previews.
- Audit events.
- Eval artifacts.
- Optional model provider credentials in local `.env`.

## Threats And Controls

| Threat | Control |
| --- | --- |
| Secret leakage | `.env` ignored; `.env.example` uses placeholders; `make portfolio-check` scans public files. |
| Prompt injection through SOP text | Guardrail policy and deterministic validation outrank retrieved prose. |
| Prompt injection through workflow YAML | Workflow content is data; model output cannot bypass tool policy. |
| Invented lab facts | Agent must not invent concentrations, sample IDs, wells, blanks, standards, or worklists. |
| Invalid robot-facing artifact | Deterministic validation blocks JANUS-style output for invalid batches. |
| Commit without approval | Tool runtime requires dry-run audit event and approval token. |
| Source conflict | Retrieval diagnostics flag policy-critical conflicts and cite both sources. |
| Stale SOP guidance | Stale/retired source metadata is surfaced in retrieval diagnostics. |
| Audit tampering | Current local audit is demonstrative only; production would need append-only durable storage and IAM controls. |
| Tenant data leakage | Out of scope for v0.1; production would need tenant-scoped keys, auth, and access tests. |

## Production Gaps

- AuthN/AuthZ.
- Tenant isolation.
- Key management.
- Immutable audit storage.
- Human approval workflow service.
- Incident response and alerting.
- Formal security review.

## Portfolio Boundary

The project is synthetic, non-clinical, and local-first. The threat model shows
engineering judgment and future controls; it is not a claim of production
security readiness.
