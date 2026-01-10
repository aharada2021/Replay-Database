"""
コメントAPIハンドラー

試合ごとにコメントを追加・編集・削除・いいねする機能を提供
"""

import json
import os
import time
import uuid
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError


def decimal_to_int(obj):
    """DynamoDBのDecimal型をintに変換"""
    if isinstance(obj, Decimal):
        return int(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


class DecimalEncoder(json.JSONEncoder):
    """Decimal型をJSONエンコードするカスタムエンコーダー"""

    def default(self, obj):
        if isinstance(obj, Decimal):
            return int(obj)
        return super().default(obj)

# 環境変数
COMMENTS_TABLE = os.environ.get("COMMENTS_TABLE", "wows-comments-dev")
SESSIONS_TABLE = os.environ.get("SESSIONS_TABLE", "wows-sessions-dev")
REPLAYS_TABLE = os.environ.get("REPLAYS_TABLE", "wows-replays-dev")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "")

# DynamoDB
dynamodb = boto3.resource("dynamodb")
comments_table = dynamodb.Table(COMMENTS_TABLE)
sessions_table = dynamodb.Table(SESSIONS_TABLE)
replays_table = dynamodb.Table(REPLAYS_TABLE)

# コメント文字数制限
MAX_COMMENT_LENGTH = 1000


def update_replays_comment_count(arena_unique_id: str, delta: int):
    """
    ReplaysTableのコメント数を更新

    Args:
        arena_unique_id: 試合ID
        delta: 増減値（+1 または -1）
    """
    try:
        # 該当arenaUniqueIDの全レコードを取得
        response = replays_table.query(
            KeyConditionExpression="arenaUniqueID = :aid",
            ExpressionAttributeValues={":aid": arena_unique_id},
            ProjectionExpression="arenaUniqueID, playerID",
        )

        # 各レコードのcommentCountを更新
        for item in response.get("Items", []):
            replays_table.update_item(
                Key={
                    "arenaUniqueID": item["arenaUniqueID"],
                    "playerID": item["playerID"],
                },
                UpdateExpression="SET commentCount = if_not_exists(commentCount, :zero) + :delta",
                ExpressionAttributeValues={":zero": 0, ":delta": delta},
            )

        print(f"Updated commentCount for {arena_unique_id}: delta={delta}, records={len(response.get('Items', []))}")

    except Exception as e:
        # コメントカウント更新失敗はログのみ（コメント操作自体は成功させる）
        print(f"Failed to update commentCount for {arena_unique_id}: {e}")


def get_cors_headers(origin=None):
    """CORS ヘッダーを取得"""
    allowed_origins = [
        FRONTEND_URL,
        "http://localhost:3000",
    ]

    if origin and origin in allowed_origins:
        return {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Headers": "Content-Type, Cookie",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
        }

    return {
        "Access-Control-Allow-Origin": allowed_origins[0] if allowed_origins[0] else "*",
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Allow-Headers": "Content-Type, Cookie",
        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
    }


def get_cookie(event, name):
    """CookieからセッションIDを取得"""
    cookies = event.get("cookies", [])
    for cookie in cookies:
        if cookie.startswith(f"{name}="):
            return cookie.split("=", 1)[1].split(";")[0]

    # headers から取得（HTTP API v2）
    headers = event.get("headers", {})
    cookie_header = headers.get("cookie") or headers.get("Cookie", "")
    for part in cookie_header.split(";"):
        part = part.strip()
        if part.startswith(f"{name}="):
            return part.split("=", 1)[1]

    return None


def get_session(event):
    """セッション情報を取得（認証済みの場合）"""
    session_id = get_cookie(event, "session_id")
    if not session_id:
        return None

    try:
        response = sessions_table.get_item(Key={"sessionId": session_id})
        session = response.get("Item")
    except Exception as e:
        print(f"Session lookup error: {e}")
        return None

    if not session:
        return None

    # 有効期限チェック
    if session.get("expiresAt", 0) < int(time.time()):
        return None

    return session


