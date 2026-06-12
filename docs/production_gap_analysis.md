# Production Gap Analysis

LabFlow is a portfolio prototype. It demonstrates production-shaped engineering patterns, but it is not a production LIMS, clinical system, diagnostic system, or robot-control system.

## Strong Demonstration Areas

- Deterministic workflow validation owns lab truth.
- RAG answers cite retrieved synthetic sources or refuse unsupported claims.
- Tool calls are guarded, audited, and read-only by default.
- Eval reports include corpus fingerprint metadata.
- Corpus drift tests cover irrelevant additions, source renames, conflicts, removals, updates, and stale SOPs.
- Optional vector backend scripts show how hosted retrieval would be controlled and compared.

## Before Production

The following would be required before any production lab use:

- authn/authz and tenant isolation;
- secrets management and key rotation;
- immutable audit storage;
- human approval workflow service;
- validated deployment, monitoring, alerting, and incident response;
- formal data governance and retention controls;
- broader adversarial retrieval and tool-use evals;
- operational SOP ownership by the deploying lab;
- integration testing against approved LIMS and instrument interfaces.

## Boundary

The project uses synthetic examples and synthetic SOP-like docs only. It does not claim compatibility with STARLIMS internals or any proprietary lab environment.
