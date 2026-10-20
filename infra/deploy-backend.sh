#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# RingCare AI – Build, push to ECR, and deploy to an EC2 instance.
#
# Required env vars:
#   ECR_REPO   full ECR image URI, e.g. 123456789.dkr.ecr.ap-south-1.amazonaws.com/ringcare-ai
#   AWS_REGION e.g. ap-south-1
#   EC2_HOST   public IP or DNS of the EC2 instance, e.g. 1.2.3.4
#   EC2_KEY    path to the .pem key file, e.g. ~/keys/ringcare.pem
#
# Optional:
#   EC2_USER   SSH user (default: ec2-user; use ubuntu for Ubuntu AMIs)
#
# Usage:
#   ECR_REPO=... AWS_REGION=... EC2_HOST=... EC2_KEY=... ./infra/deploy-backend.sh
# ---------------------------------------------------------------------------

: "${ECR_REPO:?ECR_REPO must be set}"
: "${AWS_REGION:?AWS_REGION must be set}"
: "${EC2_HOST:?EC2_HOST must be set (public IP or DNS of your EC2 instance)}"
: "${EC2_KEY:?EC2_KEY must be set (path to your .pem key file)}"

EC2_USER="${EC2_USER:-ec2-user}"
IMAGE_TAG="${ECR_REPO}:latest"
REGISTRY="${ECR_REPO%%/*}"    # just the registry host, e.g. 123456789.dkr.ecr.ap-south-1.amazonaws.com

echo "==> [1/4] Building Docker image ..."
docker build -t ringcare-ai-backend:latest .

echo "==> [2/4] Tagging and pushing to ECR (${IMAGE_TAG}) ..."
docker tag ringcare-ai-backend:latest "${IMAGE_TAG}"
aws ecr get-login-password --region "${AWS_REGION}" \
  | docker login --username AWS --password-stdin "${REGISTRY}"
docker push "${IMAGE_TAG}"

echo "==> [3/4] Connecting to EC2 (${EC2_USER}@${EC2_HOST}) ..."
# The EC2 instance must have:
#   - Docker installed (sudo yum install -y docker && sudo systemctl start docker)
#   - AWS CLI installed and configured (IAM role attached is the cleanest approach)
#   - The instance's IAM role must have permissions for:
#       ECR (ecr:GetAuthorizationToken, ecr:BatchGetImage, ecr:GetDownloadUrlForLayer)
#       DynamoDB, Rekognition, SNS, S3 (scoped to the specific resources)
ssh -i "${EC2_KEY}" -o StrictHostKeyChecking=no "${EC2_USER}@${EC2_HOST}" bash <<REMOTE
set -euo pipefail

echo "  -> Logging in to ECR on EC2 ..."
aws ecr get-login-password --region "${AWS_REGION}" \
  | docker login --username AWS --password-stdin "${REGISTRY}"

echo "  -> Pulling latest image ..."
docker pull "${IMAGE_TAG}"

echo "  -> Stopping existing container (if any) ..."
docker rm -f ringcare-backend 2>/dev/null || true

echo "  -> Starting new container ..."
# Secrets come from the instance environment or a secrets manager call in your startup script.
# Pass them here with -e flags or load them from /etc/ringcare.env on the instance.
docker run -d \
  --name ringcare-backend \
  --restart unless-stopped \
  -p 8000:8000 \
  -v /home/${EC2_USER}/clips:/app/backend/clips \
  --env-file /etc/ringcare.env \
  "${IMAGE_TAG}"

echo "  -> Container started."
docker ps --filter name=ringcare-backend --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
REMOTE

echo "==> [4/4] Deployment complete."
echo ""
echo "Backend is running at:  http://${EC2_HOST}:8000/api/health"
echo ""
echo "--- EC2 first-time setup (if not done yet) ---"
echo "  # On the EC2 instance, create /etc/ringcare.env with:"
echo "  STORAGE_BACKEND=dynamodb"
echo "  VISION_BACKEND=rekognition"
echo "  CLIPS_BACKEND=s3"
echo "  AWS_REGION=${AWS_REGION}"
echo "  S3_BUCKET=<your-clips-bucket>"
echo "  SNS_TOPIC_ARN=<your-sns-arn>"
echo "  RING_ACCESS_TOKEN=<your-ring-playground-token>"
echo "  DDB_EVENTS_TABLE=RingCareEvents"
echo "  DDB_SETTINGS_TABLE=RingCareSettings"
echo "  NOTIFY_CHANNELS=sns"
echo "  RESIDENT_NAME=Eleanor Vance"
echo ""
echo "  # Secure the env file:"
echo "  sudo chmod 600 /etc/ringcare.env"
echo "  sudo chown root:root /etc/ringcare.env"
echo ""
echo "--- Security group (minimum inbound rules) ---"
echo "  Port 22  (SSH)  – your IP only"
echo "  Port 8000 (API) – your IP or a load balancer / CloudFront origin"
