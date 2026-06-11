data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda_api" {
  name               = "${var.name_prefix}-lambda-api"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
  tags               = var.tags
}

data "aws_iam_policy_document" "lambda_api" {
  statement {
    sid = "WriteLogs"
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents"
    ]
    resources = ["arn:aws:logs:*:*:log-group:/aws/lambda/${var.name_prefix}-api:*"]
  }

  statement {
    sid = "ReadWriteControlPlaneTables"
    actions = [
      "dynamodb:BatchGetItem",
      "dynamodb:BatchWriteItem",
      "dynamodb:DeleteItem",
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:Query",
      "dynamodb:UpdateItem"
    ]
    resources = var.dynamodb_tables
  }

  statement {
    sid = "ReadWriteLabFlowBuckets"
    actions = [
      "s3:GetObject",
      "s3:ListBucket",
      "s3:PutObject"
    ]
    resources = concat(
      [
        var.artifact_bucket,
        var.knowledge_bucket,
        var.instrument_bucket,
        var.eval_bucket
      ],
      [
        "${var.artifact_bucket}/*",
        "${var.knowledge_bucket}/*",
        "${var.instrument_bucket}/*",
        "${var.eval_bucket}/*"
      ]
    )
  }
}

resource "aws_iam_policy" "lambda_api" {
  name   = "${var.name_prefix}-lambda-api"
  policy = data.aws_iam_policy_document.lambda_api.json
  tags   = var.tags
}

resource "aws_iam_role_policy_attachment" "lambda_api" {
  role       = aws_iam_role.lambda_api.name
  policy_arn = aws_iam_policy.lambda_api.arn
}
