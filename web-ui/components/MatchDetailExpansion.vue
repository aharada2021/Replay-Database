<template>
  <div class="pa-4">
    <!-- スコアボード + ミニマップ動画 横並び -->
    <v-row v-if="hasAllPlayersStats">
      <!-- 全プレイヤー戦闘統計（スコアボード） -->
      <v-col cols="12" lg="8">
        <h3 class="mb-2 text-body-2">戦闘統計スコアボード</h3>
        <v-data-table
          :headers="scoreboardHeaders"
          :items="sortedPlayersStats"
          :items-per-page="-1"
          density="compact"
          class="scoreboard-table"
          hide-default-footer
        >
          <!-- チーム -->
          <template v-slot:item.team="{ item }">
            <span :class="item.team === 'ally' ? 'text-success' : 'text-error'">
              {{ item.team === 'ally' ? '🟢' : '🔴' }}
            </span>
            <v-icon v-if="item.isOwn" size="x-small" color="primary">mdi-star</v-icon>
          </template>

          <!-- プレイヤー名（艦長スキル・艦艇コンポーネントツールチップ付き） -->
          <template v-slot:item.playerName="{ item }">
            <v-tooltip v-if="hasPlayerDetails(item)" location="right" max-width="350">
              <template v-slot:activator="{ props }">
                <span v-bind="props" class="cursor-help">
                  <span v-if="item.clanTag" class="font-weight-bold" :class="item.team === 'ally' ? 'text-success' : 'text-error'">
                    [{{ item.clanTag }}]
                  </span>
                  {{ item.playerName }}
                  <v-icon v-if="item.captainSkills?.length" size="x-small" color="amber" class="ml-1">mdi-star-circle</v-icon>
                </span>
              </template>
              <div class="player-details-tooltip">
                <!-- 艦艇コンポーネント -->
                <div v-if="item.shipComponents && Object.keys(item.shipComponents).length > 0" class="mb-2">
                  <div class="tooltip-title">
                    <v-icon size="small" class="mr-1">mdi-cog</v-icon>
                    艦艇モジュール
                  </div>
                  <div class="ship-components">
                    <span v-for="(value, key) in item.shipComponents" :key="key" :class="['component-chip', item.team === 'enemy' ? 'component-chip-enemy' : '']">
                      {{ getComponentLabel(key) }} {{ value }}
                    </span>
                  </div>
                </div>
                <!-- 艦長スキル -->
                <div v-if="item.captainSkills?.length">
                  <div class="tooltip-title">
                    <v-icon size="small" class="mr-1">mdi-account-star</v-icon>
                    艦長スキル ({{ item.captainSkills.length }})
                  </div>
                  <div class="captain-skills">
                    <span v-for="(skill, idx) in item.captainSkills" :key="idx" :class="['skill-chip', item.team === 'enemy' ? 'skill-chip-enemy' : '']">
                      {{ skill }}
                    </span>
                  </div>
                </div>
              </div>
            </v-tooltip>
            <span v-else>
              <span v-if="item.clanTag" class="font-weight-bold" :class="item.team === 'ally' ? 'text-success' : 'text-error'">
                [{{ item.clanTag }}]
              </span>
              {{ item.playerName }}
            </span>
          </template>

          <!-- 艦船 -->
          <template v-slot:item.shipName="{ item }">
            <span class="text-caption">{{ item.shipName || '-' }}</span>
          </template>

          <!-- 数値フォーマット -->
          <template v-slot:item.kills="{ item }">
            <span class="text-error font-weight-bold">{{ item.kills || 0 }}</span>
          </template>

          <template v-slot:item.damage="{ item }">
            <v-tooltip location="top">
              <template v-slot:activator="{ props }">
                <span v-bind="props" class="font-weight-bold cursor-help">{{ formatNumber(item.damage) }}</span>
              </template>
              <div class="tooltip-content">
                <div class="tooltip-title">ダメージ内訳</div>
                <div class="tooltip-row">
                  <span>主砲 AP:</span>
                  <span>{{ formatNumber(item.damageAP) }}</span>
                </div>
                <div class="tooltip-row">
                  <span>主砲 HE:</span>
                  <span>{{ formatNumber(item.damageHE) }}</span>
                </div>
                <div class="tooltip-row">
                  <span>副砲 HE:</span>
                  <span>{{ formatNumber(item.damageHESecondaries) }}</span>
                </div>
                <div class="tooltip-row">
                  <span>魚雷:</span>
                  <span>{{ formatNumber(item.damageTorps) }}</span>
                </div>
                <div class="tooltip-row">
                  <span>深度魚雷:</span>
                  <span>{{ formatNumber(item.damageDeepWaterTorps) }}</span>
                </div>
                <div class="tooltip-row text-orange">
                  <span>火災:</span>
                  <span>{{ formatNumber(item.damageFire) }}</span>
                </div>
                <div class="tooltip-row text-blue">
                  <span>浸水:</span>
                  <span>{{ formatNumber(item.damageFlooding) }}</span>
                </div>
                <div class="tooltip-row">
                  <span>その他:</span>
                  <span>{{ formatNumber(item.damageOther) }}</span>
                </div>
              </div>
            </v-tooltip>
          </template>

          <template v-slot:item.spottingDamage="{ item }">
            {{ formatNumber(item.spottingDamage) }}
          </template>

          <template v-slot:item.receivedDamage="{ item }">
            {{ formatNumber(item.receivedDamage) }}
          </template>

          <template v-slot:item.potentialDamage="{ item }">
            {{ formatNumber(item.potentialDamage) }}
          </template>

          <template v-slot:item.totalHits="{ item }">
            <v-tooltip location="top">
              <template v-slot:activator="{ props }">
                <span v-bind="props" class="cursor-help">{{ item.totalHits || 0 }}</span>
              </template>
              <div class="tooltip-content">
                <div class="tooltip-title">命中数内訳</div>
                <div class="tooltip-row">
                  <span>主砲 AP:</span>
                  <span>{{ item.hitsAP || 0 }} 発</span>
                </div>
                <div class="tooltip-row">
                  <span>主砲 HE:</span>
                  <span>{{ item.hitsHE || 0 }} 発</span>
                </div>
                <div class="tooltip-row">
                  <span>副砲 HE:</span>
                  <span>{{ item.hitsSecondaries || 0 }} 発</span>
                </div>
              </div>
            </v-tooltip>
          </template>

          <template v-slot:item.fires="{ item }">
            <span class="text-orange">{{ item.fires || 0 }}</span>
          </template>

          <template v-slot:item.floods="{ item }">
            <span class="text-blue">{{ item.floods || 0 }}</span>
          </template>

          <template v-slot:item.citadels="{ item }">
            <span class="text-purple font-weight-bold">{{ item.citadels || 0 }}</span>
          </template>

          <template v-slot:item.baseXP="{ item }">
            <span class="text-amber">{{ formatNumber(item.baseXP) }}</span>
          </template>
        </v-data-table>
      </v-col>

      <!-- 動画プレーヤー（スコアボードがある場合） -->
      <v-col cols="12" lg="4">
        <h3 class="mb-2 text-body-2">ミニマップ動画</h3>
        <div v-if="videoReplay" class="video-container">
          <video
            controls
            class="video-player"
            :src="getVideoUrl(videoReplay.mp4S3Key)"
          >
            お使いのブラウザは動画タグをサポートしていません。
          </video>
          <div class="mt-1 text-caption">
            <v-icon size="small">mdi-account</v-icon>
            {{ videoReplay.playerName }} のリプレイ
          </div>
        </div>
        <v-alert v-else type="info" density="compact">
          動画なし
        </v-alert>
      </v-col>
    </v-row>

    <!-- プレイヤー一覧（allPlayersStatsがない場合のフォールバック） + ミニマップ動画 -->
    <v-row v-else>
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
              <v-card-text class="pa-2">
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
              <v-card-text class="pa-2">
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

      <!-- 動画プレーヤー（スコアボードがない場合） -->
      <v-col cols="12" md="6">
        <h3 class="mb-2">ミニマップ動画</h3>
        <div v-if="videoReplay" class="video-container">
          <video
            controls
            class="video-player"
            :src="getVideoUrl(videoReplay.mp4S3Key)"
          >
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
import type { MatchRecord, PlayerStats } from '~/types/replay'

