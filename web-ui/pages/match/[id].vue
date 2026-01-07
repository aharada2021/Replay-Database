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
        <v-card-title>試合情報</v-card-title>
        <v-card-text>
          <v-row>
            <v-col cols="12" md="6">
              <div class="mb-2">
                <strong>日時:</strong> {{ formatDateTime(match.dateTime) }}
              </div>
              <div class="mb-2">
                <strong>マップ:</strong> {{ match.mapDisplayName }}
              </div>
              <div class="mb-2">
                <strong>ゲームタイプ:</strong>
                <v-chip :color="getGameTypeColor(match.gameType)" size="small" class="ml-2">
                  {{ getGameTypeText(match.gameType) }}
                </v-chip>
              </div>
              <div class="mb-2">
                <strong>勝敗:</strong>
                <v-chip :color="getWinLossColor(match.winLoss)" size="small" class="ml-2">
                  {{ getWinLossText(match.winLoss) }}
                </v-chip>
              </div>
            </v-col>
            <v-col cols="12" md="6">
              <div class="mb-2">
                <strong>Arena ID:</strong> {{ match.arenaUniqueID }}
              </div>
              <div class="mb-2">
                <strong>クライアントバージョン:</strong> {{ match.clientVersion }}
              </div>
              <div class="mb-2">
                <strong>リプレイ提供数:</strong> {{ match.replays.length }} 件
              </div>
            </v-col>
          </v-row>
        </v-card-text>
      </v-card>

      <!-- リプレイ提供者カード -->
      <v-card class="mb-4">
        <v-card-title>リプレイ提供者</v-card-title>
        <v-card-text>
          <v-list>
            <v-list-item
              v-for="(replay, index) in match.replays"
              :key="index"
              :active="selectedReplayIndex === index"
              @click="selectReplay(index)"
              class="mb-2"
            >
              <template v-slot:prepend>
                <v-avatar color="primary">
                  <v-icon v-if="replay.mp4S3Key">mdi-video</v-icon>
                  <v-icon v-else>mdi-account</v-icon>
                </v-avatar>
              </template>

              <v-list-item-title>
                <span v-if="replay.ownPlayer?.clanTag" class="text-primary font-weight-bold">
                  [{{ replay.ownPlayer.clanTag }}]
                </span>
                {{ replay.playerName }}
                <v-chip v-if="replay.mp4S3Key" size="x-small" color="success" class="ml-2">
                  動画あり
                </v-chip>
              </v-list-item-title>

              <v-list-item-subtitle>
                アップロード: {{ formatDateTime(replay.uploadedAt) }} by {{ replay.uploadedBy }}
                <br>
                船: {{ replay.ownPlayer?.shipName || '-' }}
              </v-list-item-subtitle>

              <template v-slot:append>
                <v-btn
                  size="small"
                  variant="outlined"
                  @click.stop="downloadReplay(replay.s3Key)"
                >
                  <v-icon>mdi-download</v-icon>
                </v-btn>
              </template>
            </v-list-item>
          </v-list>
        </v-card-text>
      </v-card>

      <!-- プレイヤー一覧 -->
      <v-card class="mb-4">
        <v-card-title>プレイヤー一覧</v-card-title>
        <v-card-text>
          <v-row>
            <!-- 自分 -->
            <v-col cols="12" md="4">
              <h3 class="mb-2">自分</h3>
              <v-list density="compact">
                <v-list-item>
                  <v-list-item-title>
                    <span v-if="match.ownPlayer.clanTag" class="text-primary font-weight-bold">
                      [{{ match.ownPlayer.clanTag }}]
                    </span>
                    {{ match.ownPlayer.name }}
                  </v-list-item-title>
                  <v-list-item-subtitle>
                    {{ match.ownPlayer.shipName }}
                  </v-list-item-subtitle>
                </v-list-item>
              </v-list>
            </v-col>

            <!-- 味方 -->
            <v-col cols="12" md="4">
              <h3 class="mb-2">味方 ({{ match.allies.length }}名)</h3>
              <v-list density="compact">
                <v-list-item v-for="(player, idx) in match.allies" :key="idx">
                  <v-list-item-title>
                    <span v-if="player.clanTag" class="text-primary font-weight-bold">
                      [{{ player.clanTag }}]
                    </span>
                    {{ player.name }}
                  </v-list-item-title>
                  <v-list-item-subtitle>
                    {{ player.shipName }}
                  </v-list-item-subtitle>
                </v-list-item>
              </v-list>
            </v-col>

            <!-- 敵 -->
            <v-col cols="12" md="4">
              <h3 class="mb-2">敵 ({{ match.enemies.length }}名)</h3>
              <v-list density="compact">
                <v-list-item v-for="(player, idx) in match.enemies" :key="idx">
                  <v-list-item-title>
                    <span v-if="player.clanTag" class="text-error font-weight-bold">
                      [{{ player.clanTag }}]
                    </span>
                    {{ player.name }}
                  </v-list-item-title>
                  <v-list-item-subtitle>
                    {{ player.shipName }}
                  </v-list-item-subtitle>
                </v-list-item>
              </v-list>
            </v-col>
          </v-row>
        </v-card-text>
      </v-card>

      <!-- 動画セクション -->
      <v-card>
        <v-card-title>
          ミニマップ動画
          <v-chip v-if="selectedReplay" size="small" class="ml-2">
            {{ selectedReplay.playerName }}のリプレイ
          </v-chip>
        </v-card-title>
        <v-card-text>
          <!-- 未生成 -->
          <div v-if="!hasVideo && !generatingVideo">
            <p>選択中のリプレイの動画はまだ生成されていません。</p>
            <v-btn color="primary" @click="handleGenerateVideo" :loading="generatingVideo">
              <v-icon left>mdi-video</v-icon>
              動画を生成
            </v-btn>
          </div>

          <!-- 生成中 -->
          <div v-if="generatingVideo">
            <v-progress-linear indeterminate></v-progress-linear>
            <p class="mt-2">動画を生成中です... (数分かかる場合があります)</p>
          </div>

          <!-- 生成済み -->
          <div v-if="hasVideo && videoUrl">
            <video controls width="100%" :src="videoUrl">
              お使いのブラウザは動画タグをサポートしていません。
            </video>
            <div class="mt-2">
              <v-btn color="primary" :href="videoUrl" download>
                <v-icon left>mdi-download</v-icon>
                動画をダウンロード
              </v-btn>
              <v-chip v-if="selectedReplay?.mp4GeneratedAt" size="small" class="ml-2">
                生成日時: {{ formatDateTime(selectedReplay.mp4GeneratedAt) }}
              </v-chip>
            </div>
          </div>
        </v-card-text>
      </v-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import type { MatchDetailResponse, ReplayProvider } from '~/types/replay'

