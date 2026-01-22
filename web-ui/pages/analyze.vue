<template>
  <div>
    <!-- ログインしていない場合 -->
    <v-alert v-if="!authStore.isLoading && !authStore.isAuthenticated" type="info" class="mb-4">
      <div class="d-flex align-center">
        <span>データ分析機能を使用するにはログインが必要です。</span>
        <v-btn class="ml-4" color="primary" size="small" @click="authStore.loginWithDiscord">
          <v-icon start>mdi-discord</v-icon>
          ログイン
        </v-btn>
      </div>
    </v-alert>

    <!-- メインコンテンツ -->
    <v-card v-else class="mb-4">
      <v-card-title class="d-flex align-center">
        <v-icon start>mdi-brain</v-icon>
        データ分析 (Claude AI)
      </v-card-title>

      <v-card-text>
        <!-- 質問入力フォーム -->
        <v-form @submit.prevent="handleAnalyze">
          <v-row dense>
            <v-col cols="12">
              <v-textarea
                v-model="analysisStore.query"
                label="質問を入力"
                placeholder="例: 最近の負けパターンは？ / クラン戦の勝率が低い原因は？ / 改善点を教えて"
                rows="2"
                :counter="500"
                :maxlength="500"
                :disabled="analysisStore.loading"
                hide-details="auto"
              ></v-textarea>
            </v-col>
          </v-row>

          <!-- フィルター -->
          <v-row dense class="mt-2">
            <v-col cols="12" sm="4">
              <v-select
                v-model="analysisStore.gameType"
                :items="gameTypes"
                label="ゲームタイプ"
                clearable
                density="compact"
                hide-details
                item-title="text"
                item-value="value"
              ></v-select>
            </v-col>
            <v-col cols="6" sm="3">
              <v-text-field
                v-model="analysisStore.dateFrom"
                label="From"
                clearable
                density="compact"
                hide-details
                type="date"
              ></v-text-field>
            </v-col>
            <v-col cols="6" sm="3">
              <v-text-field
                v-model="analysisStore.dateTo"
                label="To"
                clearable
                density="compact"
                hide-details
                type="date"
              ></v-text-field>
            </v-col>
            <v-col cols="12" sm="2" class="d-flex align-center">
              <v-btn
                color="primary"
                type="submit"
                :loading="analysisStore.loading"
                :disabled="!analysisStore.query.trim()"
                block
              >
                <v-icon start>mdi-magnify</v-icon>
                分析
              </v-btn>
            </v-col>
          </v-row>
        </v-form>

        <!-- エラー表示 -->
        <v-alert
          v-if="analysisStore.error"
          type="error"
          class="mt-4"
          closable
          @click:close="analysisStore.error = null"
        >
          {{ analysisStore.error }}
        </v-alert>

        <!-- 残りクエリ数 -->
        <div v-if="analysisStore.response" class="mt-2 text-caption text-grey">
          残りクエリ: {{ analysisStore.response.remainingQueries }}/5 (本日)
          <span class="ml-2">
            使用トークン: {{ analysisStore.response.tokensUsed.toLocaleString() }}
          </span>
        </div>
      </v-card-text>
    </v-card>

    <!-- 分析結果 -->
    <v-card v-if="analysisStore.hasResponse" class="mb-4">
      <v-card-title class="d-flex align-center">
        <v-icon start>mdi-file-document-outline</v-icon>
        分析結果
        <v-spacer></v-spacer>
        <v-chip size="small" class="ml-2">
          {{ analysisStore.response?.dataUsed.totalBattles }}試合を分析
        </v-chip>
      </v-card-title>

      <v-card-text>
        <div class="analysis-result markdown-body" v-html="renderedAnalysis"></div>
      </v-card-text>
    </v-card>

    <!-- ローディング -->
    <v-card v-if="analysisStore.loading" class="mb-4">
      <v-card-text class="text-center py-8">
        <v-progress-circular indeterminate color="primary" size="48"></v-progress-circular>
        <div class="mt-4 text-subtitle-1">データを分析中...</div>
        <div class="text-caption text-grey">数秒かかる場合があります</div>
      </v-card-text>
    </v-card>

    <!-- 履歴 -->
    <v-card v-if="analysisStore.hasHistory">
      <v-card-title class="d-flex align-center">
        <v-icon start>mdi-history</v-icon>
        履歴
        <v-spacer></v-spacer>
        <v-btn size="small" variant="text" @click="analysisStore.clearHistory">
          <v-icon start>mdi-delete</v-icon>
          クリア
        </v-btn>
      </v-card-title>

      <v-list density="compact">
        <v-list-item
          v-for="(item, index) in analysisStore.history"
          :key="index"
          @click="handleRestoreHistory(item)"
          :class="{ 'bg-grey-lighten-4': analysisStore.query === item.query }"
        >
          <v-list-item-title class="text-truncate">
            {{ item.query }}
          </v-list-item-title>
          <v-list-item-subtitle>
            {{ formatTimestamp(item.timestamp) }}
          </v-list-item-subtitle>
        </v-list-item>
      </v-list>
    </v-card>

    <!-- 使い方ガイド -->
    <v-card v-if="!analysisStore.hasResponse && !analysisStore.loading" class="mb-4">
      <v-card-title>
        <v-icon start>mdi-help-circle-outline</v-icon>
        使い方
      </v-card-title>
      <v-card-text>
        <v-list density="compact">
          <v-list-item>
            <v-list-item-title>質問の例:</v-list-item-title>
          </v-list-item>
          <v-list-item>
            <template #prepend>
              <v-icon size="small" class="mr-2">mdi-chevron-right</v-icon>
            </template>
            <v-list-item-title>「最近の負けパターンは？」</v-list-item-title>
          </v-list-item>
          <v-list-item>
            <template #prepend>
              <v-icon size="small" class="mr-2">mdi-chevron-right</v-icon>
            </template>
            <v-list-item-title>「勝率が高い艦艇は？」</v-list-item-title>
          </v-list-item>
          <v-list-item>
            <template #prepend>
              <v-icon size="small" class="mr-2">mdi-chevron-right</v-icon>
            </template>
            <v-list-item-title>「ダメージを上げるにはどうしたらいい？」</v-list-item-title>
          </v-list-item>
          <v-list-item>
            <template #prepend>
              <v-icon size="small" class="mr-2">mdi-chevron-right</v-icon>
            </template>
            <v-list-item-title>「苦手なマップはある？」</v-list-item-title>
          </v-list-item>
        </v-list>

        <v-divider class="my-2"></v-divider>

        <v-alert type="info" density="compact" variant="tonal">
          <div class="text-caption">
            <strong>制限:</strong> 1日5クエリまで / クエリ間30秒のクールダウン
          </div>
        </v-alert>
      </v-card-text>
    </v-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { useAuthStore } from '~/stores/auth'
