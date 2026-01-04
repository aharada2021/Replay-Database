#!/bin/bash

echo "🔄 Botの再起動を開始します..."

# 既存のbotプロセスを検索（大文字小文字を区別しない）
BOT_PIDS=$(pgrep -fi "python.*bot\.py")

if [ -n "$BOT_PIDS" ]; then
    echo "既存のBotプロセスを終了します: $BOT_PIDS"
    pkill -9 -fi "python.*bot\.py"
    sleep 3
    echo "✅ 既存のプロセスを終了しました"
else
    echo "既存のBotプロセスは見つかりませんでした"
fi

# 作業ディレクトリに移動
cd "$(dirname "$0")"

# ログファイルをクリア
> bot.log

echo "🚀 新しいBotプロセスを起動します..."

# Botをバックグラウンドで起動
nohup python3 bot.py > bot.log 2>&1 &

# プロセスIDを保存
echo $! > bot.pid

sleep 5

# 起動確認（大文字小文字を区別しない）
if pgrep -fi "python.*bot\.py" > /dev/null; then
    echo "✅ Botが正常に起動しました"
    echo "プロセスID: $(cat bot.pid)"

    # ログの最後の数行を表示
    echo ""
    echo "--- 起動ログ ---"
    tail -20 bot.log
    exit 0
else
    echo "❌ Botの起動に失敗しました"
    echo "--- エラーログ ---"
    cat bot.log
    exit 1
fi
