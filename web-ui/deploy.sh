#!/bin/bash

# WoWS Replay Web UI デプロイスクリプト

set -e

STAGE=${1:-dev}
BUCKET_NAME="wows-replay-web-ui-${STAGE}"
REGION="ap-northeast-1"

echo "======================================"
echo "WoWS Replay Web UI デプロイ"
echo "Stage: ${STAGE}"
echo "Bucket: ${BUCKET_NAME}"
echo "======================================"

# ビルド
echo ""
echo "[1/4] Building..."
npm run generate

# S3バケット存在確認
echo ""
echo "[2/4] Checking S3 bucket..."
if aws s3 ls "s3://${BUCKET_NAME}" 2>&1 | grep -q 'NoSuchBucket'
then
    echo "Creating S3 bucket: ${BUCKET_NAME}"
    aws s3 mb "s3://${BUCKET_NAME}" --region ${REGION}

    # 静的ウェブサイトホスティング有効化
    echo "Enabling static website hosting..."
    aws s3 website "s3://${BUCKET_NAME}" \
        --index-document index.html \
        --error-document 404.html

    # パブリックアクセス設定
    echo "Setting public access policy..."
    aws s3api put-bucket-policy --bucket ${BUCKET_NAME} --policy '{
      "Version": "2012-10-17",
      "Statement": [
        {
          "Sid": "PublicReadGetObject",
          "Effect": "Allow",
          "Principal": "*",
          "Action": "s3:GetObject",
          "Resource": "arn:aws:s3:::'${BUCKET_NAME}'/*"
        }
      ]
    }'
else
    echo "S3 bucket already exists: ${BUCKET_NAME}"
fi

# アップロード
echo ""
echo "[3/4] Uploading to S3..."
aws s3 sync .output/public/ "s3://${BUCKET_NAME}" --delete

# 完了
echo ""
echo "[4/4] Done!"
echo ""
echo "======================================"
echo "デプロイ完了"
echo "URL: http://${BUCKET_NAME}.s3-website-${REGION}.amazonaws.com"
echo "======================================"
