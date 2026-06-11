variable "name_prefix" {
  description = "Name prefix for S3 buckets."
  type        = string
}

variable "tags" {
  description = "Tags applied to S3 buckets."
  type        = map(string)
  default     = {}
}
