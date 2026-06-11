# AWS Architecture Decisions

LabFlow is local-first, but its boundaries are shaped so the same system could
map to AWS services later. This document describes the intended shape without
requiring cloud credentials or deployment.

## Service Mapping

| LabFlow Boundary | AWS Shape |
| --- | --- |
| FastAPI app | Lambda behind API Gateway HTTP API |
| Workflow state | DynamoDB table keyed by lab/project/batch |
| Audit events | DynamoDB append-only audit table |
| Eval runs | DynamoDB metadata plus S3 report artifacts |
| Knowledge corpus | S3 versioned knowledge prefixes |
| Generated artifacts | S3 artifact prefixes with metadata records |
| Prompt/model registry | DynamoDB prompt versions plus S3 prompt/eval artifacts |
| Logs/traces | CloudWatch logs and metrics |

## Lambda And API Gateway

Lambda is sufficient for portfolio scale and keeps operations simple. A
container service would become attractive if model-side preprocessing, larger
dependencies, or long-running eval jobs became central.

## DynamoDB Key Design

Suggested tables:

- workflow state: `tenant_id#project_id` partition key, `batch_id#version`
  sort key;
- audit events: `tenant_id#batch_id` partition key, timestamp/audit ID sort
  key;
- eval runs: `suite_id` partition key, run timestamp sort key;
- prompt versions: `prompt_id` partition key, semantic version sort key.

## S3 Layout

Suggested prefixes:

```text
knowledge/{corpus_version}/...
instrument-files/{tenant}/{batch}/...
artifacts/{tenant}/{batch}/{artifact_id}
eval-reports/{suite}/{run_id}.json
prompt-registry/{prompt_id}/{version}.json
```

## IAM Boundary

Principles:

- Lambda role gets least-privilege table and prefix access.
- Eval-report writes do not imply workflow-state mutation.
- Artifact write permission is separate from read-only validation.
- Approval/commit paths require explicit audit linkage.

## Non-Mutating Portfolio Evidence

Only these Terraform commands are portfolio-readiness evidence:

```sh
terraform -chdir=infra/terraform fmt -check
terraform -chdir=infra/terraform init -backend=false
terraform -chdir=infra/terraform validate
```

Do not run `terraform plan`, `terraform apply`, or `terraform destroy` for the
portfolio gate.

## Future Production Gaps

- Authentication and authorization.
- Tenant isolation.
- Secrets management.
- CI/CD deployment controls.
- Observability dashboards.
- Incident response.
- Data retention and artifact lifecycle policies.
- Customer-specific SOP ingestion and approval workflows.