def handle(event, context):
    """
    コメントAPIのルーティングハンドラー
    """
    origin = event.get("headers", {}).get("origin") or event.get("headers", {}).get("Origin")
    cors_headers = get_cors_headers(origin)

    # HTTPメソッドとパスを取得
    http_method = event.get("requestContext", {}).get("http", {}).get("method", "GET")
    path = event.get("rawPath", "")

    # OPTIONSリクエスト
    if http_method == "OPTIONS":
        return {"statusCode": 200, "headers": cors_headers, "body": ""}

    # パスパラメータを取得
    path_params = event.get("pathParameters", {}) or {}
    arena_unique_id = path_params.get("arenaUniqueID")
    comment_id = path_params.get("commentId")

    if not arena_unique_id:
        return {
            "statusCode": 400,
            "headers": cors_headers,
            "body": json.dumps({"error": "arenaUniqueID is required"}),
        }

    # ルーティング
    if "/like" in path and http_method == "POST":
        return handle_like_comment(event, arena_unique_id, comment_id, cors_headers)
    elif comment_id and http_method == "PUT":
        return handle_update_comment(event, arena_unique_id, comment_id, cors_headers)
    elif comment_id and http_method == "DELETE":
        return handle_delete_comment(event, arena_unique_id, comment_id, cors_headers)
    elif http_method == "POST":
        return handle_post_comment(event, arena_unique_id, cors_headers)
    elif http_method == "GET":
        return handle_get_comments(event, arena_unique_id, cors_headers)
    else:
        return {
            "statusCode": 405,
            "headers": cors_headers,
            "body": json.dumps({"error": "Method not allowed"}),
        }


def handle_get_comments(event, arena_unique_id, cors_headers):
    """
    コメント一覧を取得
    認証不要
    """
    try:
        response = comments_table.query(
            KeyConditionExpression="arenaUniqueID = :aid",
            ExpressionAttributeValues={":aid": arena_unique_id},
        )

        comments = response.get("Items", [])

        # createdAtでソート（古い順）
        comments.sort(key=lambda x: x.get("createdAt", ""))

        # likes配列をセットからリストに変換（DynamoDB SS型対応）
        for comment in comments:
            if "likes" in comment:
                if isinstance(comment["likes"], set):
                    comment["likes"] = list(comment["likes"])

        return {
            "statusCode": 200,
            "headers": {**cors_headers, "Content-Type": "application/json"},
            "body": json.dumps({"comments": comments}, cls=DecimalEncoder),
        }

    except Exception as e:
        print(f"Error in handle_get_comments: {e}")
        return {
            "statusCode": 500,
            "headers": cors_headers,
            "body": json.dumps({"error": str(e)}),
        }


def handle_post_comment(event, arena_unique_id, cors_headers):
    """
    コメントを投稿
    認証必須
    """
    try:
        # 認証チェック
        session = get_session(event)
        if not session:
            return {
                "statusCode": 401,
                "headers": cors_headers,
                "body": json.dumps({"error": "Authentication required"}),
            }

        # リクエストボディを取得
        try:
            body = json.loads(event.get("body", "{}"))
        except json.JSONDecodeError:
            return {
                "statusCode": 400,
                "headers": cors_headers,
                "body": json.dumps({"error": "Invalid JSON body"}),
            }

        content = body.get("content", "").strip()

        if not content:
            return {
                "statusCode": 400,
                "headers": cors_headers,
                "body": json.dumps({"error": "Content is required"}),
            }

        if len(content) > MAX_COMMENT_LENGTH:
            return {
                "statusCode": 400,
                "headers": cors_headers,
                "body": json.dumps({"error": f"Content exceeds {MAX_COMMENT_LENGTH} characters"}),
            }

        # コメントを作成
        comment_id = str(uuid.uuid4())
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        comment = {
            "arenaUniqueID": arena_unique_id,
            "commentId": comment_id,
            "discordUserId": session.get("discordUserId"),
            "discordUsername": session.get("discordUsername", ""),
            "discordGlobalName": session.get("discordGlobalName", ""),
            "discordAvatar": session.get("discordAvatar"),
            "content": content,
            "createdAt": now,
            "updatedAt": None,
            "likes": [],
            "likeCount": 0,
        }

        comments_table.put_item(Item=comment)

        # ReplaysTableのコメント数を更新
        update_replays_comment_count(arena_unique_id, delta=1)

        return {
            "statusCode": 201,
            "headers": {**cors_headers, "Content-Type": "application/json"},
            "body": json.dumps(comment),
        }

    except Exception as e:
        print(f"Error in handle_post_comment: {e}")
        return {
            "statusCode": 500,
            "headers": cors_headers,
            "body": json.dumps({"error": str(e)}),
        }


