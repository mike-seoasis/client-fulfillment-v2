#!/bin/bash
# LocalStack initialization script
# Creates the default S3 bucket for local development

set -e

echo "Creating S3 bucket: onboarding-files"
awslocal s3 mb s3://onboarding-files 2>/dev/null || echo "Bucket already exists"

echo "LocalStack S3 initialization complete"
