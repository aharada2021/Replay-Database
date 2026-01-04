#!/bin/bash

set -e

echo "🔧 AWS CLI v2をインストールします"
echo ""

# 一時ディレクトリ
TMP_DIR=$(mktemp -d)
cd $TMP_DIR

echo "📥 AWS CLI v2をダウンロード中..."
curl -s "https://awscli.amazonaws.com/AWSCLIV2.pkg" -o "AWSCLIV2.pkg"

echo "✅ ダウンロード完了"
echo ""
echo "📦 AWS CLI v2をインストール中..."
echo "   管理者権限が必要です（パスワードを入力してください）"
sudo installer -pkg AWSCLIV2.pkg -target /

# クリーンアップ
cd -
rm -rf $TMP_DIR

echo ""
echo "✅ AWS CLI v2のインストールが完了しました"
echo ""

# バージョン確認
aws --version

echo ""
echo "📋 次のステップ:"
echo ""
echo "1. AWS認証情報を設定"
echo "   aws configure"
echo ""
echo "   必要な情報:"
echo "   - AWS Access Key ID"
echo "   - AWS Secret Access Key"
echo "   - Default region name: ap-northeast-1"
echo "   - Default output format: json"
echo ""
echo "2. セットアップを続行"
echo "   ./setup_lambda.sh"
echo ""