def handle_update_comment(event, arena_unique_id, comment_id, cors_headers):
    """
    コメントを編集
    認証必須（誰でも編集可能）
    """
    try:
        # 認証チェック
        session = get_session(event)
        if not session:
            return {
                "statusCode": 401,
                "headers": cors_headers,
                "body": json.dumps({"error": "Authentication required"}),
            }

        # リクエストボディを取得
        try:
            body = json.loads(event.get("body", "{}"))
        except json.JSONDecodeError:
            return {
                "statusCode": 400,
                "headers": cors_headers,
                "body": json.dumps({"error": "Invalid JSON body"}),
            }

        content = body.get("content", "").strip()

        if not content:
            return {
                "statusCode": 400,
                "headers": cors_headers,
                "body": json.dumps({"error": "Content is required"}),
            }

        if len(content) > MAX_COMMENT_LENGTH:
            return {
                "statusCode": 400,
                "headers": cors_headers,
                "body": json.dumps({"error": f"Content exceeds {MAX_COMMENT_LENGTH} characters"}),
            }

        # コメントを更新
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        try:
            response = comments_table.update_item(
                Key={"arenaUniqueID": arena_unique_id, "commentId": comment_id},
                UpdateExpression="SET content = :content, updatedAt = :updatedAt",
                ExpressionAttributeValues={
                    ":content": content,
                    ":updatedAt": now,
                },
                ConditionExpression="attribute_exists(arenaUniqueID)",
                ReturnValues="ALL_NEW",
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return {
                    "statusCode": 404,
                    "headers": cors_headers,
                    "body": json.dumps({"error": "Comment not found"}),
                }
            raise

        comment = response.get("Attributes", {})

        # likes配列をセットからリストに変換
        if "likes" in comment and isinstance(comment["likes"], set):
            comment["likes"] = list(comment["likes"])

        return {
            "statusCode": 200,
            "headers": {**cors_headers, "Content-Type": "application/json"},
            "body": json.dumps(comment, cls=DecimalEncoder),
        }

    except Exception as e:
        print(f"Error in handle_update_comment: {e}")
        return {
            "statusCode": 500,
            "headers": cors_headers,
            "body": json.dumps({"error": str(e)}),
        }


def handle_delete_comment(event, arena_unique_id, comment_id, cors_headers):
    """
    コメントを削除
    認証必須（誰でも削除可能）
    """
    try:
        # 認証チェック
        session = get_session(event)
        if not session:
            return {
                "statusCode": 401,
                "headers": cors_headers,
                "body": json.dumps({"error": "Authentication required"}),
            }

        # コメントを削除
        try:
            comments_table.delete_item(
                Key={"arenaUniqueID": arena_unique_id, "commentId": comment_id},
                ConditionExpression="attribute_exists(arenaUniqueID)",
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return {
                    "statusCode": 404,
                    "headers": cors_headers,
                    "body": json.dumps({"error": "Comment not found"}),
                }
            raise

        # ReplaysTableのコメント数を更新
        update_replays_comment_count(arena_unique_id, delta=-1)

        return {
            "statusCode": 200,
            "headers": {**cors_headers, "Content-Type": "application/json"},
            "body": json.dumps({"success": True}),
        }

    except Exception as e:
        print(f"Error in handle_delete_comment: {e}")
        return {
            "statusCode": 500,
            "headers": cors_headers,
            "body": json.dumps({"error": str(e)}),
        }


def handle_like_comment(event, arena_unique_id, comment_id, cors_headers):
    """
    コメントにいいねを追加/解除（トグル）
    認証必須
    """
    try:
        # 認証チェック
        session = get_session(event)
        if not session:
            return {
                "statusCode": 401,
                "headers": cors_headers,
                "body": json.dumps({"error": "Authentication required"}),
            }

        user_id = session.get("discordUserId")

        # 現在のコメントを取得
        response = comments_table.get_item(
            Key={"arenaUniqueID": arena_unique_id, "commentId": comment_id}
        )

        comment = response.get("Item")
        if not comment:
            return {
                "statusCode": 404,
                "headers": cors_headers,
                "body": json.dumps({"error": "Comment not found"}),
            }

        # いいねをトグル
        likes = comment.get("likes", [])
        if isinstance(likes, set):
            likes = list(likes)

        if user_id in likes:
            # いいね解除
            likes.remove(user_id)
        else:
            # いいね追加
            likes.append(user_id)

        # 更新
        update_response = comments_table.update_item(
            Key={"arenaUniqueID": arena_unique_id, "commentId": comment_id},
            UpdateExpression="SET likes = :likes, likeCount = :likeCount",
            ExpressionAttributeValues={
                ":likes": likes,
                ":likeCount": len(likes),
            },
            ReturnValues="ALL_NEW",
        )

        updated_comment = update_response.get("Attributes", {})

        # likes配列をセットからリストに変換
        if "likes" in updated_comment and isinstance(updated_comment["likes"], set):
            updated_comment["likes"] = list(updated_comment["likes"])

        return {
            "statusCode": 200,
            "headers": {**cors_headers, "Content-Type": "application/json"},
            "body": json.dumps(updated_comment, cls=DecimalEncoder),
        }

    except Exception as e:
        print(f"Error in handle_like_comment: {e}")
        return {
            "statusCode": 500,
            "headers": cors_headers,
            "body": json.dumps({"error": str(e)}),
        }
