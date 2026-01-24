<template>
  <v-app>
    <!-- ナビゲーションドロワー -->
    <v-navigation-drawer v-model="drawer" temporary>
      <v-list density="compact" nav>
        <v-list-item
          prepend-icon="mdi-home"
          title="ホーム"
          to="/"
        ></v-list-item>

        <v-divider class="my-2"></v-divider>

        <v-list-subheader>ツール</v-list-subheader>

        <v-list-item
          prepend-icon="mdi-download"
          title="自動アップローダー"
          subtitle="リプレイを自動でアップロード"
          :loading="isDownloading"
          @click="downloadUploader"
        ></v-list-item>

        <v-list-item
          v-if="auth.isAuthenticated"
          prepend-icon="mdi-key"
          title="API Key"
          subtitle="アップローダー用のAPI Key"
          :loading="isLoadingApiKey"
          @click="showApiKeyDialog"
        ></v-list-item>

        <v-list-item
          prepend-icon="mdi-help-circle-outline"
          title="セットアップガイド"
          subtitle="自動アップローダーの使い方"
          @click="setupGuideDialog = true"
        ></v-list-item>

        <v-divider class="my-2"></v-divider>

        <v-list-subheader>リンク</v-list-subheader>

        <v-list-item
          prepend-icon="mdi-github"
          title="GitHub"
          href="https://github.com/aharada2021/WoWS-Replay-Classification-Bot"
          target="_blank"
        ></v-list-item>
      </v-list>
    </v-navigation-drawer>

    <!-- API Key ダイアログ -->
    <v-dialog v-model="apiKeyDialog" max-width="500">
      <v-card>
        <v-card-title class="text-h6">
          <v-icon start>mdi-key</v-icon>
          自動アップローダー設定
        </v-card-title>
        <v-card-text>
          <p class="text-body-2 mb-3">
            自動アップローダーのセットアップ時に入力する情報です。他の人には共有しないでください。
          </p>
          <v-text-field
            v-model="serverUrl"
            label="サーバーURL"
            readonly
            variant="outlined"
            density="compact"
          >
            <template v-slot:append>
              <v-btn
                icon="mdi-content-copy"
                variant="text"
                size="small"
                @click="copyServerUrl"
              ></v-btn>
            </template>
          </v-text-field>
          <v-text-field
            v-model="apiKeyData.apiKey"
            label="API Key"
            readonly
            variant="outlined"
            density="compact"
            :append-inner-icon="showApiKey ? 'mdi-eye-off' : 'mdi-eye'"
            :type="showApiKey ? 'text' : 'password'"
            @click:append-inner="showApiKey = !showApiKey"
          >
            <template v-slot:append>
              <v-btn
                icon="mdi-content-copy"
                variant="text"
                size="small"
                @click="copyApiKey"
              ></v-btn>
            </template>
          </v-text-field>
          <v-text-field
            v-model="apiKeyData.discordUserId"
            label="Discord User ID (オプション)"
            readonly
            variant="outlined"
            density="compact"
          >
            <template v-slot:append>
              <v-btn
                icon="mdi-content-copy"
                variant="text"
                size="small"
                @click="copyDiscordUserId"
              ></v-btn>
            </template>
          </v-text-field>
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn color="primary" variant="text" @click="apiKeyDialog = false">
            閉じる
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- セットアップガイドダイアログ -->
    <v-dialog v-model="setupGuideDialog" max-width="600">
      <v-card>
        <v-card-title class="text-h6">
          <v-icon start>mdi-help-circle-outline</v-icon>
          自動アップローダー セットアップガイド
        </v-card-title>
        <v-card-text>
          <v-stepper :model-value="1" alt-labels non-linear>
            <v-stepper-header>
              <v-stepper-item title="ダウンロード" value="1" complete></v-stepper-item>
              <v-divider></v-divider>
              <v-stepper-item title="設定情報取得" value="2"></v-stepper-item>
              <v-divider></v-divider>
              <v-stepper-item title="初回起動" value="3"></v-stepper-item>
            </v-stepper-header>
          </v-stepper>

          <div class="mt-4">
            <h4 class="text-subtitle-1 font-weight-bold mb-2">ステップ 1: ダウンロード</h4>
            <p class="text-body-2 mb-3">
              このメニューの「自動アップローダー」をクリックしてダウンロードしてください。
            </p>

            <h4 class="text-subtitle-1 font-weight-bold mb-2">ステップ 2: 設定情報取得</h4>
            <p class="text-body-2 mb-3">
              Discordでログイン後、このメニューの「API Key」をクリックして以下の情報をメモしてください:
            </p>
            <ul class="text-body-2 mb-3">
              <li><strong>サーバーURL</strong> - 接続先サーバーのURL</li>
              <li><strong>API Key</strong> - 認証用のキー</li>
              <li><strong>Discord User ID</strong> - オプション（アップロード者を識別）</li>
            </ul>

            <h4 class="text-subtitle-1 font-weight-bold mb-2">ステップ 3: 初回起動</h4>
            <ol class="text-body-2 mb-3">
              <li>ダウンロードしたzipファイルを展開</li>
              <li><code>wows_replay_uploader.exe</code> をダブルクリックして起動</li>
              <li>セットアップウィザードで<strong>サーバーURL</strong>を入力</li>
              <li><strong>API Key</strong>を入力</li>
              <li>リプレイフォルダは自動検出されるのでそのままEnter</li>
              <li>Discord User IDを入力（オプション）</li>
              <li>スタートアップ登録で「Y」を選択するとPC起動時に自動起動</li>
            </ol>

            <v-alert type="success" variant="tonal" density="compact" class="mb-3">
              <strong>完了!</strong> これでWorld of Warshipsで試合が終わるたびに、リプレイが自動でアップロードされます。
            </v-alert>

            <v-alert type="info" variant="tonal" density="compact">
              <strong>困ったときは:</strong>
              問題が発生した場合は、Discordサーバーでお問い合わせください。
            </v-alert>
          </div>
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn color="primary" variant="text" @click="setupGuideDialog = false">
            閉じる
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- コピー成功スナックバー -->
    <v-snackbar v-model="copySnackbar" :timeout="2000" color="success">
      クリップボードにコピーしました
    </v-snackbar>

    <v-app-bar v-if="showAppBar" color="primary" density="compact" height="48">
      <v-app-bar-nav-icon size="small" @click="drawer = !drawer"></v-app-bar-nav-icon>
      <v-toolbar-title class="text-body-1 cursor-pointer" @click="router.push('/')">WoWS Replay Database</v-toolbar-title>
      <v-spacer></v-spacer>

      <!-- ユーザーメニュー -->
      <template v-if="auth.isAuthenticated && auth.user">
        <v-menu offset-y>
          <template v-slot:activator="{ props }">
            <v-btn v-bind="props" variant="text" class="text-none" size="small">
              <v-avatar size="24" class="mr-1">
                <v-img v-if="auth.user.avatar" :src="auth.user.avatar" :alt="auth.displayName"></v-img>
                <v-icon v-else size="small">mdi-account-circle</v-icon>
              </v-avatar>
              <span class="d-none d-sm-inline text-caption">{{ auth.displayName }}</span>
              <v-icon end size="small">mdi-menu-down</v-icon>
            </v-btn>
          </template>
          <v-list density="compact">
            <v-list-item>
              <v-list-item-title class="text-caption text-grey">
                {{ auth.user.username }}
              </v-list-item-title>
            </v-list-item>
            <v-divider></v-divider>
            <v-list-item @click="handleLogout">
              <template v-slot:prepend>
                <v-icon size="small">mdi-logout</v-icon>
              </template>
              <v-list-item-title class="text-body-2">ログアウト</v-list-item-title>
            </v-list-item>
          </v-list>
        </v-menu>
      </template>
    </v-app-bar>

    <v-main>
      <v-container fluid class="pa-2">
        <NuxtPage />
      </v-container>
    </v-main>

    <v-footer v-if="showAppBar" app class="py-1">
      <v-spacer></v-spacer>
      <span class="text-caption">&copy; 2026 WoWS Replay Bot</span>
    </v-footer>
  </v-app>
