output "knowledge_bucket_name" {
  value = aws_s3_bucket.this["knowledge"].bucket
}

output "knowledge_bucket_arn" {
  value = aws_s3_bucket.this["knowledge"].arn
}

output "instrument_bucket_name" {
  value = aws_s3_bucket.this["instruments"].bucket
}

output "instrument_bucket_arn" {
  value = aws_s3_bucket.this["instruments"].arn
}

output "artifact_bucket_name" {
  value = aws_s3_bucket.this["artifacts"].bucket
}

output "artifact_bucket_arn" {
  value = aws_s3_bucket.this["artifacts"].arn
}

output "eval_bucket_name" {
  value = aws_s3_bucket.this["evals"].bucket
}

output "eval_bucket_arn" {
  value = aws_s3_bucket.this["evals"].arn
}

output "bucket_prefixes" {
  value = local.prefixes
}
