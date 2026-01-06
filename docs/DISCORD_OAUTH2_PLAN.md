# Discord OAuth2 認証実装計画

## 概要

現在のBasic認証をDiscord OAuth2認証に置き換え、Discordアカウントでログインできるようにする。

## 現状

- **フロントエンド**: Nuxt 3 (SPA) on CloudFront + S3
- **バックエンド**: API Gateway + Lambda
- **認証**: Basic認証 (CloudFront Functions)
- **Discord App ID**: `1457057871664648364`

## 目標構成

```
User → CloudFront → S3 (SPA)
         ↓
    /api/auth/* → API Gateway → Lambda (Auth)
         ↓
    DynamoDB (Sessions)
         ↓
    Discord OAuth2 API
```

## Discord OAuth2 フロー

```
1. ユーザー: 「Discordでログイン」クリック
         ↓
2. フロントエンド: /api/auth/discord にリダイレクト
         ↓
3. Lambda: Discord認証URL生成 → Discord認証ページにリダイレクト
         ↓
4. ユーザー: Discordで認可
         ↓
5. Discord: callback URLに authorization code を付けてリダイレクト
         ↓
6. Lambda (callback):
   - code を access_token に交換
   - Discord APIでユーザー情報取得
   - セッション作成 (DynamoDB)
   - Set-Cookie でセッションID設定
   - フロントエンドにリダイレクト
         ↓
7. フロントエンド: セッションCookieで認証済み
```

## 必要なコンポーネント

### 1. バックエンド (Lambda)

#### 新規API エンドポイント

| メソッド | パス | 説明 |
|---------|------|------|
| GET | `/api/auth/discord` | Discord認証開始（リダイレクト） |
| GET | `/api/auth/discord/callback` | コールバック処理 |
| GET | `/api/auth/me` | 現在のユーザー情報取得 |
| POST | `/api/auth/logout` | ログアウト |

#### 認証ハンドラー実装 (`src/handlers/api/auth.py`)

```python
# /api/auth/discord
def handle_discord_auth(event, context):
    """Discord OAuth2認証開始"""
    state = generate_random_state()
    # stateをDynamoDBに保存（CSRF対策）

    auth_url = (
        f"https://discord.com/api/oauth2/authorize"
        f"?client_id={DISCORD_CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=identify"
        f"&state={state}"
    )
    return redirect(auth_url)

# /api/auth/discord/callback
def handle_discord_callback(event, context):
    """Discord OAuth2コールバック"""
    code = event['queryStringParameters']['code']
    state = event['queryStringParameters']['state']

    # state検証
    # code → access_token交換
    # Discord APIでユーザー情報取得
    # セッション作成
    # Set-Cookie + リダイレクト

# /api/auth/me
def handle_auth_me(event, context):
    """現在のユーザー情報取得"""
    session_id = get_cookie(event, 'session_id')
    user = get_session_user(session_id)
    return user or 401

# /api/auth/logout
def handle_logout(event, context):
    """ログアウト"""
    session_id = get_cookie(event, 'session_id')
    delete_session(session_id)
    # Clear-Cookie
```

### 2. DynamoDB テーブル

#### セッションテーブル (`wows-sessions-{stage}`)

| 属性 | 型 | 説明 |
|------|------|------|
| sessionId | S (PK) | セッションID (UUID) |
| discordUserId | S | Discord ユーザーID |
| discordUsername | S | Discord ユーザー名 |
| discordAvatar | S | アバターURL |
| createdAt | S | 作成日時 |
| expiresAt | N | 有効期限 (TTL) |

```yaml
# serverless.yml に追加
SessionsTable:
  Type: AWS::DynamoDB::Table
  Properties:
    TableName: wows-sessions-${self:provider.stage}
    BillingMode: PAY_PER_REQUEST
    AttributeDefinitions:
      - AttributeName: sessionId
        AttributeType: S
    KeySchema:
      - AttributeName: sessionId
        KeyType: HASH
    TimeToLiveSpecification:
      AttributeName: expiresAt
      Enabled: true
```

### 3. フロントエンド (Nuxt)

#### 認証ストア (`stores/auth.ts`)

