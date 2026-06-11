terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

locals {
  name_prefix = "${var.project_name}-${var.environment}"

  tags = merge(
    {
      Project     = "LabFlow AI Studio"
      Environment = var.environment
      ManagedBy   = "terraform"
      Synthetic   = "true"
    },
    var.tags
  )
}

module "s3" {
  source = "./modules/s3"

  name_prefix = local.name_prefix
  tags        = local.tags
}

module "dynamodb" {
  source = "./modules/dynamodb"

  name_prefix = local.name_prefix
  tags        = local.tags
}

module "iam" {
  source = "./modules/iam"

  name_prefix       = local.name_prefix
  dynamodb_tables   = module.dynamodb.table_arns
  artifact_bucket   = module.s3.artifact_bucket_arn
  knowledge_bucket  = module.s3.knowledge_bucket_arn
  instrument_bucket = module.s3.instrument_bucket_arn
  eval_bucket       = module.s3.eval_bucket_arn
  tags              = local.tags
}

module "cloudwatch" {
  source = "./modules/cloudwatch"

  name_prefix        = local.name_prefix
  log_retention_days = var.log_retention_days
  tags               = local.tags
}

module "lambda_api" {
  source = "./modules/lambda_api"

  name_prefix       = local.name_prefix
  lambda_role_arn   = module.iam.lambda_role_arn
  log_group_name    = module.cloudwatch.lambda_log_group_name
  artifact_bucket   = module.s3.artifact_bucket_name
  knowledge_bucket  = module.s3.knowledge_bucket_name
  instrument_bucket = module.s3.instrument_bucket_name
  eval_bucket       = module.s3.eval_bucket_name
  table_names       = module.dynamodb.table_names
  tags              = local.tags
}

module "api_gateway" {
  source = "./modules/api_gateway"

  name_prefix          = local.name_prefix
  lambda_function_name = module.lambda_api.function_name
  lambda_invoke_arn    = module.lambda_api.invoke_arn
  access_log_group_arn = module.cloudwatch.api_access_log_group_arn
  tags                 = local.tags
}
