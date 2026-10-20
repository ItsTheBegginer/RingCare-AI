#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# RingCare AI – Deploy backend Docker image to ECR
# Usage:
#   ECR_REPO=123456789.dkr.ecr.ap-south-1.amazonaws.com/ringcare-ai \
#   AWS_REGION=ap-south-1 \
#   ./infra/deploy-backend.sh
# ---------------------------------------------------------------------------

: "${ECR_REPO:?ECR_REPO must be set (e.g. 123456789.dkr.ecr.ap-south-1.amazonaws.com/ringcare-ai)}"
: "${AWS_REGION:?AWS_REGION must be set}"

echo "[1/3] Building Docker image ..."
docker build -t ringcare-ai-backend .

echo "[2/3] Tagging image for ECR ..."
docker tag ringcare-ai-backend:latest "${ECR_REPO}:latest"

echo "[3/3] Pushing to ECR ..."
aws ecr get-login-password --region "${AWS_REGION}" \
  | docker login --username AWS --password-stdin "${ECR_REPO%%/*}"
docker push "${ECR_REPO}:latest"

echo ""
echo "=== Done ==="
echo ""
echo "Next steps:"
echo "  1. In the AWS App Runner console, create a new service pointing to:"
echo "       ${ECR_REPO}:latest"
echo "  2. Set the following environment variables in App Runner:"
echo "       STORAGE_BACKEND=dynamodb"
echo "       VISION_BACKEND=rekognition"
echo "       CLIPS_BACKEND=s3"
echo "       S3_BUCKET=<your-clips-bucket>"
echo "       S3_REGION=${AWS_REGION}"
echo "       AWS_REGION=${AWS_REGION}"
echo "       RING_ACCESS_TOKEN=<your-ring-token>"
echo "       SNS_TOPIC_ARN=<your-sns-arn>"
echo "  3. Attach an IAM role to the App Runner service with S3, DynamoDB, Rekognition, and SNS permissions."
