#!/bin/bash

set -e

echo "🚀 AWS Lambda デプロイ環境のセットアップを開始します"
echo ""

# ======================================
# 1. 前提条件の確認
# ======================================
echo "📋 前提条件を確認中..."

# Node.js
if ! command -v node &> /dev/null; then
    echo "❌ Node.jsがインストールされていません"
    echo "   インストール: https://nodejs.org/"
    exit 1
fi
echo "✅ Node.js $(node --version)"

# Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Dockerがインストールされていません"
    echo "   インストール: https://www.docker.com/get-started"
    exit 1
fi
echo "✅ Docker $(docker --version | cut -d' ' -f3 | tr -d ',')"

# Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3がインストールされていません"
    exit 1
fi
echo "✅ Python $(python3 --version | cut -d' ' -f2)"

echo ""

# ======================================
# 2. AWS CLIのインストール確認
# ======================================
echo "📦 AWS CLIを確認中..."

if ! command -v aws &> /dev/null; then
    echo "⚠️  AWS CLIがインストールされていません"
    echo ""
    echo "macOSの場合、以下のコマンドでインストールできます:"
    echo ""
    echo "  curl \"https://awscli.amazonaws.com/AWSCLIV2.pkg\" -o \"AWSCLIV2.pkg\""
    echo "  sudo installer -pkg AWSCLIV2.pkg -target /"
    echo ""
    echo "詳細: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
    echo ""
    read -p "続行しますか? (AWS CLIは後でインストールできます) [y/N]: " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo "✅ AWS CLI $(aws --version | cut -d' ' -f1 | cut -d'/' -f2)"

    # AWS認証情報の確認
    if aws sts get-caller-identity &> /dev/null; then
        echo "✅ AWS認証情報が設定されています"
        aws sts get-caller-identity --query 'Account' --output text | xargs -I {} echo "   アカウント: {}"
    else
        echo "⚠️  AWS認証情報が設定されていません"
        echo "   以下のコマンドで設定してください:"
        echo "   aws configure"
    fi
fi

echo ""

# ======================================
# 3. Node.js依存関係のインストール
# ======================================
echo "📦 Node.js依存関係をインストール中..."

npm install

echo "✅ Node.js依存関係のインストール完了"
echo ""

# ======================================
# 4. 環境変数の設定確認
# ======================================
echo "🔐 環境変数を確認中..."

if [ ! -f .env ]; then
    echo "⚠️  .envファイルが見つかりません"
    echo "   .env.exampleをコピーして.envを作成してください:"
    echo ""
    echo "   cp .env.example .env"
    echo ""
    echo "   その後、以下の環境変数を設定してください:"
    echo "   - DISCORD_APPLICATION_ID"
    echo "   - DISCORD_PUBLIC_KEY"
    echo "   - DISCORD_BOT_TOKEN"
    echo "   - GUILD_ID"
    echo "   - INPUT_CHANNEL_ID"
    echo ""

    read -p ".envファイルを今作成しますか? [y/N]: " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        cp .env.example .env
        echo "✅ .envファイルを作成しました"
        echo "   エディタで.envファイルを編集して環境変数を設定してください"

        # エディタで開く
        if command -v code &> /dev/null; then
            code .env
        elif command -v vim &> /dev/null; then
            vim .env
        else
            open -e .env 2>/dev/null || true
        fi
    fi
else
    echo "✅ .envファイルが見つかりました"

    # 必須環境変数のチェック
    source .env

    missing_vars=()
    [ -z "$DISCORD_APPLICATION_ID" ] && missing_vars+=("DISCORD_APPLICATION_ID")
    [ -z "$DISCORD_PUBLIC_KEY" ] && missing_vars+=("DISCORD_PUBLIC_KEY")
    [ -z "$DISCORD_BOT_TOKEN" ] && missing_vars+=("DISCORD_BOT_TOKEN")
    [ -z "$GUILD_ID" ] && missing_vars+=("GUILD_ID")
    [ -z "$INPUT_CHANNEL_ID" ] && missing_vars+=("INPUT_CHANNEL_ID")

    if [ ${#missing_vars[@]} -gt 0 ]; then
        echo "⚠️  以下の環境変数が設定されていません:"
        for var in "${missing_vars[@]}"; do
            echo "   - $var"
        done
        echo ""
        echo "   .envファイルを編集して設定してください"
    else
        echo "✅ 必須環境変数が全て設定されています"
    fi
fi

echo ""

# ======================================
# 5. セットアップ完了
# ======================================
echo "✅ セットアップが完了しました！"
echo ""
echo "📚 次のステップ:"
echo ""
echo "1. AWS認証情報を設定 (未設定の場合)"
echo "   aws configure"
echo ""
echo "2. .envファイルを編集して環境変数を設定 (未設定の場合)"
echo "   vi .env"
echo ""
echo "3. ECRリポジトリを作成"
echo "   aws ecr create-repository --repository-name wows-replay-bot --region ap-northeast-1"
echo ""
echo "4. Dockerイメージをビルド・プッシュ"
echo "   ./deploy_lambda.sh"
echo ""
echo "詳細は README_LAMBDA.md をご覧ください"
echo ""
