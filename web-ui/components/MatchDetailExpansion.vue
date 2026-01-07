<template>
  <div class="pa-4">
    <!-- 戦闘統計 -->
    <div v-if="hasBattleStats">
      <h3 class="mb-3">戦闘統計</h3>
      <v-row>
        <!-- 基本統計 -->
        <v-col cols="12" md="4">
          <v-card variant="outlined" class="h-100">
            <v-card-title class="text-subtitle-2 bg-blue-grey-darken-3">基本統計</v-card-title>
            <v-card-text class="pa-3">
              <div class="d-flex justify-space-between mb-2">
                <span class="text-grey">与ダメージ</span>
                <span class="font-weight-bold">{{ formatNumber(match.damage) }}</span>
              </div>
              <div class="d-flex justify-space-between mb-2">
                <span class="text-grey">被ダメージ</span>
                <span class="font-weight-bold">{{ formatNumber(match.receivedDamage) }}</span>
              </div>
              <div class="d-flex justify-space-between mb-2">
                <span class="text-grey">偵察ダメージ</span>
                <span class="font-weight-bold">{{ formatNumber(match.spottingDamage) }}</span>
              </div>
              <div class="d-flex justify-space-between mb-2">
                <span class="text-grey">潜在ダメージ</span>
                <span class="font-weight-bold">{{ formatNumber(match.potentialDamage) }}</span>
              </div>
              <v-divider class="my-2"></v-divider>
              <div class="d-flex justify-space-between mb-2">
                <span class="text-grey">撃沈数</span>
                <span class="font-weight-bold text-error">{{ match.kills || 0 }}</span>
              </div>
              <div class="d-flex justify-space-between mb-2">
                <span class="text-grey">火災発生</span>
                <span class="font-weight-bold text-orange">{{ match.fires || 0 }}</span>
              </div>
              <div class="d-flex justify-space-between mb-2">
                <span class="text-grey">浸水発生</span>
                <span class="font-weight-bold text-blue">{{ match.floods || 0 }}</span>
              </div>
              <div class="d-flex justify-space-between">
                <span class="text-grey">基礎経験値</span>
                <span class="font-weight-bold text-amber">{{ formatNumber(match.baseXP) }}</span>
              </div>
            </v-card-text>
          </v-card>
        </v-col>

        <!-- ダメージ内訳 -->
        <v-col cols="12" md="4">
          <v-card variant="outlined" class="h-100">
            <v-card-title class="text-subtitle-2 bg-red-darken-3">ダメージ内訳</v-card-title>
            <v-card-text class="pa-3">
              <div class="text-caption text-grey mb-1">主砲</div>
              <div class="d-flex justify-space-between mb-1 pl-2">
                <span class="text-grey-lighten-1">AP弾</span>
                <span>{{ formatNumber(match.damageAP) }}</span>
              </div>
              <div class="d-flex justify-space-between mb-2 pl-2">
                <span class="text-grey-lighten-1">HE弾</span>
                <span>{{ formatNumber(match.damageHE) }}</span>
              </div>
              <div class="text-caption text-grey mb-1">副砲</div>
              <div class="d-flex justify-space-between mb-2 pl-2">
                <span class="text-grey-lighten-1">HE弾</span>
                <span>{{ formatNumber(match.damageHESecondaries) }}</span>
              </div>
              <div class="text-caption text-grey mb-1">魚雷</div>
              <div class="d-flex justify-space-between mb-1 pl-2">
                <span class="text-grey-lighten-1">通常魚雷</span>
                <span>{{ formatNumber(match.damageTorps) }}</span>
              </div>
              <div class="d-flex justify-space-between mb-2 pl-2">
                <span class="text-grey-lighten-1">深水魚雷</span>
                <span>{{ formatNumber(match.damageDeepWaterTorps) }}</span>
              </div>
              <div class="text-caption text-grey mb-1">継続ダメージ</div>
              <div class="d-flex justify-space-between mb-1 pl-2">
                <span class="text-grey-lighten-1 text-orange">火災</span>
                <span>{{ formatNumber(match.damageFire) }}</span>
              </div>
              <div class="d-flex justify-space-between mb-2 pl-2">
                <span class="text-grey-lighten-1 text-blue">浸水</span>
                <span>{{ formatNumber(match.damageFlooding) }}</span>
              </div>
              <div class="d-flex justify-space-between">
                <span class="text-grey">その他</span>
                <span>{{ formatNumber(match.damageOther) }}</span>
              </div>
            </v-card-text>
          </v-card>
        </v-col>

        <!-- 命中数内訳 -->
        <v-col cols="12" md="4">
          <v-card variant="outlined" class="h-100">
            <v-card-title class="text-subtitle-2 bg-green-darken-3">命中数内訳</v-card-title>
            <v-card-text class="pa-3">
              <div class="text-caption text-grey mb-1">主砲</div>
              <div class="d-flex justify-space-between mb-1 pl-2">
                <span class="text-grey-lighten-1">AP弾</span>
                <span>{{ match.hitsAP || 0 }} 発</span>
              </div>
              <div class="d-flex justify-space-between mb-2 pl-2">
                <span class="text-grey-lighten-1">HE弾</span>
                <span>{{ match.hitsHE || 0 }} 発</span>
              </div>
              <div class="text-caption text-grey mb-1">副砲</div>
              <div class="d-flex justify-space-between pl-2">
                <span class="text-grey-lighten-1">HE弾</span>
                <span>{{ match.hitsSecondaries || 0 }} 発</span>
              </div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <v-divider class="my-4"></v-divider>
    </div>

    <v-row>
      <!-- プレイヤー一覧 -->
      <v-col cols="12" md="6">
        <h3 class="mb-2">プレイヤー一覧</h3>
        <v-row dense>
          <!-- 自分 -->
          <v-col cols="12">
            <v-card variant="outlined" density="compact">
              <v-card-title class="text-caption bg-primary py-1">自分</v-card-title>
              <v-card-text class="pa-2">
                <div class="text-body-2">
                  <span v-if="match.ownPlayer.clanTag" class="text-primary font-weight-bold">
                    [{{ match.ownPlayer.clanTag }}]
                  </span>
                  {{ match.ownPlayer.name }}
                  <span class="text-caption text-grey ml-2">{{ match.ownPlayer.shipName }}</span>
                </div>
              </v-card-text>
            </v-card>
          </v-col>

          <!-- 味方 -->
          <v-col cols="6">
            <v-card variant="outlined" density="compact">
              <v-card-title class="text-caption bg-success py-1">味方 ({{ match.allies?.length || 0 }}名)</v-card-title>
              <v-card-text class="pa-2" style="max-height: 200px; overflow-y: auto">
                <div v-for="(player, idx) in match.allies" :key="idx" class="mb-1">
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
          <v-col cols="6">
            <v-card variant="outlined" density="compact">
              <v-card-title class="text-caption bg-error py-1">敵 ({{ match.enemies?.length || 0 }}名)</v-card-title>
              <v-card-text class="pa-2" style="max-height: 200px; overflow-y: auto">
                <div v-for="(player, idx) in match.enemies" :key="idx" class="mb-1">
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
      </v-col>

      <!-- 動画プレーヤー -->
      <v-col cols="12" md="6">
        <h3 class="mb-2">ミニマップ動画</h3>
        <div v-if="videoReplay">
          <video controls width="100%" :src="getVideoUrl(videoReplay.mp4S3Key)">
            お使いのブラウザは動画タグをサポートしていません。
          </video>
          <div class="mt-1 text-caption">
            <v-icon size="small">mdi-account</v-icon>
            {{ videoReplay.playerName }} のリプレイ
          </div>
        </div>
        <v-alert v-else type="info" density="compact">
          この試合の動画はまだ生成されていません
        </v-alert>
      </v-col>
    </v-row>

    <v-divider class="my-3"></v-divider>

    <!-- リプレイ提供者 -->
    <h3 class="mb-2">リプレイ提供者</h3>
    <v-list density="compact" class="py-0">
      <v-list-item v-for="(replay, index) in match.replays" :key="index" class="px-0">
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
          <span class="text-caption text-grey ml-2">
            {{ replay.ownPlayer?.shipName || '-' }} | {{ formatDateTime(replay.uploadedAt) }}
          </span>
        </v-list-item-title>

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
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { MatchRecord } from '~/types/replay'

const props = defineProps<{
  match: MatchRecord
}>()

const api = useApi()

// 戦闘統計があるかどうか
const hasBattleStats = computed(() => {
  return props.match.damage !== undefined && props.match.damage !== null
})

// 数値をカンマ区切りでフォーマット
const formatNumber = (value: number | undefined | null): string => {
  if (value === undefined || value === null) return '0'
  return value.toLocaleString()
}

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
