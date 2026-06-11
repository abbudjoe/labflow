variable "name_prefix" {
  description = "Name prefix for CloudWatch resources."
  type        = string
}

variable "log_retention_days" {
  description = "CloudWatch retention in days."
  type        = number
}

variable "tags" {
  description = "Tags applied to CloudWatch resources."
  type        = map(string)
  default     = {}
}
