variable "name_prefix" {
  description = "Name prefix for the Lambda API."
  type        = string
}

variable "lambda_role_arn" {
  description = "IAM role ARN for the Lambda API."
  type        = string
}

variable "log_group_name" {
  description = "CloudWatch log group name created before Lambda."
  type        = string
}

variable "package_path" {
  description = "Placeholder Lambda deployment package path."
  type        = string
  default     = "placeholder-lambda.zip"
}

variable "artifact_bucket" {
  description = "Artifact bucket name."
  type        = string
}

variable "knowledge_bucket" {
  description = "Knowledge bucket name."
  type        = string
}

variable "instrument_bucket" {
  description = "Instrument bucket name."
  type        = string
}

variable "eval_bucket" {
  description = "Eval report bucket name."
  type        = string
}

variable "table_names" {
  description = "DynamoDB table names."
  type        = map(string)
}

variable "tags" {
  description = "Tags applied to Lambda resources."
  type        = map(string)
  default     = {}
}
