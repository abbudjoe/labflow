locals {
  tables = {
    workflows       = "${var.name_prefix}-workflows"
    audit_events    = "${var.name_prefix}-audit-events"
    eval_runs       = "${var.name_prefix}-eval-runs"
    artifacts       = "${var.name_prefix}-artifacts"
    prompt_versions = "${var.name_prefix}-prompt-versions"
  }
}

resource "aws_dynamodb_table" "this" {
  for_each = local.tables

  name         = each.value
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  range_key    = "sk"

  attribute {
    name = "pk"
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = merge(var.tags, { LabFlowTable = each.key })
}
