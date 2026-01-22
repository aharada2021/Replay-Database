"""
Claude API クライアント

戦闘データ分析用のClaude APIラッパー。

Version: 2026-01-23 - Initial implementation
"""

import os
import json
from typing import Dict, Any, Optional
import anthropic

# Claude API設定
MODEL_ID = "claude-sonnet-4-20250514"  # コスト効率重視
MAX_TOKENS = 4096
TEMPERATURE = 0.7

# システムプロンプト（日本語対応）
SYSTEM_PROMPT = """あなたはWorld of Warshipsの戦闘アナリストです。
提供された戦闘統計を分析し、プレイヤーの質問に具体的なアドバイスを返してください。

## ガイドライン

1. **具体的な数値を引用して説明する**
   - 「勝率は58%で平均ダメージは85,000です」のように、データに基づいて説明

2. **パターンや傾向を特定する**
   - 特定のマップや艦種での成績の違いを指摘
   - 最近のトレンド（調子の良し悪し）を分析

3. **改善のための具体的なアドバイスを提供する**
   - 成績の良い艦や悪い艦を特定し、改善点を示唆
   - マップごとの立ち回りなど、実践的なアドバイス

4. **データが不足している場合は明確に伝える**
   - 分析に必要なデータがない場合は正直に伝える

5. **フォーマット**
   - 見出し（##）や箇条書きを使って読みやすくする
   - 長文は避け、要点を簡潔にまとめる

## 用語説明
- winLoss: 勝敗（win/loss/draw）
- damage: 与ダメージ
- spottingDamage: 観測ダメージ
- potentialDamage: 潜在ダメージ（受けた砲弾の総ダメージポテンシャル）
- receivedDamage: 被ダメージ
- kills: 撃沈数
- baseXP: 基本経験値
- citadels: バイタルヒット数
- fires: 火災発生数
- floods: 浸水発生数

## 注意事項
- ゲームプレイの楽しさを損なわないよう、批判的すぎる表現は避ける
- 改善点を指摘する際も、良い点も併せて伝える
- 回答は日本語で行う
"""

# APIキーの遅延初期化
_client = None


def get_client() -> anthropic.Anthropic:
    """Anthropicクライアントを取得（遅延初期化）"""
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is not set")
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


