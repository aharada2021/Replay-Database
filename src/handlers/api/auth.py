"""
Discord OAuth2 認証APIハンドラー

Discord OAuth2を使った認証フローを処理
"""

import json
import os
import secrets
import time
import urllib.parse
import urllib.request

import boto3

# 環境変数
DISCORD_CLIENT_ID = os.environ.get("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET = os.environ.get("DISCORD_CLIENT_SECRET")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "https://wows-replay.mirage0926.com")
SESSIONS_TABLE = os.environ.get("SESSIONS_TABLE", "wows-sessions-dev")
ALLOWED_GUILD_ID = os.environ.get("ALLOWED_GUILD_ID", "487923834868072449")
ALLOWED_ROLE_IDS = os.environ.get("ALLOWED_ROLE_IDS", "487924554111516672,1458737823585927179")
UPLOAD_API_KEY = os.environ.get("UPLOAD_API_KEY", "")

# DynamoDB
dynamodb = boto3.resource("dynamodb")
sessions_table = dynamodb.Table(SESSIONS_TABLE)

# セッション有効期限（1ヶ月）
SESSION_TTL = 30 * 24 * 60 * 60

# Discord OAuth2 URLs
DISCORD_AUTH_URL = "https://discord.com/api/oauth2/authorize"
DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"
DISCORD_USER_URL = "https://discord.com/api/users/@me"
DISCORD_GUILDS_URL = "https://discord.com/api/users/@me/guilds"
DISCORD_GUILD_MEMBER_URL = "https://discord.com/api/users/@me/guilds/{guild_id}/member"


def get_redirect_uri():
    """リダイレクトURIを取得"""
    return f"{FRONTEND_URL}/api/auth/discord/callback"


def get_cors_headers(origin=None):
    """CORS ヘッダーを取得"""
    allowed_origins = [
        "https://wows-replay.mirage0926.com",
        "http://localhost:3000",
    ]

    if origin and origin in allowed_origins:
        return {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Headers": "Content-Type, Cookie",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        }

    return {
        "Access-Control-Allow-Origin": allowed_origins[0],
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Allow-Headers": "Content-Type, Cookie",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
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


def set_cookie_header(name, value, max_age=SESSION_TTL, secure=True):
    """Set-Cookie ヘッダーを生成"""
    cookie_parts = [
        f"{name}={value}",
        f"Max-Age={max_age}",
        "Path=/",
        "HttpOnly",
        "SameSite=Lax",
    ]
    if secure:
        cookie_parts.append("Secure")
    return "; ".join(cookie_parts)


def handle_discord_auth(event, context):
    """
    Discord OAuth2 認証開始

    /api/auth/discord にアクセスすると Discord認証ページにリダイレクト
    """
    try:
        origin = event.get("headers", {}).get("origin") or event.get("headers", {}).get("Origin")
        cors_headers = get_cors_headers(origin)

        # state パラメータ生成（CSRF対策）
        state = secrets.token_urlsafe(32)

        # stateをDynamoDBに保存（5分間有効）
        sessions_table.put_item(
            Item={
                "sessionId": f"state:{state}",
                "createdAt": int(time.time()),
                "expiresAt": int(time.time()) + 300,  # 5分
            }
        )

        # Discord認証URLを構築
        params = {
            "client_id": DISCORD_CLIENT_ID,
            "redirect_uri": get_redirect_uri(),
            "response_type": "code",
            "scope": "identify guilds guilds.members.read",
            "state": state,
        }
        auth_url = f"{DISCORD_AUTH_URL}?{urllib.parse.urlencode(params)}"

        # リダイレクト
        return {
            "statusCode": 302,
            "headers": {
                **cors_headers,
                "Location": auth_url,
            },
            "body": "",
        }

    except Exception as e:
        print(f"Error in handle_discord_auth: {e}")
        return {
            "statusCode": 500,
            "headers": get_cors_headers(),
            "body": json.dumps({"error": str(e)}),
        }


def handle_discord_callback(event, context):
    """
    Discord OAuth2 コールバック処理

    Discordからの認可コードを受け取り、アクセストークンに交換してセッションを作成
    """
    try:
        origin = event.get("headers", {}).get("origin") or event.get("headers", {}).get("Origin")
        cors_headers = get_cors_headers(origin)

        # クエリパラメータ取得
        query_params = event.get("queryStringParameters", {}) or {}
        code = query_params.get("code")
        state = query_params.get("state")
        error = query_params.get("error")

        # エラーチェック
        if error:
            return {
                "statusCode": 302,
                "headers": {
                    **cors_headers,
                    "Location": f"{FRONTEND_URL}/login?error={error}",
                },
                "body": "",
            }

        if not code or not state:
            return {
                "statusCode": 302,
                "headers": {
                    **cors_headers,
                    "Location": f"{FRONTEND_URL}/login?error=missing_params",
                },
                "body": "",
            }

        # state検証
        try:
            state_item = sessions_table.get_item(Key={"sessionId": f"state:{state}"})
            if "Item" not in state_item:
                return {
                    "statusCode": 302,
                    "headers": {
                        **cors_headers,
                        "Location": f"{FRONTEND_URL}/login?error=invalid_state",
                    },
                    "body": "",
                }
            # state削除
            sessions_table.delete_item(Key={"sessionId": f"state:{state}"})
        except Exception as e:
            print(f"State validation error: {e}")
            return {
                "statusCode": 302,
                "headers": {
                    **cors_headers,
                    "Location": f"{FRONTEND_URL}/login?error=state_error",
                },
                "body": "",
            }

        # アクセストークン取得
        token_data = {
            "client_id": DISCORD_CLIENT_ID,
            "client_secret": DISCORD_CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": get_redirect_uri(),
        }

        req = urllib.request.Request(
            DISCORD_TOKEN_URL,
            data=urllib.parse.urlencode(token_data).encode(),
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "wows-replay/1.0",
            },
        )

        try:
            with urllib.request.urlopen(req) as response:
                token_response = json.loads(response.read().decode())
        except urllib.error.HTTPError as e:
            error_body = e.read().decode() if e.fp else ""
            print(f"Token exchange error: {e.code} - {error_body}")
            return {
                "statusCode": 302,
                "headers": {
                    **cors_headers,
                    "Location": f"{FRONTEND_URL}/login?error=token_error",
                },
                "body": "",
            }

        access_token = token_response.get("access_token")
        if not access_token:
            return {
                "statusCode": 302,
                "headers": {
                    **cors_headers,
                    "Location": f"{FRONTEND_URL}/login?error=no_token",
                },
                "body": "",
            }

        # ユーザー情報取得
        user_req = urllib.request.Request(
            DISCORD_USER_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "User-Agent": "wows-replay/1.0",
            },
        )

        try:
            with urllib.request.urlopen(user_req) as response:
                user_data = json.loads(response.read().decode())
        except urllib.error.HTTPError as e:
            print(f"User info error: {e}")
            return {
                "statusCode": 302,
                "headers": {
                    **cors_headers,
                    "Location": f"{FRONTEND_URL}/login?error=user_error",
                },
                "body": "",
            }

        # ギルドメンバーシップ確認
        if ALLOWED_GUILD_ID:
            guilds_req = urllib.request.Request(
                DISCORD_GUILDS_URL,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "User-Agent": "wows-replay/1.0",
                },
            )

            try:
                with urllib.request.urlopen(guilds_req) as response:
                    guilds_data = json.loads(response.read().decode())
            except urllib.error.HTTPError as e:
                print(f"Guilds info error: {e}")
                return {
                    "statusCode": 302,
                    "headers": {
                        **cors_headers,
                        "Location": f"{FRONTEND_URL}/login?error=guilds_error",
                    },
                    "body": "",
                }

            # 許可されたギルドのメンバーかチェック
            is_member = any(guild.get("id") == ALLOWED_GUILD_ID for guild in guilds_data)

            if not is_member:
                print(f"User {user_data.get('id')} is not a member of guild {ALLOWED_GUILD_ID}")
                return {
                    "statusCode": 302,
                    "headers": {
                        **cors_headers,
                        "Location": f"{FRONTEND_URL}/login?error=not_member",
                    },
                    "body": "",
                }

            # ロールチェック
            if ALLOWED_ROLE_IDS:
                allowed_roles = [r.strip() for r in ALLOWED_ROLE_IDS.split(",") if r.strip()]

                if allowed_roles:
                    # ギルドメンバー情報を取得してロールを確認
                    member_url = DISCORD_GUILD_MEMBER_URL.format(guild_id=ALLOWED_GUILD_ID)
                    member_req = urllib.request.Request(
                        member_url,
                        headers={
                            "Authorization": f"Bearer {access_token}",
                            "User-Agent": "wows-replay/1.0",
                        },
                    )

                    try:
                        with urllib.request.urlopen(member_req) as response:
                            member_data = json.loads(response.read().decode())
                    except urllib.error.HTTPError as e:
                        print(f"Guild member info error: {e}")
                        return {
                            "statusCode": 302,
                            "headers": {
                                **cors_headers,
                                "Location": f"{FRONTEND_URL}/login?error=member_error",
                            },
                            "body": "",
                        }

                    # ユーザーのロールを取得
                    user_roles = member_data.get("roles", [])
                    print(f"User {user_data.get('id')} roles: {user_roles}")

                    # 許可されたロールを持っているかチェック
                    has_allowed_role = any(role in allowed_roles for role in user_roles)

                    if not has_allowed_role:
                        print(
                            f"User {user_data.get('id')} does not have any allowed roles. "
                            f"User roles: {user_roles}, Allowed: {allowed_roles}"
                        )
                        return {
                            "statusCode": 302,
                            "headers": {
                                **cors_headers,
                                "Location": f"{FRONTEND_URL}/login?error=no_role",
                            },
                            "body": "",
                        }

        # セッション作成
        session_id = secrets.token_urlsafe(32)
        expires_at = int(time.time()) + SESSION_TTL

        # アバターURL構築
        print(f"Discord user_data: {user_data}")
        avatar_url = None
        if user_data.get("avatar"):
            avatar_url = f"https://cdn.discordapp.com/avatars/{user_data['id']}/{user_data['avatar']}.png"
            print(f"Avatar URL: {avatar_url}")

        session_item = {
            "sessionId": session_id,
            "discordUserId": user_data["id"],
            "discordUsername": user_data.get("username", ""),
            "discordGlobalName": user_data.get("global_name", ""),
            "discordAvatar": avatar_url,
            "createdAt": int(time.time()),
            "expiresAt": expires_at,
        }

        sessions_table.put_item(Item=session_item)

        # Cookie設定してリダイレクト
        return {
            "statusCode": 302,
            "headers": {
                **cors_headers,
                "Location": FRONTEND_URL,
                "Set-Cookie": set_cookie_header("session_id", session_id),
            },
            "body": "",
        }

    except Exception as e:
        print(f"Error in handle_discord_callback: {e}")
        import traceback

        traceback.print_exc()
        return {
            "statusCode": 302,
            "headers": get_cors_headers(),
            "body": "",
        }


