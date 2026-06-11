# Stage 15 Assembly Review

Review date: 2026-06-09

Stage: `15_aws_iac_skeleton`

Authoritative spec: `.codex_build/prompts/15_aws_iac_skeleton.md`

Status: `successful`

## Target Contract

Create a production-shaped AWS Terraform skeleton for LabFlow AI Studio without requiring deployment, real account IDs, secrets, or cloud mutation. The skeleton should model Lambda API, API Gateway, DynamoDB, S3, IAM, and CloudWatch resources and document the local-to-AWS mapping.

## Extracted DoD Checklist

| DoD item | Status | Evidence |
| --- | --- | --- |
| D1: Read project doctrine/specs before implementation | met | Read Stage 15 prompt and required project doctrine files. |
| D2: Add `infra/terraform/main.tf` | met | Root Terraform orchestration added. |
| D3: Add `infra/terraform/variables.tf` | met | Project/environment/region/log retention/tags variables added. |
| D4: Add `infra/terraform/outputs.tf` | met | API, Lambda, DynamoDB, S3 bucket, and S3 prefix outputs added. |
| D5: Add `modules/lambda_api` | met | Lambda module added with function, environment mapping, tracing, and outputs. |
| D6: Add `modules/api_gateway` | met | HTTP API, Lambda integration, routes, default stage, access logs, and invoke permission added. |
| D7: Add `modules/dynamodb` | met | DynamoDB module added. |
| D8: Add `modules/s3` | met | S3 module added. |
| D9: Add `modules/iam` | met | IAM module added. |
| D10: Add `modules/cloudwatch` | met | CloudWatch module added. |
| D11: Model Lambda API | met | `aws_lambda_function.api` models the FastAPI/Lambda adapter with LabFlow bucket/table environment variables. |
| D12: Model API Gateway | met | `aws_apigatewayv2_api`, integration, routes, stage, and Lambda permission modeled. |
| D13: Model DynamoDB tables for workflows, audit events, eval runs, artifacts, prompt versions | met | Five PAY_PER_REQUEST tables with `pk`/`sk`, point-in-time recovery, and table outputs modeled. |
| D14: Model S3 buckets/prefixes for knowledge, instrument files, artifacts, eval reports | met | Four versioned/private/encrypted buckets plus reserved logical prefixes modeled. |
| D15: Model IAM roles/policies | met | Lambda assume role and scoped CloudWatch/DynamoDB/S3 policy modeled. |
| D16: Model CloudWatch logs | met | Lambda log group and API Gateway access log group modeled. |
| D17: No real account IDs, no secrets, placeholder variables | met | Secret/account pattern scan returned no matches. |
| D18: Terraform validate should pass if Terraform is installed | met | User installed Terraform and ran `terraform -chdir=infra/terraform init -backend=false` plus `terraform -chdir=infra/terraform validate`; configuration is valid. |
| D19: README explains local-to-AWS mapping | met | `infra/terraform/README.md` documents modules, local-to-AWS mapping, validation commands, and no-apply boundary. |
| D20: Reference repo not modified and no cloud mutation | met | Reference repo status only shows pre-existing `?? .DS_Store`; no cloud commands beyond local static checks were run. |
| D21: Assembly subagent review clean | met | Reviewer found one P1 API Gateway provider-contract issue; fixed and rechecked. |

## Planned Evidence Commands

```text
find infra/terraform -type f | sort
grep -RInE "account_id|access_key|secret_key|BEGIN (RSA|OPENSSH|PRIVATE)|AKIA[0-9A-Z]{16}" infra/terraform || true
terraform -chdir=infra/terraform init -backend=false
terraform -chdir=infra/terraform validate
uv run --python /Users/joseph/.local/bin/python3.12 --with python-hcl2 python - <<'PY'
from pathlib import Path
import hcl2
paths = sorted(Path('infra/terraform').rglob('*.tf'))
for path in paths:
    with path.open() as handle:
        hcl2.load(handle)
print(f'parsed {len(paths)} terraform files')
PY
make test
make lint
make type
git -C /Users/joseph/ngs_lab_automation status --short
```

## Changed Files

- `infra/terraform/main.tf`
- `infra/terraform/variables.tf`
- `infra/terraform/outputs.tf`
- `infra/terraform/README.md`
- `infra/terraform/modules/api_gateway/main.tf`
- `infra/terraform/modules/api_gateway/outputs.tf`
- `infra/terraform/modules/api_gateway/variables.tf`
- `infra/terraform/modules/cloudwatch/main.tf`
- `infra/terraform/modules/cloudwatch/outputs.tf`
- `infra/terraform/modules/cloudwatch/variables.tf`
- `infra/terraform/modules/dynamodb/main.tf`
- `infra/terraform/modules/dynamodb/outputs.tf`
- `infra/terraform/modules/dynamodb/variables.tf`
- `infra/terraform/modules/iam/main.tf`
- `infra/terraform/modules/iam/outputs.tf`
- `infra/terraform/modules/iam/variables.tf`
- `infra/terraform/modules/lambda_api/main.tf`
- `infra/terraform/modules/lambda_api/outputs.tf`
- `infra/terraform/modules/lambda_api/variables.tf`
- `infra/terraform/modules/s3/main.tf`
- `infra/terraform/modules/s3/outputs.tf`
- `infra/terraform/modules/s3/variables.tf`
- `docs/stage15_assembly_review.md`

## Review Findings

- P1: `aws_apigatewayv2_integration` was missing `integration_method = "POST"`, which the AWS provider requires for non-`MOCK` integrations. Fixed in `infra/terraform/modules/api_gateway/main.tf`.
- Post-fix evidence: `make test`, `make lint`, `make type`, secret/account scan, `python-hcl2` parse of all 21 Terraform files, `terraform init -backend=false`, and `terraform validate` passed.
