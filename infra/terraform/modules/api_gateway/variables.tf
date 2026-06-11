variable "name_prefix" {
  description = "Name prefix for API Gateway resources."
  type        = string
}

variable "lambda_function_name" {
  description = "Lambda function name for invoke permissions."
  type        = string
}

variable "lambda_invoke_arn" {
  description = "Lambda invoke ARN for HTTP API integration."
  type        = string
}

variable "access_log_group_arn" {
  description = "CloudWatch log group ARN for HTTP API access logs."
  type        = string
}

variable "tags" {
  description = "Tags applied to API Gateway resources."
  type        = map(string)
  default     = {}
}
