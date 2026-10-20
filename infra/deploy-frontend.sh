#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# RingCare AI – Deploy frontend to S3 + CloudFront
# Usage:
#   FRONTEND_BUCKET=my-ringcare-frontend \
#   CF_DISTRIBUTION_ID=EXAMPLEID \
#   ./infra/deploy-frontend.sh
# ---------------------------------------------------------------------------

: "${FRONTEND_BUCKET:?FRONTEND_BUCKET must be set (S3 bucket name for static hosting)}"

# Pass VITE_API_URL into the build if provided
if [ -n "${API_URL:-}" ]; then
  export VITE_API_URL="${API_URL}"
  echo "Building with VITE_API_URL=${VITE_API_URL}"
fi

echo "[1/3] Building frontend ..."
npm run build

echo "[2/3] Syncing dist/ to s3://${FRONTEND_BUCKET} ..."
aws s3 sync dist/ "s3://${FRONTEND_BUCKET}" --delete

if [ -n "${CF_DISTRIBUTION_ID:-}" ]; then
  echo "[3/3] Invalidating CloudFront distribution ${CF_DISTRIBUTION_ID} ..."
  aws cloudfront create-invalidation \
    --distribution-id "${CF_DISTRIBUTION_ID}" \
    --paths "/*"
  echo ""
  echo "=== Frontend deployed ==="
  echo "CloudFront URL: https://$(aws cloudfront get-distribution --id ${CF_DISTRIBUTION_ID} --query 'Distribution.DomainName' --output text)"
else
  echo "[3/3] No CF_DISTRIBUTION_ID set — skipping CloudFront invalidation."
  echo ""
  echo "=== Frontend deployed ==="
  echo "S3 Website URL: http://${FRONTEND_BUCKET}.s3-website.$(aws configure get region 2>/dev/null || echo 'us-east-1').amazonaws.com"
fi
