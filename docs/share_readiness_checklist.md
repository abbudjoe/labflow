# Share Readiness Checklist

This checklist defines what must be true before LabFlow AI Studio is shared as a
portfolio project.

## Public Positioning

- LabFlow AI Studio is a synthetic AI/LIMS workflow development studio.
- It is not a STARLIMS clone.
- It does not use proprietary STARLIMS internals or proprietary lab SOPs.
- It is not a clinical, diagnostic, production lab, or robot-control system.
- JANUS-style files are dry-run portfolio previews, not certified robot-ready
  artifacts.
- The deterministic workflow engine owns lab truth; the model only retrieves,
  explains, proposes, or calls controlled tools.

## Files That Are Safe To Share

- Source code under `packages/`, `apps/`, `scripts/`, `infra/`, and `docs/`.
- Synthetic examples under `examples/`.
- Synthetic knowledge corpus under `knowledge/`.
- Eval case definitions under `evals/`.
- Curated summaries:
  - `docs/eval_summary.md`;
  - `docs/role_alignment_starlims.md`;
  - `docs/demo_script_starlims_role.md`;
  - `docs/case_study.md`.

## Files That Must Stay Local

- `.env`
- local caches such as `.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/`, and
  `__pycache__/`;
- `node_modules/`;
- Terraform state and `.terraform/`;
- raw historical artifacts under `artifacts/` unless intentionally exported;
- Codex assembly scaffolding under `.codex_build/` unless a private review
  needs it.

## Required Checks

Run:

```sh
make portfolio-check
```

The check verifies:

- required portfolio docs exist;
- `.env` is ignored and not tracked;
- expected ignore patterns are present;
- public docs do not make unsafe clinical, production, proprietary, or
  robot-ready claims without disclaimers;
- obvious API-key patterns are not present in public files.

Recommended deeper checks before sharing:

```sh
make test
make lint
make type
make eval-summary
make corpus-drift-eval
make portfolio-export
```

Terraform evidence must stay local and non-mutating:

```sh
terraform -chdir=infra/terraform fmt -check
terraform -chdir=infra/terraform init -backend=false
terraform -chdir=infra/terraform validate
```

Do not run `terraform apply`, `terraform destroy`, or any cloud-credentialed
command as part of the portfolio gate.

## Canonical Evidence

Start with:

- `docs/eval_summary.md` for eval results;
- `docs/demo_script_starlims_role.md` for the live narrative;
- `docs/role_alignment_starlims.md` for job-description mapping;
- `docs/case_study.md` for architecture and tradeoffs;
- `docs/corpus_lifecycle_reliability.md` for corpus drift and fingerprinting;
- `docs/portfolio_brief.md` for the short hiring-reviewer packet.

Raw eval artifacts are audit support, not the primary reviewer experience.