const props = defineProps<{
  match: MatchRecord
}>()

const api = useApi()

// 全プレイヤー統計があるかどうか
const hasAllPlayersStats = computed(() => {
  return props.match.allPlayersStats && props.match.allPlayersStats.length > 0
})

// スコアボードのヘッダー（圧縮版）
const scoreboardHeaders = [
  { title: '', key: 'team', sortable: true, width: '30px' },
  { title: 'プレイヤー', key: 'playerName', sortable: true },
  { title: '艦船', key: 'shipName', sortable: true },
  { title: '撃沈', key: 'kills', sortable: true, align: 'end' as const, width: '40px' },
  { title: '与ダメ', key: 'damage', sortable: true, align: 'end' as const, width: '65px' },
  { title: '観測', key: 'spottingDamage', sortable: true, align: 'end' as const, width: '55px' },
  { title: '被ダメ', key: 'receivedDamage', sortable: true, align: 'end' as const, width: '55px' },
  { title: '潜在', key: 'potentialDamage', sortable: true, align: 'end' as const, width: '60px' },
  { title: '命中', key: 'totalHits', sortable: true, align: 'end' as const, width: '40px' },
  { title: '火', key: 'fires', sortable: true, align: 'end' as const, width: '30px' },
  { title: '浸', key: 'floods', sortable: true, align: 'end' as const, width: '30px' },
  { title: 'Crits', key: 'citadels', sortable: true, align: 'end' as const, width: '35px' },
  { title: 'XP', key: 'baseXP', sortable: true, align: 'end' as const, width: '50px' },
]

