# Corpus Lifecycle Reliability

LabFlow treats the knowledge corpus as a versioned input to retrieval behavior, not as invisible prompt material. Stage 20 adds a deterministic corpus manifest so eval reports can be tied back to the exact synthetic documents, chunk settings, and retrieval metadata schema used for a run.

## Manifest Contract

The manifest includes:

- stable document IDs and relative paths;
- content and normalized-content SHA-256 hashes;
- chunk counts and chunking parameters;
- source-family, status, authority, version, effective-date, and supersession metadata;
- a top-level corpus fingerprint.

Absolute filesystem paths are excluded from the fingerprint so the same corpus produces the same identity on another machine.

## Drift Eval Variants

`make corpus-drift-eval` runs a local-only suite over temporary corpus copies. It covers:

- irrelevant document additions;
- renamed or rechunked current SOPs;
- conflicting lower-authority SOPs;
- removed source documents;
- updated current SOP plus retired predecessor;
- stale or retired SOP retrieval.

The goal is not to freeze every ranking position. The goal is to preserve source-family recall, detect policy conflicts, and surface stale sources when they appear in retrieved evidence.

## Conflict And Staleness Handling

Retrieved chunks are interpreted through explicit source lifecycle metadata. Locked doctrine outranks lower-authority SOP drafts for policy-critical rules. If retrieved non-locked sources conflict, the answer must request manual review instead of choosing silently. Retired or stale sources are surfaced as stale retrieval evidence.

## Review Commands

```sh
make corpus-drift-eval
python3 scripts/index_knowledge_pinecone.py --dry-run
python3 scripts/compare_retrieval_backends.py
```

These commands are local-first. Pinecone is optional and disabled unless explicitly configured.
