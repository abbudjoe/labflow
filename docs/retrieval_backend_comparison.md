# Retrieval Backend Comparison

LabFlow separates retrieval correctness from retrieval infrastructure. The same corpus lifecycle cases can be evaluated against local hybrid retrieval and an optional Pinecone backend.

## Metrics

The comparison report includes:

- required source-family recall;
- exact required-source hit rate;
- top-k overlap against local retrieval;
- stale-source retrieval rate;
- conflict detection count;
- p50 and p95 latency;
- corpus fingerprint.

## Interpretation

For the portfolio demo, local hybrid retrieval is the reliable default because it is deterministic, dependency-light, and fast. A hosted vector backend would mainly support larger corpora, remote deployments, and index management workflows. It does not replace source lifecycle checks, conflict detection, citations, or deterministic validation.

## Command

```sh
make retrieval-backend-compare
```

Without Pinecone configuration, the Pinecone row is marked skipped. That is expected and keeps CI/local review independent of external services.
