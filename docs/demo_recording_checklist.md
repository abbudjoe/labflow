# Demo Recording Checklist

Use this checklist for a short portfolio recording.

## Before Recording

- Run `make portfolio-check`.
- Run `make corpus-drift-eval`.
- Run `make eval-summary`.
- Confirm `.env` is not tracked with `git ls-files -- .env`.
- Close terminals that show API keys or local secrets.

## Suggested Flow

1. Open the README and show the Hiring Reviewer Path.
2. Run the fixed RNA workflow demo path.
3. Show deterministic validation blocking invalid JANUS-style output.
4. Show downstream QC provenance linking synthetic QC results to sample lineage.
5. Run the interactive RAG demo and ask why a batch is not robot-ready.
6. Open `docs/eval_summary.md`.
7. Run or show `make corpus-drift-eval` output.
8. Open `docs/production_gap_analysis.md` and explain the boundary.

## Recording Boundary

Do not show `.env`, live API keys, cloud consoles, or any real lab data.
