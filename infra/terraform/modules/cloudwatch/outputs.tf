output "lambda_log_group_name" {
  value = aws_cloudwatch_log_group.lambda_api.name
}

output "api_access_log_group_arn" {
  value = aws_cloudwatch_log_group.api_gateway_access.arn
}
