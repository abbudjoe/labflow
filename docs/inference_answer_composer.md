# Inference Answer Composer

Stage 18.4 adds an optional answer-composer boundary for language quality
experiments. It is separate from the planner and receives only fixed grounded
context captured after retrieval and deterministic tool execution.

## Boundary

The composer receives:

- a sanitized user question and boolean request-shape flags;
- plan task, rationale, and retrieval query;
- retrieved chunk IDs, source metadata, and chunk text;
- deterministic tool evidence with stable IDs such as `tool:0:validate_batch`;
- baseline deterministic answer, next safe action, blocked reason, and
  unsupported flag.

The composer returns only a `GroundedAnswerDraft`:

- answer prose;
- cited source IDs;
- cited tool evidence IDs;
- next safe action;
- optional blocked reason;
- safety flags.

The final `AgentResponse` keeps task, plan, sources, tool calls, unsupported
state, trace metadata, and artifact eligibility from the deterministic baseline.

## Guarded Fallback

`GroundedAnswerDraftValidator` rejects drafts that:

- cite source or tool IDs outside the fixed context;
- omit evidence citations when context has evidence;
- invent numeric lab values or well locations;
- claim a blocked batch is robot-ready;
- claim JANUS/artifact generation without deterministic artifact support;
- suggest inferring or estimating missing lab facts.

Rejected drafts fall back to deterministic answer composition.
Fallback status and sanitized composer diagnostics are recorded on the agent
trace.

## Configuration

Default local behavior uses deterministic composition only:

```text
LABFLOW_ANSWER_COMPOSER=deterministic
```

Live answer composition is opt-in:

```text
LABFLOW_ANSWER_COMPOSER=openrouter
OPENROUTER_API_KEY=...
```

Local tests and offline evals do not require provider credentials.

## Eval Implication

`grounded_answer_quality` now scores deterministic baseline text and inference
draft text over the same `GroundedAnswerContext`. Planner generalization remains
separate in `semantic_generalization`.

Offline runs use a fixture answer composer to verify fixed-context comparison
without provider credentials. Live OpenRouter comparison remains opt-in.

## Risks And Limits

The first validator is intentionally conservative. It can reject some safe
paraphrases when they look like unsupported artifact or readiness claims. It
also does not prove full natural-language entailment; it enforces citation IDs,
known numeric/well values, explicit blocked diagnostics, and readiness/artifact
polarity. Production use would need stronger claim extraction, richer
provenance, and human-reviewed SOP alignment.
