# LabFlow AWS Terraform Skeleton

This directory is a production-shaped Terraform skeleton for LabFlow AI Studio. It is intentionally not deployed by the project tests and contains no real account IDs, secrets, clinical data, or proprietary SOPs.

## Local-To-AWS Mapping

- Local FastAPI app in `apps/api` maps to `modules/lambda_api` behind `modules/api_gateway`.
- Local workflow examples and API state map to DynamoDB tables for workflows, audit events, eval runs, artifacts, and prompt versions.
- Local `knowledge/`, instrument inputs, generated artifacts, and eval reports map to separate S3 buckets/prefixes.
- Local agent guardrails map to Lambda IAM permissions scoped to the modeled tables and buckets.
- Local logs and trace IDs map to CloudWatch log groups.

## Modules

- `lambda_api`: Lambda function placeholder for the FastAPI adapter.
- `api_gateway`: HTTP API Gateway front door.
- `dynamodb`: workflow/control-plane tables.
- `s3`: knowledge, instrument, artifact, and eval report buckets.
- `iam`: Lambda execution role and scoped policy.
- `cloudwatch`: Lambda log group.

## Validation

When Terraform is installed:

```text
terraform -chdir=infra/terraform init -backend=false
terraform -chdir=infra/terraform validate
```

This repository does not require AWS credentials for local development or tests. Do not run `terraform apply` unless a future stage explicitly authorizes cloud mutation.
