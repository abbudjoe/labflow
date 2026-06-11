output "api_endpoint" {
  description = "Placeholder API Gateway endpoint for the LabFlow API."
  value       = module.api_gateway.api_endpoint
}

output "lambda_function_name" {
  description = "Lambda function name for the LabFlow FastAPI adapter."
  value       = module.lambda_api.function_name
}

output "dynamodb_table_names" {
  description = "DynamoDB tables used by the AWS-shaped LabFlow control plane."
  value       = module.dynamodb.table_names
}

output "s3_bucket_names" {
  description = "S3 buckets used by the AWS-shaped LabFlow data plane."
  value = {
    knowledge   = module.s3.knowledge_bucket_name
    instruments = module.s3.instrument_bucket_name
    artifacts   = module.s3.artifact_bucket_name
    evals       = module.s3.eval_bucket_name
  }
}

output "s3_bucket_prefixes" {
  description = "Reserved logical prefixes for LabFlow S3 object classes."
  value       = module.s3.bucket_prefixes
}
