<template>
  <div>
    <v-card class="mb-2" density="compact">
      <v-card-text class="py-2">
        <v-form @submit.prevent="handleSearch">
          <v-row dense align="center">
            <!-- ゲームタイプ -->
            <v-col cols="6" sm="4" md="2">
              <v-select
                v-model="searchStore.query.gameType"
                :items="gameTypes"
                label="ゲームタイプ"
                clearable
                density="compact"
                hide-details
                item-title="text"
                item-value="value"
              ></v-select>
            </v-col>

            <!-- マップ -->
            <v-col cols="6" sm="4" md="2">
              <v-select
                v-model="searchStore.query.mapId"
                :items="mapList"
                label="マップ"
                clearable
                density="compact"
                hide-details
                item-title="text"
                item-value="value"
              ></v-select>
            </v-col>

            <!-- 勝敗 -->
            <v-col cols="6" sm="4" md="1">
              <v-select
                v-model="searchStore.query.winLoss"
                :items="winLossTypes"
                label="勝敗"
                clearable
                density="compact"
                hide-details
                item-title="text"
                item-value="value"
              ></v-select>
            </v-col>

            <!-- 味方クランタグ -->
            <v-col cols="6" sm="4" md="1">
              <v-text-field
                v-model="searchStore.query.allyClanTag"
                label="味方"
                placeholder="クランタグ"
                clearable
                density="compact"
                hide-details
              ></v-text-field>
            </v-col>

            <!-- 敵クランタグ -->
            <v-col cols="6" sm="4" md="1">
              <v-text-field
                v-model="searchStore.query.enemyClanTag"
                label="敵"
                placeholder="クランタグ"
                clearable
                density="compact"
                hide-details
              ></v-text-field>
            </v-col>

            <!-- 日時範囲 From -->
            <v-col cols="6" sm="4" md="2">
              <v-text-field
                v-model="searchStore.query.dateFrom"
                label="From"
                clearable
                density="compact"
                hide-details
                type="date"
              ></v-text-field>
            </v-col>

            <!-- 日時範囲 To -->
            <v-col cols="6" sm="4" md="2">
              <v-text-field
                v-model="searchStore.query.dateTo"
                label="To"
                clearable
                density="compact"
                hide-details
                type="date"
              ></v-text-field>
            </v-col>

            <!-- ボタン -->
            <v-col cols="12" md="1" class="d-flex">
              <v-btn color="primary" type="submit" :loading="searchStore.loading" size="small" class="mr-1">
                <v-icon size="small">mdi-magnify</v-icon>
              </v-btn>
              <v-btn @click="handleReset" size="small">
                <v-icon size="small">mdi-refresh</v-icon>
              </v-btn>
            </v-col>
          </v-row>
        </v-form>
      </v-card-text>
    </v-card>

    <!-- 検索結果 -->
    <v-card>
      <v-data-table
        :headers="headers"
        :items="sortedResults"
        :loading="searchStore.loading || false"
        :items-per-page="searchStore.query?.limit || 50"
        hide-default-footer
        show-expand
        :expanded="expanded"
        @update:expanded="onExpandedChange"
        @click:row="onRowClick"
        item-value="matchKey"
        v-model:sort-by="sortBy"
        density="compact"
        class="clickable-rows"
      >
        <!-- カスタムヘッダー: 検索結果タイトルを追加 -->
        <template v-slot:top>
          <div class="d-flex align-center px-4 py-1 bg-surface">
            <span class="text-body-2 font-weight-medium">検索結果</span>
            <span class="text-caption text-grey ml-2">{{ searchStore.totalCount }} 件</span>
          </div>
        </template>
        <!-- 日時 -->
        <template v-slot:item.dateTime="{ item }">
          {{ formatDateTime(item?.dateTime || item?.raw?.dateTime) }}
        </template>

        <!-- マップ -->
        <template v-slot:item.mapDisplayName="{ item }">
          {{ getMapName(item?.mapId || item?.raw?.mapId) }}
        </template>

        <!-- ゲームタイプ -->
        <template v-slot:item.gameType="{ item }">
          <v-chip :color="getGameTypeColor(item?.gameType || item?.raw?.gameType)" size="small">
            {{ getGameTypeText(item?.gameType || item?.raw?.gameType) }}
          </v-chip>
        </template>

        <!-- 勝敗 -->
        <template v-slot:item.winLoss="{ item }">
          <v-chip :color="getWinLossColor(item?.winLoss || item?.raw?.winLoss)" size="small">
            {{ getWinLossText(item?.winLoss || item?.raw?.winLoss) }}
          </v-chip>
        </template>

        <!-- 自分 -->
        <template v-slot:item.ownPlayer="{ item }">
          <div v-if="item?.ownPlayer || item?.raw?.ownPlayer">
            <span v-if="(item?.ownPlayer || item?.raw?.ownPlayer)?.clanTag" class="text-primary">[{{ (item?.ownPlayer || item?.raw?.ownPlayer).clanTag }}]</span>
            {{ (item?.ownPlayer || item?.raw?.ownPlayer)?.name || '-' }}
            <div class="text-caption text-grey">{{ (item?.ownPlayer || item?.raw?.ownPlayer)?.shipName || '-' }}</div>
          </div>
        </template>

        <!-- 味方クラン -->
        <template v-slot:item.allies="{ item }">
          <v-chip
            v-if="(item?.gameType || item?.raw?.gameType) === 'clan' && (item?.allyMainClanTag || item?.raw?.allyMainClanTag)"
            size="small"
          >
            [{{ item?.allyMainClanTag ?? item?.raw?.allyMainClanTag }}]
          </v-chip>
          <span v-else>-</span>
        </template>

        <!-- 敵クラン -->
        <template v-slot:item.enemies="{ item }">
          <v-chip
            v-if="(item?.gameType || item?.raw?.gameType) === 'clan' && (item?.enemyMainClanTag || item?.raw?.enemyMainClanTag)"
            size="small"
            color="error"
          >
            [{{ item?.enemyMainClanTag ?? item?.raw?.enemyMainClanTag }}]
          </v-chip>
          <span v-else>-</span>
        </template>

        <!-- リプレイ数 -->
        <template v-slot:item.replayCount="{ item }">
          <v-chip size="small" color="info">
            {{ item?.replayCount ?? item?.raw?.replayCount ?? 1 }} 件
          </v-chip>
        </template>

        <!-- 展開時の詳細表示 -->
        <template v-slot:expanded-row="{ columns, item }">
          <tr>
            <td :colspan="columns.length">
              <match-detail-expansion :match="item" />
            </td>
          </tr>
        </template>
      </v-data-table>

      <!-- ページネーション -->
      <v-card-actions>
        <v-btn
          :disabled="!searchStore.hasPrevPage"
          @click="searchStore.prevPage()"
        >
          <v-icon>mdi-chevron-left</v-icon>
          前へ
        </v-btn>
        <v-spacer></v-spacer>
        <span>
          ページ {{ searchStore.currentPage }} / {{ searchStore.totalPages }}
        </span>
        <v-spacer></v-spacer>
        <v-btn
          :disabled="!searchStore.hasNextPage"
          @click="searchStore.nextPage()"
        >
          次へ
          <v-icon>mdi-chevron-right</v-icon>
        </v-btn>
      </v-card-actions>
    </v-card>
  </div>