import { useAnalysisStore } from '~/stores/analysis'
import type { AnalysisHistoryItem } from '~/types/replay'

// Stores
const authStore = useAuthStore()
const analysisStore = useAnalysisStore()

// ゲームタイプ選択肢
const gameTypes = [
  { text: '全て', value: '' },
  { text: 'クラン戦', value: 'clan' },
  { text: 'ランク戦', value: 'ranked' },
  { text: 'ランダム戦', value: 'random' },
]

// Markdown レンダリング
const renderedAnalysis = computed(() => {
  if (!analysisStore.response?.analysis) return ''
  const rawHtml = marked.parse(analysisStore.response.analysis) as string
  return DOMPurify.sanitize(rawHtml)
})

// タイムスタンプをフォーマット
const formatTimestamp = (timestamp: string) => {
  const date = new Date(timestamp)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)

  if (diffMins < 1) return 'たった今'
  if (diffMins < 60) return `${diffMins}分前`

  const diffHours = Math.floor(diffMins / 60)
  if (diffHours < 24) return `${diffHours}時間前`

  const diffDays = Math.floor(diffHours / 24)
  return `${diffDays}日前`
}

// 分析実行
const handleAnalyze = () => {
  analysisStore.analyze()
}

// 履歴から復元
const handleRestoreHistory = (item: AnalysisHistoryItem) => {
  analysisStore.restoreFromHistory(item)
}

// 初期化
onMounted(() => {
  // 認証状態を取得
  if (!authStore.user && !authStore.isLoading) {
    authStore.fetchUser()
  }

  // 履歴をローカルストレージから読み込み
  analysisStore.loadHistoryFromStorage()
})
</script>

<style scoped>
.analysis-result {
  line-height: 1.8;
}

.analysis-result :deep(h2) {
  font-size: 1.25rem;
  font-weight: 600;
  margin-top: 1.5rem;
  margin-bottom: 0.75rem;
  border-bottom: 1px solid rgba(0, 0, 0, 0.12);
  padding-bottom: 0.5rem;
}

.analysis-result :deep(h3) {
  font-size: 1.1rem;
  font-weight: 600;
  margin-top: 1.25rem;
  margin-bottom: 0.5rem;
}

.analysis-result :deep(ul),
.analysis-result :deep(ol) {
  margin-left: 1.5rem;
  margin-bottom: 1rem;
}

.analysis-result :deep(li) {
  margin-bottom: 0.25rem;
}

.analysis-result :deep(p) {
  margin-bottom: 1rem;
}

.analysis-result :deep(strong) {
  font-weight: 600;
}

.analysis-result :deep(code) {
  background-color: rgba(0, 0, 0, 0.05);
  padding: 0.125rem 0.25rem;
  border-radius: 4px;
  font-size: 0.9em;
}
</style>
