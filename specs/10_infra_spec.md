# Infrastructure Specification

## Goal

Provide production-shaped AWS architecture without requiring deployment for local demo.

## Resources to scaffold

Terraform skeleton for:

- Lambda function for API;
- API Gateway;
- DynamoDB tables;
- S3 buckets;
- IAM roles/policies;
- CloudWatch logs.

## Suggested DynamoDB tables

- `labflow-workflows`
- `labflow-audit-events`
- `labflow-eval-runs`
- `labflow-artifacts`
- `labflow-prompt-versions`

## Suggested S3 prefixes

```text
knowledge/
instrument-files/
artifacts/janus/
artifacts/reports/
eval-reports/
```

## Local parity

Local implementation should map to the same abstractions:

- JSONL/SQLite for DynamoDB-like store;
- local filesystem for S3-like artifact store;
- local FastAPI for Lambda/API Gateway.

## Secrets

No secrets in repo. Use `.env.example`.