</template>

<script setup lang="ts">
import { useSearchStore } from '~/stores/search'
import { useMapNames } from '~/composables/useMapNames'
import type { PlayerInfo } from '~/types/replay'

const searchStore = useSearchStore()
const { getMapName, getMapList } = useMapNames()

// マップ一覧
const mapList = getMapList()

// 初回検索
onMounted(async () => {
  await searchStore.search()
})

// フォーム選択肢
const gameTypes = [
  { text: 'すべて', value: '' },
  { text: 'クラン戦', value: 'clan' },
  { text: 'ランダム戦', value: 'pvp' },
  { text: 'ランク戦', value: 'ranked' },
]

const winLossTypes = [
  { text: 'すべて', value: '' },
  { text: '勝利', value: 'win' },
  { text: '敗北', value: 'loss' },
  { text: '引き分け', value: 'draw' },
]

// 展開状態の管理
const expanded = ref([])

const onExpandedChange = (newExpanded: any[]) => {
  expanded.value = newExpanded
}

// 行クリック時の展開トグル
const onRowClick = (_event: Event, { item }: { item: any }) => {
  const matchKey = item.matchKey
  const index = expanded.value.indexOf(matchKey)
  if (index === -1) {
    expanded.value = [...expanded.value, matchKey]
  } else {
    expanded.value = expanded.value.filter((key: string) => key !== matchKey)
  }
}

