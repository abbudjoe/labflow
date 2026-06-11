resource "aws_cloudwatch_log_group" "lambda_api" {
  name              = "/aws/lambda/${var.name_prefix}-api"
  retention_in_days = var.log_retention_days
  tags              = var.tags
}

resource "aws_cloudwatch_log_group" "api_gateway_access" {
  name              = "/aws/apigateway/${var.name_prefix}-http-api"
  retention_in_days = var.log_retention_days
  tags              = var.tags
}
