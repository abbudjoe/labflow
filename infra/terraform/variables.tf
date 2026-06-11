variable "project_name" {
  description = "Short project name used as an AWS resource prefix."
  type        = string
  default     = "labflow-ai-studio"
}

variable "environment" {
  description = "Deployment environment label. Use placeholders for this portfolio skeleton."
  type        = string
  default     = "dev"
}

variable "aws_region" {
  description = "AWS region placeholder for local Terraform planning."
  type        = string
  default     = "us-east-1"
}

variable "log_retention_days" {
  description = "CloudWatch log retention period for the Lambda API."
  type        = number
  default     = 14
}

variable "tags" {
  description = "Additional tags to apply to AWS resources."
  type        = map(string)
  default     = {}
}
