<template>
  <div class="pa-4">
    <v-row>
      <!-- リプレイ提供者 -->
      <v-col cols="12" md="6">
        <h3 class="mb-3">リプレイ提供者</h3>
        <v-list density="compact">
          <v-list-item v-for="(replay, index) in match.replays" :key="index" class="mb-1">
            <template v-slot:prepend>
              <v-avatar size="small" color="primary">
                <v-icon v-if="replay.mp4S3Key" size="small">mdi-video</v-icon>
                <v-icon v-else size="small">mdi-account</v-icon>
              </v-avatar>
            </template>

            <v-list-item-title>
              <span v-if="replay.ownPlayer?.clanTag" class="text-primary font-weight-bold">
                [{{ replay.ownPlayer.clanTag }}]
              </span>
              {{ replay.playerName }}
              <v-chip v-if="replay.mp4S3Key" size="x-small" color="success" class="ml-1">
                動画あり
              </v-chip>
            </v-list-item-title>

            <v-list-item-subtitle>
              {{ replay.ownPlayer?.shipName || '-' }} | {{ formatDateTime(replay.uploadedAt) }}
            </v-list-item-subtitle>

            <template v-slot:append>
              <v-btn
                size="x-small"
                variant="text"
                icon="mdi-download"
                @click="downloadReplay(replay.s3Key)"
              ></v-btn>
            </template>
          </v-list-item>
        </v-list>
      </v-col>

      <!-- 動画プレーヤー -->
      <v-col cols="12" md="6">
        <h3 class="mb-3">ミニマップ動画</h3>
        <div v-if="videoReplay">
          <video controls width="100%" :src="getVideoUrl(videoReplay.mp4S3Key)">
            お使いのブラウザは動画タグをサポートしていません。
          </video>
          <div class="mt-2 text-caption">
            <v-icon size="small">mdi-account</v-icon>
            {{ videoReplay.playerName }} のリプレイ
          </div>
        </div>
        <v-alert v-else type="info" density="compact">
          このこの試合の動画はまだ生成されていません
        </v-alert>
      </v-col>
    </v-row>

    <v-divider class="my-4"></v-divider>

    <!-- プレイヤー一覧 -->
    <h3 class="mb-3">プレイヤー一覧</h3>
    <v-row>
      <!-- 自分 -->
      <v-col cols="12" md="4">
        <v-card variant="outlined">
          <v-card-title class="text-subtitle-2 bg-primary">自分</v-card-title>
          <v-card-text class="pa-2">
            <div class="text-body-2">
              <span v-if="match.ownPlayer.clanTag" class="text-primary font-weight-bold">
                [{{ match.ownPlayer.clanTag }}]
              </span>
              {{ match.ownPlayer.name }}
            </div>
            <div class="text-caption text-grey">{{ match.ownPlayer.shipName }}</div>
          </v-card-text>
        </v-card>
      </v-col>

      <!-- 味方 -->
      <v-col cols="12" md="4">
        <v-card variant="outlined">
          <v-card-title class="text-subtitle-2 bg-success">味方 ({{ match.allies?.length || 0 }}名)</v-card-title>
          <v-card-text class="pa-2" style="max-height: 300px; overflow-y: auto">
            <div v-for="(player, idx) in match.allies" :key="idx" class="mb-2">
              <div class="text-body-2">
                <span v-if="player.clanTag" class="text-primary font-weight-bold">
                  [{{ player.clanTag }}]
                </span>
                {{ player.name }}
              </div>
              <div class="text-caption text-grey">{{ player.shipName }}</div>
            </div>
          </v-card-text>
        </v-card>
      </v-col>

      <!-- 敵 -->
      <v-col cols="12" md="4">
        <v-card variant="outlined">
          <v-card-title class="text-subtitle-2 bg-error">敵 ({{ match.enemies?.length || 0 }}名)</v-card-title>
          <v-card-text class="pa-2" style="max-height: 300px; overflow-y: auto">
            <div v-for="(player, idx) in match.enemies" :key="idx" class="mb-2">
              <div class="text-body-2">
                <span v-if="player.clanTag" class="text-error font-weight-bold">
                  [{{ player.clanTag }}]
                </span>
                {{ player.name }}
              </div>
              <div class="text-caption text-grey">{{ player.shipName }}</div>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { MatchRecord } from '~/types/replay'

const props = defineProps<{
  match: MatchRecord
}>()

const api = useApi()

// 動画があるリプレイを取得
const videoReplay = computed(() => {
  if (!props.match.replays) return null
  return props.match.replays.find(r => r.mp4S3Key) || null
})

// 動画URLを生成
const getVideoUrl = (mp4S3Key: string | undefined) => {
  if (!mp4S3Key) return ''
  // 仮実装: 実際にはAPIから署名付きURLを取得
  return `https://wows-replay-bot-dev-temp.s3.ap-northeast-1.amazonaws.com/${mp4S3Key}`
}

// リプレイをダウンロード
const downloadReplay = (s3Key: string) => {
  const url = api.getReplayDownloadUrl(s3Key)
  window.open(url, '_blank')
}

// 日時フォーマット
const formatDateTime = (dateTime: string) => {
  if (!dateTime) return '-'

  try {
    const parts = dateTime.match(/(\d{2})\.(\d{2})\.(\d{4}) (\d{2}):(\d{2}):(\d{2})/)
    if (parts) {
      const [_, day, month, year, hour, minute, second] = parts
      return `${year}/${month}/${day} ${hour}:${minute}`
    }

    const date = new Date(dateTime)
    if (!isNaN(date.getTime())) {
      const year = date.getFullYear()
      const month = String(date.getMonth() + 1).padStart(2, '0')
      const day = String(date.getDate()).padStart(2, '0')
      const hour = String(date.getHours()).padStart(2, '0')
      const minute = String(date.getMinutes()).padStart(2, '0')
      return `${year}/${month}/${day} ${hour}:${minute}`
    }
  } catch (e) {
    console.error('Date format error:', e)
  }

  return dateTime
}
</script>
