# LabFlow Doctrine

## Core doctrine

Laboratory automation is not only robotic execution. High-throughput laboratory workflows depend on the coordination layer around the robot: validated input data, batch readiness, sample provenance, exception handling, operator instructions, and controlled artifact generation.

LabFlow AI Studio exists to demonstrate how AI can assist with LIMS workflow development without replacing deterministic validation.

## AI doctrine

1. **Deterministic before generative.**
   The lab workflow engine must work without an LLM.

2. **AI proposes; validators decide.**
   The agent may propose fixes, but deterministic validators decide whether a batch is valid.

3. **No unsupported lab claims.**
   RAG answers must cite retrieved domain documents. If the corpus does not support an answer, the assistant must say so.

4. **No silent robot artifacts.**
   JANUS-style worklists or protocol outputs cannot be generated for invalid batches.

5. **No hidden mutations.**
   All state-changing actions require dry-run first, explicit approval, and audit events.

6. **Synthetic only.**
   This project uses synthetic data and reconstructed public/domain knowledge. It is not a production LIMS, clinical diagnostic system, or proprietary workflow disclosure.

## LIMS doctrine

1. Sample identity is mandatory.
2. Source location is mandatory.
3. Destination location is mandatory when a destination exists.
4. Duplicate source/destination occupancy must block execution.
5. Sample ancestry must be traceable by sample ID.
6. Every exception must be explicit.
7. Invalid samples must not generate robot transfers.
8. Manual overrides are normal, but they must be explicit and audited.

## NGS quant/norm doctrine

1. Varioskan readings are not stock concentrations.
2. Quantification values must flow through blank correction, standard curve, assay concentration, dilution factor, and stock concentration.
3. Normalization consumes stock concentration in ng/µL.
4. Molarity is out of scope for this project.
5. Calculated transfer volumes below 1 µL require split workflow, not silent rounding.
6. In-place normalization is a separate mode, not a standard destination transfer.
7. RNA re-quant results become downstream concentration; no default percent tolerance is assumed.

## Developer-platform doctrine

1. The VS Code extension should make workflow errors visible before runtime.
2. DSL diagnostics should be deterministic.
3. AI explanations should cite doctrine and tool outputs.
4. Developer actions should be repeatable from CLI/API, not trapped inside the UI.
5. Every demo scenario should have a corresponding automated test or eval.
