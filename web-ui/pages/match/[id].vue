<template>
  <div>
    <!-- 戻るボタン -->
    <v-btn class="mb-4" to="/">
      <v-icon left>mdi-arrow-left</v-icon>
      検索に戻る
    </v-btn>

    <!-- ローディング -->
    <v-progress-linear v-if="loading" indeterminate></v-progress-linear>

    <!-- エラー -->
    <v-alert v-if="error" type="error" class="mb-4">
      {{ error }}
    </v-alert>

    <!-- データがない -->
    <v-alert v-if="!loading && !match" type="warning" class="mb-4">
      試合データが見つかりません
    </v-alert>

    <!-- 詳細表示 -->
    <div v-if="match">
      <!-- 試合情報カード -->
      <v-card class="mb-4">
        <v-card-title class="d-flex align-center">
          <div>
            <v-chip :color="getGameTypeColor(match.gameType)" size="small" class="mr-2">
              {{ getGameTypeText(match.gameType) }}
            </v-chip>
            <v-chip :color="getWinLossColor(match.winLoss)" size="small" class="mr-2">
              {{ getWinLossText(match.winLoss) }}
            </v-chip>
            <span class="text-body-1">{{ getMapName(match.mapId) }}</span>
            <span class="text-caption text-grey ml-2">{{ formatDateTime(match.dateTime) }}</span>
          </div>
          <v-spacer></v-spacer>
          <div v-if="match.allyMainClanTag && match.enemyMainClanTag" class="text-body-2">
            <span class="text-success font-weight-bold">[{{ match.allyMainClanTag }}]</span>
            <span class="mx-2">vs</span>
            <span class="text-error font-weight-bold">[{{ match.enemyMainClanTag }}]</span>
          </div>
        </v-card-title>
        <v-card-text class="pt-0">
          <span class="text-caption text-grey">Arena ID: {{ match.arenaUniqueID }} | Ver: {{ match.clientVersion }}</span>
        </v-card-text>
      </v-card>

      <!-- 戦闘統計・動画・リプレイ提供者（MatchDetailExpansionコンポーネントを使用） -->
      <v-card v-if="matchAsRecord" class="mb-4">
        <MatchDetailExpansion :match="matchAsRecord" :is-polling="isPolling" />
      </v-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import type { MatchDetailResponse, MatchRecord } from '~/types/replay'

const route = useRoute()
const api = useApi()
const { getMapName } = useMapNames()

const loading = ref(true)
const error = ref<string | null>(null)
const match = ref<MatchDetailResponse | null>(null)

// ポーリング関連
const POLLING_INTERVAL = 5000 // 5秒
let pollingTimer: ReturnType<typeof setInterval> | null = null
const isPolling = ref(false)

// 動画が未生成かどうかをチェック
const isVideoMissing = computed(() => {
  if (!match.value?.replays) return false
  return !match.value.replays.some(r => r.mp4S3Key)
})

// MatchDetailExpansionコンポーネント用にMatchRecord型に変換
const matchAsRecord = computed<MatchRecord | null>(() => {
  if (!match.value) return null
  return {
    ...match.value,
    replayCount: match.value.replays?.length || 0,
  } as MatchRecord
})

// マッチデータをロード
const loadMatch = async () => {
  const arenaUniqueID = route.params.id as string
  if (!arenaUniqueID) return

  try {
    const data = await api.getMatchDetail(arenaUniqueID)
    if (data) {
      match.value = data
    }
  } catch (err: any) {
    console.error('Match reload error:', err)
  }
}

// ポーリング開始
const startPolling = () => {
  if (pollingTimer) return
  isPolling.value = true
  pollingTimer = setInterval(async () => {
    if (!isVideoMissing.value) {
      stopPolling()
      return
    }
    await loadMatch()
  }, POLLING_INTERVAL)
}

// ポーリング停止
const stopPolling = () => {
  if (pollingTimer) {
    clearInterval(pollingTimer)
    pollingTimer = null
  }
  isPolling.value = false
}

// match が更新されたら動画チェック
watch(match, (newMatch) => {
  if (newMatch && !isVideoMissing.value) {
    stopPolling()
  }
})

onMounted(async () => {
  const arenaUniqueID = route.params.id as string

  if (!arenaUniqueID) {
    error.value = '無効なIDです'
    loading.value = false
    return
  }

  try {
    const data = await api.getMatchDetail(arenaUniqueID)
    if (data) {
      match.value = data
      // 動画が未生成の場合はポーリング開始
      if (isVideoMissing.value) {
        startPolling()
      }
    } else {
      error.value = '試合データが見つかりません'
    }
  } catch (err: any) {
    error.value = err.message || 'データ取得エラー'
  } finally {
    loading.value = false
  }
})

onUnmounted(() => {
  stopPolling()
})

// フォーマット関数
const formatDateTime = (dateTime: string) => {
  if (!dateTime) return '-'
  // DynamoDB形式（DD.MM.YYYY HH:MM:SS）をパース
  const parts = dateTime.match(/(\d{2})\.(\d{2})\.(\d{4}) (\d{2}):(\d{2}):(\d{2})/)
  if (parts) {
    const [_, day, month, year, hour, minute] = parts
    return `${year}/${month}/${day} ${hour}:${minute}`
  }
  // ISO形式の場合
  try {
    const date = new Date(dateTime)
    if (!isNaN(date.getTime())) {
      return date.toLocaleString('ja-JP')
    }
  } catch (e) {
    // パース失敗時はそのまま返す
  }
  return dateTime
}

const getGameTypeText = (type: string) => {
  const types: Record<string, string> = {
    clan: 'クラン戦',
    pvp: 'ランダム',
    ranked: 'ランク戦',
  }
  return types[type] || type
}

const getGameTypeColor = (type: string) => {
  const colors: Record<string, string> = {
    clan: 'purple',
    pvp: 'blue',
    ranked: 'orange',
  }
  return colors[type] || 'grey'
}

const getWinLossText = (winLoss?: string) => {
  const texts: Record<string, string> = {
    win: '勝利',
    loss: '敗北',
    draw: '引き分け',
    unknown: '不明',
  }
  return texts[winLoss || 'unknown'] || '-'
}

const getWinLossColor = (winLoss?: string) => {
  const colors: Record<string, string> = {
    win: 'success',
    loss: 'error',
    draw: 'warning',
    unknown: 'grey',
  }
  return colors[winLoss || 'unknown'] || 'grey'
}
</script>
