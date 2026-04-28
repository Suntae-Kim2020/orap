#!/usr/bin/env bash
# orap → orap.ailibrary.kr Cloud Run 배포 스크립트

set -euo pipefail

PROJECT="ailibrary-orap"
REGION="asia-northeast1"
SERVICE="orap"
BUCKET="ailibrary-orap-data"

cd "$(dirname "$0")"

echo "🚀 orap 배포 중..."
echo "   프로젝트: $PROJECT"
echo "   서비스:   $SERVICE"
echo "   리전:     $REGION"
echo "   URL:      https://orap.ailibrary.kr"
echo ""

gcloud run deploy "$SERVICE" \
  --source . \
  --project "$PROJECT" \
  --region "$REGION" \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --min-instances 1 \
  --max-instances 1 \
  --port 8080 \
  --timeout 600 \
  --set-env-vars="GCS_BUCKET=$BUCKET" \
  --set-secrets="FLASK_SECRET_KEY=orap-flask-secret:latest" \
  --quiet

echo ""
echo "✅ 배포 완료"
