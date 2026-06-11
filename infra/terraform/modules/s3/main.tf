locals {
  buckets = {
    knowledge   = "${var.name_prefix}-knowledge"
    instruments = "${var.name_prefix}-instrument-files"
    artifacts   = "${var.name_prefix}-artifacts"
    evals       = "${var.name_prefix}-eval-reports"
  }

  prefixes = {
    knowledge = [
      "corpus/",
      "chunks/",
      "indexes/",
    ]
    instruments = [
      "varioskan/",
      "imports/",
    ]
    artifacts = [
      "janus/",
      "audit-reports/",
      "workflow-patches/",
    ]
    evals = [
      "reports/",
      "golden-cases/",
      "regressions/",
    ]
  }
}

resource "aws_s3_bucket" "this" {
  for_each = local.buckets

  bucket = each.value
  tags   = merge(var.tags, { LabFlowDataClass = each.key })
}

resource "aws_s3_bucket_versioning" "this" {
  for_each = aws_s3_bucket.this

  bucket = each.value.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "this" {
  for_each = aws_s3_bucket.this

  bucket = each.value.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "this" {
  for_each = aws_s3_bucket.this

  bucket                  = each.value.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
