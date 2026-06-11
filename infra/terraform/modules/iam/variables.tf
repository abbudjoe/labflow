variable "name_prefix" {
  description = "Name prefix for IAM resources."
  type        = string
}

variable "dynamodb_tables" {
  description = "DynamoDB table ARNs the Lambda API can access."
  type        = list(string)
}

variable "artifact_bucket" {
  description = "Artifact S3 bucket ARN."
  type        = string
}

variable "knowledge_bucket" {
  description = "Knowledge S3 bucket ARN."
  type        = string
}

variable "instrument_bucket" {
  description = "Instrument file S3 bucket ARN."
  type        = string
}

variable "eval_bucket" {
  description = "Eval report S3 bucket ARN."
  type        = string
}

variable "tags" {
  description = "Tags applied to IAM resources."
  type        = map(string)
  default     = {}
}