```typescript
export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null as User | null,
    isAuthenticated: false,
    isLoading: true,
  }),
  actions: {
    async fetchUser() {
      try {
        const response = await $fetch('/api/auth/me')
        this.user = response
        this.isAuthenticated = true
      } catch {
        this.user = null
        this.isAuthenticated = false
      } finally {
        this.isLoading = false
      }
    },
    loginWithDiscord() {
      window.location.href = '/api/auth/discord'
    },
    async logout() {
      await $fetch('/api/auth/logout', { method: 'POST' })
      this.user = null
      this.isAuthenticated = false
    }
  }
})
```

#### 認証ミドルウェア (`middleware/auth.ts`)

```typescript
export default defineNuxtRouteMiddleware(async (to) => {
  const auth = useAuthStore()

  if (auth.isLoading) {
    await auth.fetchUser()
  }

  if (!auth.isAuthenticated) {
    return navigateTo('/login')
  }
})
```

#### ログインページ (`pages/login.vue`)

```vue
<template>
  <v-container>
    <v-card>
      <v-card-title>WoWS Replay Database</v-card-title>
      <v-card-text>
        リプレイデータベースにアクセスするには、Discordでログインしてください。
      </v-card-text>
      <v-card-actions>
        <v-btn color="primary" @click="loginWithDiscord">
          <v-icon left>mdi-discord</v-icon>
          Discordでログイン
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-container>
</template>
```

### 4. CloudFront 設定変更

#### Basic認証の削除

1. CloudFront Function (`wows-replay-basic-auth`) をdistributionから解除
2. `/api/auth/*` パスを追加

#### 新しいキャッシュビヘイビア

| パス | オリジン | キャッシュ | 認証 |
|------|---------|-----------|------|
| `/api/auth/*` | API Gateway | 無効 | なし |
| `/api/*` | API Gateway | 無効 | なし |
| `/*` | S3 | 有効 | なし |

### 5. Discord Developer Portal 設定

1. [Discord Developer Portal](https://discord.com/developers/applications) にアクセス
2. アプリケーション `1457057871664648364` を選択
3. OAuth2 > Redirects に追加:
   - `https://wows-replay.mirage0926.com/api/auth/discord/callback`
4. OAuth2 > Scopes で `identify` を有効化

## 環境変数

```bash
# deploy/.env に追加
DISCORD_CLIENT_SECRET=<Discord OAuth2 Client Secret>
SESSION_SECRET=<セッション署名用シークレット>
FRONTEND_URL=https://wows-replay.mirage0926.com
```

## 実装ステップ

### Phase 1: バックエンド準備

1. [ ] DynamoDB セッションテーブル作成
2. [ ] Discord Developer Portalで Redirect URI設定
3. [ ] DISCORD_CLIENT_SECRET取得・設定
4. [ ] 認証Lambda関数実装 (`src/handlers/api/auth.py`)
5. [ ] serverless.yml に認証API追加
6. [ ] デプロイ・テスト

### Phase 2: フロントエンド実装

1. [ ] 認証ストア作成 (`stores/auth.ts`)
2. [ ] ログインページ作成 (`pages/login.vue`)
3. [ ] 認証ミドルウェア作成 (`middleware/auth.ts`)
4. [ ] ヘッダーにユーザー情報・ログアウトボタン追加
5. [ ] ページ保護設定

### Phase 3: CloudFront移行

1. [ ] Basic認証を一時的に無効化
2. [ ] `/api/auth/*` パスのキャッシュビヘイビア追加
3. [ ] 動作確認
4. [ ] Basic認証完全削除

### Phase 4: テスト・リリース

1. [ ] ログインフロー確認
2. [ ] ログアウト確認
3. [ ] セッション有効期限確認
4. [ ] エラーハンドリング確認

## セキュリティ考慮事項

1. **CSRF対策**: OAuth2 stateパラメータ使用
2. **セッション管理**: HttpOnly, Secure, SameSite=Lax Cookie
3. **セッション有効期限**: 24時間（DynamoDB TTL）
4. **HTTPS強制**: CloudFrontでリダイレクト
5. **Client Secret保護**: 環境変数で管理、フロントエンドに露出しない

## 認可（将来拡張）

現在は認証のみ。将来的に以下を追加可能：

- 特定Discordサーバーのメンバーのみアクセス許可
- ロールベースのアクセス制御
- アップロード権限の制限