// 命中数を計算するヘルパー
const getTotalHits = (player: PlayerStats): number => {
  return (player.hitsAP || 0) + (player.hitsHE || 0) + (player.hitsSecondaries || 0)
}

// ダメージ順にソートされたプレイヤー統計（totalHitsを追加）
const sortedPlayersStats = computed(() => {
  if (!props.match.allPlayersStats) return []
  return [...props.match.allPlayersStats]
    .map(p => ({ ...p, totalHits: getTotalHits(p) }))
    .sort((a, b) => (b.damage || 0) - (a.damage || 0))
})

// 数値をカンマ区切りでフォーマット
const formatNumber = (value: number | undefined | null): string => {
  if (value === undefined || value === null) return '0'
  return value.toLocaleString()
}

// プレイヤー詳細情報があるかどうか
const hasPlayerDetails = (player: PlayerStats): boolean => {
  return !!(player.captainSkills?.length || (player.shipComponents && Object.keys(player.shipComponents).length > 0))
}

// コンポーネントキーを日本語ラベルに変換
const componentLabels: Record<string, string> = {
  hull: '船体',
  artillery: '主砲',
  torpedoes: '魚雷',
  fireControl: '射撃管制',
  engine: 'エンジン',
  atba: '副砲',
  airDefense: '対空',
  finders: '探知機',
  directors: '測距儀',
  depthCharges: '爆雷',
  radars: 'レーダー',
}

const getComponentLabel = (key: string): string => {
  return componentLabels[key] || key
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

<style scoped>
.scoreboard-table {
  font-size: 0.7rem;
}

.scoreboard-table :deep(th),
.scoreboard-table :deep(td) {
  padding: 2px 4px !important;
  white-space: nowrap;
}

.scoreboard-table :deep(th) {
  font-size: 0.65rem !important;
}

.video-container {
  display: flex;
  flex-direction: column;
}

.video-player {
  width: 100%;
  max-height: calc(100vh - 200px);
  object-fit: contain;
}

.cursor-help {
  cursor: help;
  text-decoration: underline dotted;
  text-underline-offset: 2px;
}

.tooltip-content {
  min-width: 140px;
}

.tooltip-title {
  font-weight: bold;
  margin-bottom: 4px;
  padding-bottom: 4px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.3);
}

.tooltip-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 0.85rem;
  line-height: 1.4;
}

/* プレイヤー詳細ツールチップ */
.player-details-tooltip {
  max-width: 350px;
}

.player-details-tooltip .tooltip-title {
  font-weight: bold;
  margin-bottom: 6px;
  padding-bottom: 4px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.3);
  display: flex;
  align-items: center;
}

.ship-components {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.component-chip {
  background: rgba(33, 150, 243, 0.3);
  color: #90caf9;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 0.75rem;
  white-space: nowrap;
}

.component-chip-enemy {
  background: rgba(156, 39, 176, 0.3);
  color: #ce93d8;
}

.captain-skills {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.skill-chip {
  background: rgba(76, 175, 80, 0.3);
  color: #a5d6a7;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 0.7rem;
  white-space: nowrap;
}

.skill-chip-enemy {
  background: rgba(244, 67, 54, 0.3);
  color: #ef9a9a;
}
</style>
