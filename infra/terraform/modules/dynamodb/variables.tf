variable "name_prefix" {
  description = "Name prefix for DynamoDB tables."
  type        = string
}

variable "tags" {
  description = "Tags applied to DynamoDB tables."
  type        = map(string)
  default     = {}
}