const route = useRoute()
const api = useApi()

const loading = ref(true)
const error = ref<string | null>(null)
const match = ref<MatchDetailResponse | null>(null)
const selectedReplayIndex = ref(0)
const generatingVideo = ref(false)
const videoUrl = ref<string | null>(null)

// 選択中のリプレイ
const selectedReplay = computed(() => {
  if (!match.value || !match.value.replays || match.value.replays.length === 0) {
    return null
  }
  return match.value.replays[selectedReplayIndex.value]
})

// 選択中のリプレイに動画があるか
const hasVideo = computed(() => {
  return selectedReplay.value?.mp4S3Key != null
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

      // 動画が既に生成済みのリプレイを優先選択
      const videoReplayIndex = data.replays.findIndex((r) => r.mp4S3Key)
      if (videoReplayIndex >= 0) {
        selectedReplayIndex.value = videoReplayIndex
      }

      // 動画URLを設定
      updateVideoUrl()
    } else {
      error.value = '試合データが見つかりません'
    }
  } catch (err: any) {
    error.value = err.message || 'データ取得エラー'
  } finally {
    loading.value = false
  }
})

// リプレイ選択時の処理
const selectReplay = (index: number) => {
  selectedReplayIndex.value = index
  updateVideoUrl()
}

// 動画URLを更新
const updateVideoUrl = () => {
  const replay = selectedReplay.value
  if (replay?.mp4S3Key) {
    // 仮実装: 実際にはAPIから署名付きURLを取得する必要がある
    videoUrl.value = `https://wows-replay-bot-dev-temp.s3.ap-northeast-1.amazonaws.com/${replay.mp4S3Key}`
  } else {
    videoUrl.value = null
  }
}

const handleGenerateVideo = async () => {
  if (!match.value || !selectedReplay.value) return

  generatingVideo.value = true
  try {
    const response = await api.generateVideo({
      arenaUniqueID: match.value.arenaUniqueID,
      playerID: selectedReplay.value.playerID,
    })

    if (response.status === 'already_exists' || response.status === 'generated') {
      videoUrl.value = response.videoUrl || null
      if (selectedReplay.value && response.mp4S3Key) {
        selectedReplay.value.mp4S3Key = response.mp4S3Key
        updateVideoUrl()
      }
    }
  } catch (err: any) {
    error.value = `動画生成エラー: ${err.message}`
  } finally {
    generatingVideo.value = false
  }
}

const downloadReplay = (s3Key: string) => {
  const url = api.getReplayDownloadUrl(s3Key)
  window.open(url, '_blank')
}

// フォーマット関数
const formatDateTime = (dateTime: string) => {
  if (!dateTime) return '-'
  return new Date(dateTime).toLocaleString('ja-JP')
}

const formatFileSize = (bytes: number) => {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(2)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
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