def handle_auth_me(event, context):
    """
    現在のユーザー情報取得

    セッションCookieから現在ログイン中のユーザー情報を返す
    """
    try:
        origin = event.get("headers", {}).get("origin") or event.get("headers", {}).get("Origin")
        cors_headers = get_cors_headers(origin)

        # OPTIONSリクエスト
        http_method = event.get("requestContext", {}).get("http", {}).get("method")
        if http_method == "OPTIONS":
            return {"statusCode": 200, "headers": cors_headers, "body": ""}

        # セッションID取得
        session_id = get_cookie(event, "session_id")

        if not session_id:
            return {
                "statusCode": 401,
                "headers": cors_headers,
                "body": json.dumps({"error": "Not authenticated"}),
            }

        # セッション取得
        try:
            response = sessions_table.get_item(Key={"sessionId": session_id})
            session = response.get("Item")
        except Exception as e:
            print(f"Session lookup error: {e}")
            return {
                "statusCode": 401,
                "headers": cors_headers,
                "body": json.dumps({"error": "Session error"}),
            }

        if not session:
            return {
                "statusCode": 401,
                "headers": cors_headers,
                "body": json.dumps({"error": "Session not found"}),
            }

        # 有効期限チェック
        if session.get("expiresAt", 0) < int(time.time()):
            # 期限切れセッションを削除
            sessions_table.delete_item(Key={"sessionId": session_id})
            return {
                "statusCode": 401,
                "headers": cors_headers,
                "body": json.dumps({"error": "Session expired"}),
            }

        # ユーザー情報を返す
        user_info = {
            "id": session.get("discordUserId"),
            "username": session.get("discordUsername"),
            "globalName": session.get("discordGlobalName"),
            "avatar": session.get("discordAvatar"),
        }

        return {
            "statusCode": 200,
            "headers": {
                **cors_headers,
                "Content-Type": "application/json",
            },
            "body": json.dumps(user_info),
        }

    except Exception as e:
        print(f"Error in handle_auth_me: {e}")
        return {
            "statusCode": 500,
            "headers": get_cors_headers(),
            "body": json.dumps({"error": str(e)}),
        }