</template>

<script setup lang="ts">
const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const config = useRuntimeConfig()

// ナビゲーションドロワーの状態
const drawer = ref(false)

// ダウンロード状態
const isDownloading = ref(false)

// API Key関連の状態
const isLoadingApiKey = ref(false)
const apiKeyDialog = ref(false)
const showApiKey = ref(false)
const copySnackbar = ref(false)
const apiKeyData = ref({
  apiKey: '',
  discordUserId: ''
})

// セットアップガイドダイアログ
const setupGuideDialog = ref(false)

// サーバーURLを取得（apiBaseUrlから）
const serverUrl = computed(() => {
  const baseUrl = config.public.apiBaseUrl
  return baseUrl || window.location.origin
})

// ログインページではヘッダー・フッターを非表示
const showAppBar = computed(() => route.path !== '/login')

// 初回マウント時にユーザー情報を取得
onMounted(async () => {
  if (auth.isLoading) {
    await auth.fetchUser()
  }
})

const handleLogout = async () => {
  await auth.logout()
  router.push('/login')
}

// アップローダーのダウンロード
const downloadUploader = async () => {
  if (isDownloading.value) return

  isDownloading.value = true
  try {
    const response = await fetch(`${config.public.apiBaseUrl}/api/download?file=uploader`)
    if (!response.ok) {
      throw new Error('ダウンロードURLの取得に失敗しました')
    }
    const data = await response.json()

    // 署名付きURLでダウンロードを開始
    window.location.href = data.url
  } catch (error) {
    console.error('ダウンロードエラー:', error)
    alert('ダウンロードに失敗しました。しばらく待ってから再度お試しください。')
  } finally {
    isDownloading.value = false
  }
}

