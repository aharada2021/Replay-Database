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
    <v-alert v-if="!loading && !replay" type="warning" class="mb-4">
      リプレイデータが見つかりません
    </v-alert>

    <!-- 詳細表示 -->
    <div v-if="replay">
      <!-- 試合情報カード -->
      <v-card class="mb-4">
        <v-card-title>試合情報</v-card-title>
        <v-card-text>
          <v-row>
            <v-col cols="12" md="6">
              <div class="mb-2">
                <strong>日時:</strong> {{ formatDateTime(replay.dateTime) }}
              </div>
              <div class="mb-2">
                <strong>マップ:</strong> {{ replay.mapDisplayName }}
              </div>
              <div class="mb-2">
                <strong>ゲームタイプ:</strong>
                <v-chip :color="getGameTypeColor(replay.gameType)" size="small" class="ml-2">
                  {{ getGameTypeText(replay.gameType) }}
                </v-chip>
              </div>
              <div class="mb-2">
                <strong>勝敗:</strong>
                <v-chip :color="getWinLossColor(replay.winLoss)" size="small" class="ml-2">
                  {{ getWinLossText(replay.winLoss) }}
                </v-chip>
              </div>
            </v-col>
            <v-col cols="12" md="6">
              <div class="mb-2">
                <strong>アップロード者:</strong> {{ replay.uploadedBy }}
              </div>
              <div class="mb-2">
                <strong>アップロード日時:</strong> {{ formatDateTime(replay.uploadedAt) }}
              </div>
              <div class="mb-2">
                <strong>ファイル名:</strong> {{ replay.fileName }}
              </div>
              <div class="mb-2">
                <strong>ファイルサイズ:</strong> {{ formatFileSize(replay.fileSize) }}
              </div>
            </v-col>
          </v-row>
        </v-card-text>
        <v-card-actions>
          <v-btn color="primary" @click="downloadReplay">
            <v-icon left>mdi-download</v-icon>
            リプレイをダウンロード
          </v-btn>
        </v-card-actions>
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
                    <span v-if="replay.ownPlayer.clanTag" class="text-primary font-weight-bold">
                      [{{ replay.ownPlayer.clanTag }}]
                    </span>
                    {{ replay.ownPlayer.name }}
                  </v-list-item-title>
                  <v-list-item-subtitle>
                    {{ replay.ownPlayer.shipName }}
                  </v-list-item-subtitle>
                </v-list-item>
              </v-list>
            </v-col>

            <!-- 味方 -->
            <v-col cols="12" md="4">
              <h3 class="mb-2">味方 ({{ replay.allies.length }}名)</h3>
              <v-list density="compact">
                <v-list-item v-for="(player, idx) in replay.allies" :key="idx">
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
              <h3 class="mb-2">敵 ({{ replay.enemies.length }}名)</h3>
              <v-list density="compact">
                <v-list-item v-for="(player, idx) in replay.enemies" :key="idx">
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
        <v-card-title>動画</v-card-title>
        <v-card-text>
          <!-- 未生成 -->
          <div v-if="!replay.mp4S3Key && !generatingVideo">
            <p>このリプレイの動画はまだ生成されていません。</p>
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
          <div v-if="replay.mp4S3Key && videoUrl">
            <video controls width="100%" :src="videoUrl">
              お使いのブラウザは動画タグをサポートしていません。
            </video>
            <div class="mt-2">
              <v-btn color="primary" :href="videoUrl" download>
                <v-icon left>mdi-download</v-icon>
                動画をダウンロード
              </v-btn>
            </div>
          </div>
        </v-card-text>
      </v-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import type { ReplayRecord } from '~/types/replay'

const route = useRoute()
const api = useApi()

const loading = ref(true)
const error = ref<string | null>(null)
const replay = ref<ReplayRecord | null>(null)
const generatingVideo = ref(false)
const videoUrl = ref<string | null>(null)

// URLパラメータから arena ID と player ID を抽出
const parseId = (id: string) => {
  console.log('[Detail] Parsing ID:', id)
  const parts = id.split('-')
  console.log('[Detail] Split parts:', parts)

  if (parts.length < 2) {
    console.error('[Detail] Invalid ID format, expected at least 2 parts')
    return null
  }

  // arenaUniqueIDは最後のパート以外をすべて結合
  const playerIdPart = parts[parts.length - 1]
  const arenaIdParts = parts.slice(0, -1)
  const arenaUniqueID = arenaIdParts.join('-')
  const playerID = parseInt(playerIdPart, 10)

  console.log('[Detail] Parsed:', { arenaUniqueID, playerID })

  if (isNaN(playerID)) {
    console.error('[Detail] PlayerID is NaN')
    return null
  }

  return {
    arenaUniqueID,
    playerID,
  }
}

onMounted(async () => {
  const id = route.params.id as string
  console.log('[Detail] Route params:', route.params)
  console.log('[Detail] ID from route:', id)

  const parsed = parseId(id)

  if (!parsed) {
    error.value = '無効なIDです'
    loading.value = false
    return
  }

  try {
    const data = await api.getReplayDetail(parsed.arenaUniqueID, parsed.playerID)
    if (data) {
      replay.value = data

      // 動画が既に生成済みの場合、URLを取得
      if (data.mp4S3Key) {
        // 仮実装: 実際にはAPIから署名付きURLを取得する必要がある
        videoUrl.value = `https://wows-replay-bot-dev-temp.s3.ap-northeast-1.amazonaws.com/${data.mp4S3Key}`
      }
    } else {
      error.value = 'リプレイが見つかりません'
    }
  } catch (err: any) {
    error.value = err.message || 'データ取得エラー'
  } finally {
    loading.value = false
  }
})

const handleGenerateVideo = async () => {
  if (!replay.value) return

  generatingVideo.value = true
  try {
    const response = await api.generateVideo({
      arenaUniqueID: replay.value.arenaUniqueID,
      playerID: replay.value.playerID,
    })

    if (response.status === 'already_exists' || response.status === 'generated') {
      videoUrl.value = response.videoUrl || null
      if (replay.value) {
        replay.value.mp4S3Key = response.mp4S3Key
      }
    }
  } catch (err: any) {
    error.value = `動画生成エラー: ${err.message}`
  } finally {
    generatingVideo.value = false
  }
}

const downloadReplay = () => {
  if (!replay.value) return
  const url = api.getReplayDownloadUrl(replay.value.s3Key)
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
