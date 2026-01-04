#!/bin/bash

set -e

echo "🚀 AWS Lambdaへのデプロイを開始します"
echo ""

# 環境変数の読み込み
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# AWSリージョン
REGION="${AWS_REGION:-ap-northeast-1}"
REPOSITORY_NAME="wows-replay-bot"
STAGE="${DEPLOY_STAGE:-dev}"

# ======================================
# 1. AWS認証情報の確認
# ======================================
echo "🔐 AWS認証情報を確認中..."

if ! aws sts get-caller-identity &> /dev/null; then
    echo "❌ AWS認証情報が設定されていません"
    echo "   以下のコマンドで設定してください:"
    echo "   aws configure"
    exit 1
fi

ACCOUNT_ID=$(aws sts get-caller-identity --query 'Account' --output text)
echo "✅ AWSアカウント: $ACCOUNT_ID"
echo "✅ リージョン: $REGION"
echo ""

# ======================================
# 2. ECRリポジトリの作成 (存在しない場合)
# ======================================
echo "📦 ECRリポジトリを確認中..."

if ! aws ecr describe-repositories --repository-names $REPOSITORY_NAME --region $REGION &> /dev/null; then
    echo "ECRリポジトリが存在しません。作成します..."
    aws ecr create-repository \
        --repository-name $REPOSITORY_NAME \
        --region $REGION \
        --image-scanning-configuration scanOnPush=true
    echo "✅ ECRリポジトリを作成しました"
else
    echo "✅ ECRリポジトリが存在します"
fi

ECR_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${REPOSITORY_NAME}"
echo "   リポジトリURI: $ECR_URI"
echo ""

# ======================================
# 3. ECRにログイン
# ======================================
echo "🔑 ECRにログイン中..."

aws ecr get-login-password --region $REGION | \
    docker login --username AWS --password-stdin $ECR_URI

echo "✅ ECRにログインしました"
echo ""

# ======================================
# 4. Dockerイメージのビルド
# ======================================
echo "🐳 Dockerイメージをビルド中..."
echo "   これには数分かかる場合があります..."

docker build -f deploy/Dockerfile -t $REPOSITORY_NAME:latest .

echo "✅ Dockerイメージのビルド完了"
echo ""

# ======================================
# 5. Dockerイメージのタグ付け
# ======================================
echo "🏷️  Dockerイメージをタグ付け中..."

docker tag $REPOSITORY_NAME:latest $ECR_URI:latest
docker tag $REPOSITORY_NAME:latest $ECR_URI:$STAGE

echo "✅ タグ付け完了"
echo ""

# ======================================
# 6. Dockerイメージをプッシュ
# ======================================
echo "📤 Dockerイメージをプッシュ中..."
echo "   これには数分かかる場合があります..."

docker push $ECR_URI:latest
docker push $ECR_URI:$STAGE

echo "✅ Dockerイメージのプッシュ完了"
echo ""

# ======================================
# 7. serverless.ymlのECR URI更新
# ======================================
echo "📝 serverless.ymlを更新中..."

# macOSとLinuxの両方に対応
if [[ "$OSTYPE" == "darwin"* ]]; then
    sed -i '' "s|uri: .*\.dkr\.ecr\..*\.amazonaws\.com/wows-replay-bot:.*|uri: $ECR_URI:$STAGE|g" deploy/serverless.yml
else
    sed -i "s|uri: .*\.dkr\.ecr\..*\.amazonaws\.com/wows-replay-bot:.*|uri: $ECR_URI:$STAGE|g" deploy/serverless.yml
fi

echo "✅ serverless.ymlを更新しました"
echo ""

# ======================================
# 8. Serverless Frameworkでデプロイ
# ======================================
echo "🚀 Lambda関数をデプロイ中..."

cd deploy
npx serverless deploy --stage $STAGE
cd ..

echo ""
echo "✅ デプロイが完了しました！"
echo ""

# ======================================
# 9. Interactions Endpoint URLを表示
# ======================================
echo "📋 次のステップ:"
echo ""
echo "1. Discord Developer Portalで Interactions Endpoint URL を設定"
echo "   https://discord.com/developers/applications"
echo ""
echo "   Interactions Endpoint URL:"
cd deploy
ENDPOINT=$(npx serverless info --stage $STAGE | grep "POST - " | awk '{print $3}')
cd ..
echo "   $ENDPOINT"
echo ""
echo "2. Slash Commandsを登録"
echo "   python3 src/register_commands.py"
echo ""
echo "3. Discordで /upload_replay コマンドをテスト"
echo ""