// API Key表示ダイアログを開く
const showApiKeyDialog = async () => {
  if (isLoadingApiKey.value) return

  isLoadingApiKey.value = true
  try {
    const response = await fetch(`${config.public.apiBaseUrl}/api/auth/apikey`, {
      credentials: 'include'
    })
    if (!response.ok) {
      throw new Error('API Keyの取得に失敗しました')
    }
    const data = await response.json()
    apiKeyData.value = {
      apiKey: data.apiKey || '',
      discordUserId: data.discordUserId || ''
    }
    showApiKey.value = false
    apiKeyDialog.value = true
  } catch (error) {
    console.error('API Key取得エラー:', error)
    alert('API Keyの取得に失敗しました。再度ログインしてください。')
  } finally {
    isLoadingApiKey.value = false
  }
}

// サーバーURLをクリップボードにコピー
const copyServerUrl = async () => {
  try {
    await navigator.clipboard.writeText(serverUrl.value)
    copySnackbar.value = true
  } catch (error) {
    console.error('コピーエラー:', error)
  }
}

// API Keyをクリップボードにコピー
const copyApiKey = async () => {
  try {
    await navigator.clipboard.writeText(apiKeyData.value.apiKey)
    copySnackbar.value = true
  } catch (error) {
    console.error('コピーエラー:', error)
  }
}

// Discord User IDをクリップボードにコピー
const copyDiscordUserId = async () => {
  try {
    await navigator.clipboard.writeText(apiKeyData.value.discordUserId)
    copySnackbar.value = true
  } catch (error) {
    console.error('コピーエラー:', error)
  }
}
</script>

<style scoped>
.cursor-pointer {
  cursor: pointer;
}
</style>
