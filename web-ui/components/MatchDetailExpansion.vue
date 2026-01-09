<template>
  <div class="pa-4">
    <!-- スコアボード + ミニマップ動画 横並び -->
    <v-row v-if="hasAllPlayersStats">
      <!-- 全プレイヤー戦闘統計（スコアボード） -->
      <v-col cols="12" lg="8">
        <div class="d-flex align-center mb-2">
          <h3 class="text-body-2">戦闘統計スコアボード</h3>
          <v-btn
            v-if="isCustomSorted"
            size="x-small"
            variant="text"
            color="primary"
            class="ml-2"
            @click="resetToDefaultSort"
          >
            <v-icon size="small" class="mr-1">mdi-sort</v-icon>
            デフォルト順に戻す
          </v-btn>
        </div>
        <v-data-table
          v-model:sort-by="sortBy"
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
                <!-- アップグレード -->
                <div v-if="item.upgrades?.length" class="mb-2">
                  <div class="tooltip-title">
                    <v-icon size="small" class="mr-1">mdi-wrench</v-icon>
                    アップグレード ({{ item.upgrades.length }})
                  </div>
                  <div class="upgrades-list">
                    <span v-for="(upgrade, idx) in item.upgrades" :key="idx" class="upgrade-chip">
                      {{ upgrade }}
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
                    <span v-for="(skill, idx) in item.captainSkills" :key="idx" class="skill-chip">
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

          <!-- 艦種 -->
          <template v-slot:item.shipClass="{ item }">
            <v-tooltip v-if="item.shipClass" location="top">
              <template v-slot:activator="{ props }">
                <img
                  v-bind="props"
                  :src="getShipClassIcon(item.shipClass)"
                  :alt="getShipClassShortLabel(item.shipClass)"
                  class="ship-class-icon"
                />
              </template>
              {{ getShipClassShortLabel(item.shipClass) }}
            </v-tooltip>
            <span v-else class="text-grey">-</span>
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
            <v-tooltip location="top">
              <template v-slot:activator="{ props }">
                <span v-bind="props" class="cursor-help">{{ formatNumber(item.receivedDamage) }}</span>
              </template>
              <div class="tooltip-content">
                <div class="tooltip-title">被ダメージ内訳</div>
                <div class="tooltip-row">
                  <span>主砲 AP:</span>
                  <span>{{ formatNumber(item.receivedDamageAP) }}</span>
                </div>
                <div class="tooltip-row">
                  <span>主砲 HE:</span>
                  <span>{{ formatNumber(item.receivedDamageHE) }}</span>
                </div>
                <div class="tooltip-row">
                  <span>副砲 HE:</span>
                  <span>{{ formatNumber(item.receivedDamageHESecondaries) }}</span>
                </div>
                <div class="tooltip-row">
                  <span>魚雷:</span>
                  <span>{{ formatNumber(item.receivedDamageTorps) }}</span>
                </div>
                <div class="tooltip-row text-orange">
                  <span>火災:</span>
                  <span>{{ formatNumber(item.receivedDamageFire) }}</span>
                </div>
                <div class="tooltip-row text-blue">
                  <span>浸水:</span>
                  <span>{{ formatNumber(item.receivedDamageFlood) }}</span>
                </div>
              </div>
            </v-tooltip>
          </template>

          <template v-slot:item.potentialDamage="{ item }">
            <v-tooltip location="top">
              <template v-slot:activator="{ props }">
                <span v-bind="props" class="cursor-help">{{ formatNumber(item.potentialDamage) }}</span>
              </template>
              <div class="tooltip-content">
                <div class="tooltip-title">潜在ダメージ内訳</div>
                <div class="tooltip-row">
                  <span>砲撃:</span>
                  <span>{{ formatNumber(item.potentialDamageArt) }}</span>
                </div>
                <div class="tooltip-row">
                  <span>魚雷:</span>
                  <span>{{ formatNumber(item.potentialDamageTpd) }}</span>
                </div>
              </div>
            </v-tooltip>
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
            <v-tooltip location="top">
              <template v-slot:activator="{ props }">
                <span v-bind="props" class="text-purple font-weight-bold cursor-help">{{ item.citadels || 0 }}</span>
              </template>
              <div class="tooltip-content">
                <div class="tooltip-title">クリティカル内訳</div>
                <div class="tooltip-row">
                  <span>貫通 (Citadels):</span>
                  <span>{{ item.citadels || 0 }}</span>
                </div>
                <div class="tooltip-row">
                  <span>モジュール破壊 (Crits):</span>
                  <span>{{ item.crits || 0 }}</span>
                </div>
              </div>
            </v-tooltip>
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
        <v-alert v-else :type="isPolling ? 'warning' : 'info'" density="compact" class="d-flex align-center">
          <template v-if="isPolling">
            <v-progress-circular size="16" width="2" indeterminate class="mr-2" />
            動画を生成中...
          </template>
          <template v-else>
            動画なし
          </template>
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
        <v-alert v-else :type="isPolling ? 'warning' : 'info'" density="compact" class="d-flex align-center">
          <template v-if="isPolling">
            <v-progress-circular size="16" width="2" indeterminate class="mr-2" />
            動画を生成中...
          </template>
          <template v-else>
            この試合の動画はまだ生成されていません
          </template>
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
import { computed, ref } from 'vue'
import type { MatchRecord, PlayerStats, ShipClass } from '~/types/replay'

const props = defineProps<{
  match: MatchRecord
  isPolling?: boolean
}>()

