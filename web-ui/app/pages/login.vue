<template>
  <v-container class="fill-height" fluid>
    <v-row align="center" justify="center">
      <v-col cols="12" sm="8" md="6" lg="4">
        <v-card class="elevation-12">
          <v-card-title class="text-h5 text-center pa-6 bg-primary">
            <v-icon icon="mdi-ship-wheel" size="large" class="mr-2"></v-icon>
            WoWS Replay Database
          </v-card-title>

          <v-card-text class="pa-6">
            <p class="text-body-1 text-center mb-6">
              リプレイデータベースにアクセスするには、Discordでログインしてください。
            </p>

            <v-alert
              v-if="errorMessage"
              type="error"
              variant="tonal"
              class="mb-4"
            >
              {{ errorMessage }}
            </v-alert>

            <v-btn
              color="#5865F2"
              size="large"
              block
              @click="loginWithDiscord"
              :loading="auth.isLoading"
            >
              <v-icon icon="mdi-discord" class="mr-2"></v-icon>
              Discordでログイン
            </v-btn>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup lang="ts">
const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const errorMessage = computed(() => {
  const error = route.query.error as string | undefined
  if (error) {
    const errorMessages: Record<string, string> = {
      missing_params: '認証パラメータが不足しています',
      invalid_state: '認証セッションが無効です。もう一度お試しください',
      state_error: '認証エラーが発生しました',
      token_error: 'アクセストークンの取得に失敗しました',
      no_token: 'アクセストークンが取得できませんでした',
      user_error: 'ユーザー情報の取得に失敗しました',
      guilds_error: 'サーバー情報の取得に失敗しました',
      not_member: '許可されたDiscordサーバーのメンバーではありません',
      access_denied: 'アクセスが拒否されました',
    }
    return errorMessages[error] || `認証エラー: ${error}`
  }
  return auth.error
})

const loginWithDiscord = () => {
  auth.loginWithDiscord()
}

// すでにログインしている場合はトップページへリダイレクト
onMounted(async () => {
  await auth.fetchUser()
  if (auth.isAuthenticated) {
    router.push('/')
  }
})

// ページレイアウト（ヘッダー・フッターなし）
definePageMeta({
  layout: false,
})
</script>
