# VS Code Demo Workspace

Use this folder as the starting point for the portfolio VS Code demo.

Open these workflow files from the repo root:

- `examples/workflows/invalid_rna_norm_requant.workflow.yaml`
- `examples/workflows/fixed_rna_norm_requant.workflow.yaml`
- `examples/workflows/invalid_duplicate_well.workflow.yaml`

Expected demo behavior:

- diagnostics flag deterministic workflow problems;
- AI explanation cites LabFlow sources and deterministic tool output;
- dry-run patch proposals are previewed before any edit;
- commit-style actions require approval policy;
- invalid batches cannot generate JANUS-style robot-facing artifacts.

See:

- `docs/demo_script_starlims_role.md`
- `docs/role_alignment_starlims.md`
- `docs/eval_summary.md`
