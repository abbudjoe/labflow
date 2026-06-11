resource "aws_lambda_function" "api" {
  function_name = "${var.name_prefix}-api"
  role          = var.lambda_role_arn
  runtime       = "python3.12"
  handler       = "labflow_api.lambda_handler.handler"

  filename = var.package_path

  environment {
    variables = {
      LABFLOW_ARTIFACT_BUCKET   = var.artifact_bucket
      LABFLOW_KNOWLEDGE_BUCKET  = var.knowledge_bucket
      LABFLOW_INSTRUMENT_BUCKET = var.instrument_bucket
      LABFLOW_EVAL_BUCKET       = var.eval_bucket
      LABFLOW_TABLE_NAMES       = jsonencode(var.table_names)
      LABFLOW_LOG_GROUP_NAME    = var.log_group_name
      LABFLOW_RUNTIME_MODE      = "aws-skeleton"
    }
  }

  tracing_config {
    mode = "Active"
  }

  tags = var.tags
}