// ソート状態
const sortBy = ref([{ key: 'dateTime', order: 'desc' }])

// テーブルヘッダー
const headers = [
  { title: '日時', key: 'dateTime', sortable: true },
  { title: 'マップ', key: 'mapDisplayName', sortable: true },
  { title: 'ゲームタイプ', key: 'gameType', sortable: true },
  { title: '勝敗', key: 'winLoss', sortable: true },
  { title: '自分', key: 'ownPlayer', sortable: false },
  { title: '味方クラン', key: 'allies', sortable: false },
  { title: '敵クラン', key: 'enemies', sortable: false },
  { title: 'リプレイ数', key: 'replayCount', sortable: true },
]

// ソート済み結果
const sortedResults = computed(() => {
  const results = searchStore.results || []
  if (!sortBy.value.length) return results

  const { key, order } = sortBy.value[0]
  const sorted = [...results].sort((a, b) => {
    let aVal = a[key] ?? a?.raw?.[key]
    let bVal = b[key] ?? b?.raw?.[key]

    // 日時の場合は日付として比較
    if (key === 'dateTime') {
      aVal = parseDateTimeForSort(aVal)
      bVal = parseDateTimeForSort(bVal)
    }

    if (aVal < bVal) return order === 'asc' ? -1 : 1
    if (aVal > bVal) return order === 'asc' ? 1 : -1
    return 0
  })

  return sorted
})

// 日時をソート用に変換
const parseDateTimeForSort = (dateTime: string): number => {
  if (!dateTime) return 0

  // "04.01.2026 21:56:55" 形式
  const parts = dateTime.match(/(\d{2})\.(\d{2})\.(\d{4}) (\d{2}):(\d{2}):(\d{2})/)
  if (parts) {
    const [_, day, month, year, hour, minute, second] = parts
    return new Date(`${year}-${month}-${day}T${hour}:${minute}:${second}`).getTime()
  }

  // ISO形式
  const date = new Date(dateTime)
  return isNaN(date.getTime()) ? 0 : date.getTime()
}

// ハンドラー
const handleSearch = () => {
  searchStore.query.offset = 0
  searchStore.search()
}

const handleReset = () => {
  searchStore.resetQuery()
  searchStore.search()
}

// フォーマット関数
const formatDateTime = (dateTime: string) => {
  if (!dateTime) return '-'

  try {
    // "04.01.2026 21:56:55" 形式の日時を解析
    const parts = dateTime.match(/(\d{2})\.(\d{2})\.(\d{4}) (\d{2}):(\d{2}):(\d{2})/)
    if (parts) {
      const [_, day, month, year, hour, minute, second] = parts
      return `${year}/${month}/${day} ${hour}:${minute}:${second}`
    }

    // ISO形式の場合
    const date = new Date(dateTime)
    if (!isNaN(date.getTime())) {
      const year = date.getFullYear()
      const month = String(date.getMonth() + 1).padStart(2, '0')
      const day = String(date.getDate()).padStart(2, '0')
      const hour = String(date.getHours()).padStart(2, '0')
      const minute = String(date.getMinutes()).padStart(2, '0')
      const second = String(date.getSeconds()).padStart(2, '0')
      return `${year}/${month}/${day} ${hour}:${minute}:${second}`
    }
  } catch (e) {
    console.error('Date format error:', e)
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

// getAllyClanTags と getEnemyClanTags 関数は削除
// クラン戦の場合は allyMainClanTag と enemyMainClanTag を直接表示するため不要
</script>

<style scoped>
.clickable-rows :deep(tbody tr:not(.v-data-table__expanded__content)) {
  cursor: pointer;
}

.clickable-rows :deep(tbody tr:not(.v-data-table__expanded__content):hover) {
  background-color: rgba(var(--v-theme-primary), 0.08);
}
</style>
