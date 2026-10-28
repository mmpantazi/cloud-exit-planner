terraform {
  backend "s3" { bucket = "acme-tfstate" }
}
provider "aws" { region = "eu-central-1" }

# user uploads
resource "aws_s3_bucket" "uploads" { bucket = "acme-uploads" }
resource "aws_s3_bucket" "archive" {
  bucket = "acme-archive"
  # lifecycle moves to GLACIER after 90 days
  storage_class = "GLACIER"
}
resource "aws_db_instance" "main" {
  engine            = "postgres"
  multi_az          = true
  storage_encrypted = true
}
resource "aws_lambda_function" "thumbs" { function_name = "thumbs" }
resource "aws_sqs_queue" "jobs" { name = "jobs" }
resource "aws_instance" "web" {
  count = 2
  ami   = "ami-123"
}
resource "aws_vpc" "main" { cidr_block = "10.0.0.0/16" }
resource "aws_cognito_user_pool" "users" { name = "users" }