def validate_query(query: str) -> tuple[bool, str]:
    """
    クエリのバリデーション

    Args:
        query: ユーザーのクエリ

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not query or not query.strip():
        return False, "クエリが空です"

    query = query.strip()

    if len(query) > 500:
        return False, "クエリは500文字以内で入力してください"

    if len(query) < 3:
        return False, "クエリは3文字以上で入力してください"

    # 危険なパターンの簡易チェック（プロンプトインジェクション対策）
    dangerous_patterns = [
        "ignore previous",
        "ignore above",
        "ignore all",
        "disregard",
        "forget everything",
        "new instructions",
        "system prompt",
        "you are now",
        "act as",
        "pretend to be",
    ]

    query_lower = query.lower()
    for pattern in dangerous_patterns:
        if pattern in query_lower:
            return False, "不正なクエリパターンが検出されました"

    return True, ""


def format_battle_data_for_prompt(battle_data: Dict[str, Any]) -> str:
    """
    戦闘データをプロンプト用のテキストに変換

    Args:
        battle_data: 集計された戦闘データ

    Returns:
        フォーマットされたテキスト
    """
    summary = battle_data.get("summary", {})
    by_game_type = battle_data.get("byGameType", {})
    by_map = battle_data.get("byMap", {})
    by_ship = battle_data.get("byShip", {})
    recent_trend = battle_data.get("recentTrend", {})
    recent_battles = battle_data.get("recentBattles", [])
    metadata = battle_data.get("metadata", {})

    lines = []

    # メタデータ
    lines.append("## 分析データ概要")
    date_range = metadata.get("dateRange", {})
    lines.append(f"- 期間: {date_range.get('from', 'N/A')} ～ {date_range.get('to', 'N/A')}")
    game_type_filter = metadata.get("gameTypeFilter")
    if game_type_filter:
        lines.append(f"- ゲームタイプ: {game_type_filter}")
    lines.append(f"- 取得試合数: {metadata.get('totalBattlesFetched', 0)}")
    lines.append("")

    # 全体統計
    lines.append("## 全体統計")
    lines.append(f"- 総試合数: {summary.get('totalBattles', 0)}")
    lines.append(f"- 勝敗: {summary.get('wins', 0)}勝 / {summary.get('losses', 0)}敗 / {summary.get('draws', 0)}引分")
    lines.append(f"- 勝率: {summary.get('winRate', 0) * 100:.1f}%")
    lines.append(f"- 平均ダメージ: {summary.get('avgDamage', 0):,.0f}")
    lines.append(f"- 平均キル: {summary.get('avgKills', 0):.1f}")
    lines.append(f"- 平均観測ダメージ: {summary.get('avgSpottingDamage', 0):,.0f}")
    lines.append(f"- 平均潜在ダメージ: {summary.get('avgPotentialDamage', 0):,.0f}")
    lines.append(f"- 平均被ダメージ: {summary.get('avgReceivedDamage', 0):,.0f}")
    lines.append(f"- 平均基本XP: {summary.get('avgBaseXP', 0):,.0f}")
    lines.append("")

    # ゲームタイプ別
    if by_game_type:
        lines.append("## ゲームタイプ別統計")
        for gt, stats in sorted(by_game_type.items(), key=lambda x: x[1]["battles"], reverse=True):
            lines.append(f"### {gt}")
            lines.append(f"- 試合数: {stats['battles']}")
            lines.append(f"- 勝率: {stats['winRate'] * 100:.1f}%")
            lines.append(f"- 平均ダメージ: {stats['avgDamage']:,.0f}")
        lines.append("")

    # マップ別（上位5つ）
    if by_map:
        lines.append("## マップ別統計（上位5マップ）")
        sorted_maps = sorted(by_map.items(), key=lambda x: x[1]["battles"], reverse=True)[:5]
        for map_name, stats in sorted_maps:
            lines.append(f"### {map_name}")
            lines.append(f"- 試合数: {stats['battles']}")
            lines.append(f"- 勝率: {stats['winRate'] * 100:.1f}%")
            lines.append(f"- 平均ダメージ: {stats['avgDamage']:,.0f}")
        lines.append("")

    # 艦種別（上位10艦）
    if by_ship:
        lines.append("## 艦艇別統計（上位10艦）")
        sorted_ships = sorted(by_ship.items(), key=lambda x: x[1]["battles"], reverse=True)[:10]
        for ship_name, stats in sorted_ships:
            lines.append(f"### {ship_name}")
            lines.append(f"- 試合数: {stats['battles']}")
            lines.append(f"- 勝率: {stats['winRate'] * 100:.1f}%")
            lines.append(f"- 平均ダメージ: {stats['avgDamage']:,.0f}")
        lines.append("")

    # 最近のトレンド
    if recent_trend:
        lines.append("## 最近のトレンド")
        last10 = recent_trend.get("last10", {})
        prev10 = recent_trend.get("previous10", {})
        lines.append("### 直近10戦")
        lines.append(f"- 試合数: {last10.get('battles', 0)}")
        lines.append(f"- 勝率: {last10.get('winRate', 0) * 100:.1f}%")
        lines.append(f"- 平均ダメージ: {last10.get('avgDamage', 0):,.0f}")
        lines.append("### その前の10戦")
        lines.append(f"- 試合数: {prev10.get('battles', 0)}")
        lines.append(f"- 勝率: {prev10.get('winRate', 0) * 100:.1f}%")
        lines.append(f"- 平均ダメージ: {prev10.get('avgDamage', 0):,.0f}")
        lines.append("")

    # 最近の戦闘詳細（最大10件）
    if recent_battles:
        lines.append("## 最近の試合詳細（最大10件）")
        for i, b in enumerate(recent_battles[:10], 1):
            result = {"win": "勝利", "loss": "敗北", "draw": "引分"}.get(b.get("winLoss", ""), "不明")
            lines.append(f"{i}. {b.get('dateTime', 'N/A')} | {b.get('shipName', 'N/A')} | {b.get('mapDisplayName', 'N/A')} | {result}")
            lines.append(f"   ダメージ: {b.get('damage', 0):,} | キル: {b.get('kills', 0)} | XP: {b.get('baseXP', 0):,}")
        lines.append("")

    return "\n".join(lines)


def analyze_battles(
    query: str,
    battle_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    戦闘データを分析

    Args:
        query: ユーザーのクエリ（質問）
        battle_data: 集計された戦闘データ

    Returns:
        分析結果
        {
            "analysis": str,  # 分析テキスト
            "tokensUsed": int,  # 使用トークン数
            "success": bool,
            "error": str or None
        }
    """
    # クエリバリデーション
    is_valid, error_msg = validate_query(query)
    if not is_valid:
        return {
            "analysis": "",
            "tokensUsed": 0,
            "success": False,
            "error": error_msg,
        }

    # 戦闘データをテキスト化
    battle_text = format_battle_data_for_prompt(battle_data)

    # ユーザーメッセージを構築
    user_message = f"""以下の戦闘データに基づいて、質問に回答してください。

{battle_text}

## 質問
{query.strip()}
"""

    try:
        client = get_client()

        response = client.messages.create(
            model=MODEL_ID,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": user_message}
            ],
        )

        # レスポンスを処理
        analysis_text = ""
        for block in response.content:
            if hasattr(block, "text"):
                analysis_text += block.text

        # トークン使用量を計算
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        total_tokens = input_tokens + output_tokens

        return {
            "analysis": analysis_text,
            "tokensUsed": total_tokens,
            "inputTokens": input_tokens,
            "outputTokens": output_tokens,
            "success": True,
            "error": None,
        }

    except anthropic.APIError as e:
        print(f"Claude API error: {e}")
        return {
            "analysis": "",
            "tokensUsed": 0,
            "success": False,
            "error": f"Claude APIエラー: {str(e)}",
        }
    except Exception as e:
        print(f"Unexpected error in analyze_battles: {e}")
        import traceback
        traceback.print_exc()
        return {
            "analysis": "",
            "tokensUsed": 0,
            "success": False,
            "error": f"予期しないエラーが発生しました: {str(e)}",
        }
