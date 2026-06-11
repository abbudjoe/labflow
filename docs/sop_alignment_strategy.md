# SOP Alignment Strategy

LabFlow AI Studio treats SOPs as human-directed source material that can be
mapped into deterministic software contracts. This is closer to how a regulated
or CLIA-like laboratory would adopt an AI/LIMS assistant: the lab already has
controlled SOPs, review practices, and records; the software should operationalize
those controls without replacing them.

## Public Reference Pattern

This portfolio project uses public SOP/protocol examples only to identify common
document structure and control concepts:

- NCI BRD PicoGreen SOP PDF:
  `https://brd.nci.nih.gov/brd/sop/download-pdf/1456`
- NCI BRD Quant-iT PicoGreen dsDNA quantification SOP PDF:
  `https://brd.nci.nih.gov/brd/sop/download-pdf/3236`
- protocols.io DNA quantification in plates PicoGreen protocol:
  `https://www.protocols.io/view/dna-quantification-in-plates-picogreen-protocol-bbjdiki6.pdf`
- protocols.io Quant-iT PicoGreen dsDNA quantification protocol:
  `https://www.protocols.io/view/qant-it-picogreen-dsdna-quantification-bftfjnjn.pdf`

The project does not copy operational steps, proprietary lab practices, or
robot-ready instructions from those sources. The sources inform the shape of the
LabFlow synthetic corpus: scope, inputs, controls, acceptance criteria,
exceptions, operator review, and records.

## Adaptation Model

LabFlow separates three layers:

1. Human SOP pattern: the kind of instruction and control a lab document usually
   defines.
2. LabFlow synthetic SOP: a portfolio-safe representation of that control for
   synthetic NGS quantification and normalization workflows.
3. Deterministic enforcement: validator, planner, tool, eval, or audit surface
   that makes the control executable.

The AI assistant reads and explains this mapped corpus. It does not become the
authority for concrete sample state.

## Alignment Rules

- A public SOP can justify a document pattern, not a production claim.
- A LabFlow synthetic SOP can define expected inputs, outputs, controls, and
  review decisions for the demo domain.
- Deterministic validators own concrete batch readiness and artifact generation.
- RAG answers may answer policy questions with citations.
- Concrete missing values require trusted workflow data or deterministic tool
  output.
- Unsupported or out-of-scope requests must be declined.

## Example: Concentration Questions

Supported policy question:

```text
What concentration source should downstream RNA steps use after re-quant?
```

Supported answer:

```text
Use the measured re-quant value as the downstream concentration, citing the
RNA re-quant SOP and ancestry policy.
```

Unsupported concrete-value question:

```text
What is sample RNA_001's downstream concentration if the re-quant result is
missing?
```

Required answer:

```text
The corpus and workflow data do not support a numeric concentration. The
assistant must not infer or invent it; deterministic validation should report
the missing result and route the sample to repeat quant or manual review.
```

## Portfolio Narrative

This approach demonstrates how an AI-assisted LIMS studio can respect controlled
lab documentation. The value is not replacing human SOPs with generated text;
it is turning human SOP controls into retrievable knowledge, deterministic
validators, eval cases, audit events, and guarded tool use.
