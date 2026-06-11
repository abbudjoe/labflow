# Limitations And Disclosure

LabFlow AI Studio is a portfolio project using synthetic data. It is designed to demonstrate architecture and engineering judgment, not to operate a real laboratory.

## Not Production Or Clinical

This project is not:

- a production LIMS;
- a clinical or diagnostic system;
- a robot controller;
- a validated laboratory instrument integration;
- a STARLIMS clone;
- a reproduction of proprietary SOPs;
- a system for real patient, customer, or regulated lab data.

## Synthetic Data Only

Examples under `examples/`, `knowledge/`, and `evals/` are synthetic. Identifiers such as `RNA_DEMO_*`, `DNA_DEMO_*`, and `STD_*` are demo identifiers.

## JANUS Preview Boundary

JANUS-style CSV files in this repository are dry-run previews. They demonstrate deterministic gating and row formatting, but they are not certified robot-ready files for a production liquid handler.

Invalid samples and invalid batches must not generate robot transfers.

## AI Boundary

The current project does not require live model inference. The local agent uses deterministic model behavior for repeatable tests and demos.

Future live inference should be added only behind:

- provider adapters;
- prompt/model version tracking;
- eval regression checks;
- citation and unsupported-answer policies;
- deterministic validator gates;
- dry-run and approval controls;
- audit logging.

## Infrastructure Boundary

`infra/terraform` is a production-shaped skeleton. It is intended for validation and architecture discussion. It is not applied by default and should not be used to mutate AWS resources without explicit authorization and environment hardening.

## Known Gaps Before Production

- Authentication and authorization.
- Durable approval and artifact stores.
- Real LIMS/container registry integrations.
- Real instrument ingestion pipelines.
- Real robot protocol validation.
- Secrets management.
- Cloud deployment pipeline.
- Security review and threat modeling.
- Human factors validation for operator workflows.
- Production observability dashboards and alerting.