def handle_logout(event, context):
    """
    ログアウト処理

    セッションを削除してCookieをクリア
    """
    try:
        origin = event.get("headers", {}).get("origin") or event.get("headers", {}).get("Origin")
        cors_headers = get_cors_headers(origin)

        # OPTIONSリクエスト
        http_method = event.get("requestContext", {}).get("http", {}).get("method")
        if http_method == "OPTIONS":
            return {"statusCode": 200, "headers": cors_headers, "body": ""}

        # セッションID取得
        session_id = get_cookie(event, "session_id")

        if session_id:
            # セッション削除
            try:
                sessions_table.delete_item(Key={"sessionId": session_id})
            except Exception as e:
                print(f"Session delete error: {e}")

        # Cookieをクリア
        return {
            "statusCode": 200,
            "headers": {
                **cors_headers,
                "Content-Type": "application/json",
                "Set-Cookie": set_cookie_header("session_id", "", max_age=0),
            },
            "body": json.dumps({"success": True}),
        }

    except Exception as e:
        print(f"Error in handle_logout: {e}")
        return {
            "statusCode": 500,
            "headers": get_cors_headers(),
            "body": json.dumps({"error": str(e)}),
        }


def handle_apikey(event, context):
    """
    API Key取得

    認証済みユーザーにアップロード用のAPI Keyを返す
    """
    try:
        origin = event.get("headers", {}).get("origin") or event.get("headers", {}).get("Origin")
        cors_headers = get_cors_headers(origin)

        # OPTIONSリクエスト
        http_method = event.get("requestContext", {}).get("http", {}).get("method")
        if http_method == "OPTIONS":
            return {"statusCode": 200, "headers": cors_headers, "body": ""}

        # セッションID取得
        session_id = get_cookie(event, "session_id")

        if not session_id:
            return {
                "statusCode": 401,
                "headers": cors_headers,
                "body": json.dumps({"error": "Not authenticated"}),
            }

        # セッション取得
        try:
            response = sessions_table.get_item(Key={"sessionId": session_id})
            session = response.get("Item")
        except Exception as e:
            print(f"Session lookup error: {e}")
            return {
                "statusCode": 401,
                "headers": cors_headers,
                "body": json.dumps({"error": "Session error"}),
            }

        if not session:
            return {
                "statusCode": 401,
                "headers": cors_headers,
                "body": json.dumps({"error": "Session not found"}),
            }

        # 有効期限チェック
        if session.get("expiresAt", 0) < int(time.time()):
            sessions_table.delete_item(Key={"sessionId": session_id})
            return {
                "statusCode": 401,
                "headers": cors_headers,
                "body": json.dumps({"error": "Session expired"}),
            }

        # API Keyを返す
        return {
            "statusCode": 200,
            "headers": {
                **cors_headers,
                "Content-Type": "application/json",
            },
            "body": json.dumps(
                {
                    "apiKey": UPLOAD_API_KEY,
                    "discordUserId": session.get("discordUserId"),
                }
            ),
        }

    except Exception as e:
        print(f"Error in handle_apikey: {e}")
        return {
            "statusCode": 500,
            "headers": get_cors_headers(),
            "body": json.dumps({"error": str(e)}),
        }