const api = useApi()
const { getShipClassShortLabel, getShipClassIcon } = useShipClass()
const config = useRuntimeConfig()

// 艦種のソート優先度（空母→戦艦→巡洋艦→駆逐艦→潜水艦）
const SHIP_CLASS_PRIORITY: Record<string, number> = {
  'AirCarrier': 0,
  'Battleship': 1,
  'Cruiser': 2,
  'Destroyer': 3,
  'Submarine': 4,
  'Auxiliary': 5,
}

// v-data-tableのソート状態
const sortBy = ref<{ key: string; order: 'asc' | 'desc' }[]>([])

// カスタムソートが適用されているか
const isCustomSorted = computed(() => sortBy.value.length > 0)

// 全プレイヤー統計があるかどうか
const hasAllPlayersStats = computed(() => {
  return props.match.allPlayersStats && props.match.allPlayersStats.length > 0
})

// スコアボードのヘッダー（圧縮版）
const scoreboardHeaders = [
  { title: '', key: 'team', sortable: true, width: '30px' },
  { title: 'プレイヤー', key: 'playerName', sortable: true },
  { title: '', key: 'shipClass', sortable: true, width: '30px' },
  { title: '艦船', key: 'shipName', sortable: true },
  { title: '撃沈', key: 'kills', sortable: true, align: 'end' as const, width: '40px' },
  { title: '与ダメ', key: 'damage', sortable: true, align: 'end' as const, width: '65px' },
  { title: '観測', key: 'spottingDamage', sortable: true, align: 'end' as const, width: '55px' },
  { title: '被ダメ', key: 'receivedDamage', sortable: true, align: 'end' as const, width: '55px' },
  { title: '潜在', key: 'potentialDamage', sortable: true, align: 'end' as const, width: '60px' },
  { title: '命中', key: 'totalHits', sortable: true, align: 'end' as const, width: '40px' },
  { title: '火', key: 'fires', sortable: true, align: 'end' as const, width: '30px' },
  { title: '浸', key: 'floods', sortable: true, align: 'end' as const, width: '30px' },
  { title: '貫通', key: 'citadels', sortable: true, align: 'end' as const, width: '35px' },
  { title: 'XP', key: 'baseXP', sortable: true, align: 'end' as const, width: '50px' },
]

// 命中数を計算するヘルパー
const getTotalHits = (player: PlayerStats): number => {
  return (player.hitsAP || 0) + (player.hitsHE || 0) + (player.hitsSecondaries || 0)
}

// デフォルトソート: 味方→敵、艦種順、XP順、ダメージ順
const defaultSortedPlayersStats = computed(() => {
  if (!props.match.allPlayersStats) return []
  return [...props.match.allPlayersStats]
    .map(p => ({ ...p, totalHits: getTotalHits(p) }))
    .sort((a, b) => {
      // 1. チーム（味方が先）
      const teamOrder = (a.team === 'ally' ? 0 : 1) - (b.team === 'ally' ? 0 : 1)
      if (teamOrder !== 0) return teamOrder

      // 2. 艦種（空母→戦艦→巡洋艦→駆逐艦→潜水艦）
      const classA = SHIP_CLASS_PRIORITY[a.shipClass || ''] ?? 99
      const classB = SHIP_CLASS_PRIORITY[b.shipClass || ''] ?? 99
      if (classA !== classB) return classA - classB

      // 3. 経験値（高い方が先）
      const xpDiff = (b.baseXP || 0) - (a.baseXP || 0)
      if (xpDiff !== 0) return xpDiff

      // 4. ダメージ（高い方が先）
      return (b.damage || 0) - (a.damage || 0)
    })
})

// 表示用のプレイヤー統計（デフォルトソートを使用）
const sortedPlayersStats = computed(() => defaultSortedPlayersStats.value)

// デフォルトソートにリセット
const resetToDefaultSort = () => {
  sortBy.value = []
}

// 数値をカンマ区切りでフォーマット
const formatNumber = (value: number | undefined | null): string => {
  if (value === undefined || value === null) return '0'
  return value.toLocaleString()
}

// プレイヤー詳細情報があるかどうか
const hasPlayerDetails = (player: PlayerStats): boolean => {
  return !!(player.captainSkills?.length || player.upgrades?.length)
}

// 動画があるリプレイを取得
const videoReplay = computed(() => {
  if (!props.match.replays) return null
  return props.match.replays.find(r => r.mp4S3Key) || null
})

// 動画URLを生成
const getVideoUrl = (mp4S3Key: string | undefined) => {
  if (!mp4S3Key) return ''
  // S3バケットURLは環境変数から取得
  const s3BucketUrl = config.public.s3BucketUrl
  return `${s3BucketUrl}/${mp4S3Key}`
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

.ship-class-icon {
  width: 20px;
  height: 20px;
  object-fit: contain;
  filter: invert(1);
  opacity: 0.8;
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
  background: #ffffff;
  color: #000000;
  padding: 8px;
  border-radius: 4px;
}

.player-details-tooltip .tooltip-title {
  font-weight: bold;
  margin-bottom: 6px;
  padding-bottom: 4px;
  border-bottom: 1px solid #cccccc;
  display: flex;
  align-items: center;
  color: #000000;
}

.captain-skills {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.skill-chip {
  background: #f0f0f0;
  color: #000000;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 0.7rem;
  white-space: nowrap;
}

.upgrades-list {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.upgrade-chip {
  background: #e3f2fd;
  color: #1565c0;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 0.7rem;
  white-space: nowrap;
}
</style>
