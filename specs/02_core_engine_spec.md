# Core Engine Specification

## Purpose

`labflow-core` contains deterministic lab/LIMS workflow logic. It must not import RAG, agent, OpenAI, or any LLM-specific package.

## Modules

```text
labflow_core/
  domain/
    units.py
    wells.py
    containers.py
    samples.py
    statuses.py
    exceptions.py
    audit.py
  lims/
    registry.py
    ancestry.py
    manifests.py
  quant/
    varioskan.py
    standards.py
    processors.py
  norm/
    targets.py
    planner.py
    split.py
    requant.py
  robots/
    protocol_ir.py
    janus.py
  throughput/
    readiness.py
    simulator.py
    metrics.py
  dsl/
    models.py
    parser.py
    validator.py
  tools/
    core_tools.py
```

## Required deterministic behavior

### Well coordinates

- Valid wells: A1-H12.
- Standards default: A1-H1.
- Deterministic well ordering required.

### Containers

- Matrix 96 x 1 mL screwtop.
- Matrix 96 x 1 mL rubber/septum top.
- Max working volume: 999 µL.
- Container registry resolves type from barcode/container ID.

### Quantification

- Standards plate once per batch.
- 8 standards in A1-H1.
- One blank per sample plate.
- 95 samples per sample plate.
- Linear standard curve.
- Blank correction.
- Dilution factor correction.
- Final LIMS concentration is stock concentration ng/µL.

### Normalization

Supported target modes:

- final concentration + final volume;
- final mass + final volume.

Core formula:

```text
sample_transfer_volume_ul =
  target_concentration_ng_per_ul
  * target_final_volume_ul
  / source_concentration_ng_per_ul

diluent_volume_ul = target_final_volume_ul - sample_transfer_volume_ul
```

Required source volume:

```text
sample_transfer_volume_ul + 2 + 1
```

### In-place normalization

- No destination container.
- Only diluent added to source.
- No sample transfer.
- No mix.

### Split workflow

- Trigger: calculated transfer volume < 1 µL.
- Use 1 µL sample.
- Create child sample.
- Require re-quant.
- Follow-up normalization uses child re-quant concentration.

### RNA re-quant

- RiboGreen for sample-prep quant/re-quant.
- Re-quant value becomes downstream concentration.
- Missing/invalid re-quant -> manual review or repeat quant.

### JANUS export

- Minimal CSV: well, diluent_volume_ul, sample_volume_ul.
- Rich audit CSV: include batch/sample/source/destination/status/mode.
- Invalid samples must be excluded from robot transfers.

## Tests to port/create

- Well parsing and standards layout.
- Standard curve and quant pipeline.
- Normalization target modes.
- Standard normalization.
- Low concentration block.
- Insufficient source volume.
- Destination overflow.
- In-place mode.
- Split mode and ancestry.
- RNA re-quant downstream concentration.
- JANUS export gating.
- Batch readiness.
- Throughput baseline vs optimized.
