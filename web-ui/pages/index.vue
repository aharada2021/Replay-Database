<template>
  <div>
    <v-card class="mb-4">
      <v-card-title>リプレイ検索</v-card-title>
      <v-card-text>
        <v-form @submit.prevent="handleSearch">
          <v-row>
            <!-- ゲームタイプ -->
            <v-col cols="12" md="3">
              <v-select
                v-model="searchStore.query.gameType"
                :items="gameTypes"
                label="ゲームタイプ"
                clearable
                item-title="text"
                item-value="value"
              ></v-select>
            </v-col>

            <!-- マップ -->
            <v-col cols="12" md="3">
              <v-select
                v-model="searchStore.query.mapId"
                :items="mapList"
                label="マップ"
                clearable
                item-title="text"
                item-value="value"
              ></v-select>
            </v-col>

            <!-- 勝敗 -->
            <v-col cols="12" md="3">
              <v-select
                v-model="searchStore.query.winLoss"
                :items="winLossTypes"
                label="勝敗"
                clearable
                item-title="text"
                item-value="value"
              ></v-select>
            </v-col>

            <!-- 味方クランタグ -->
            <v-col cols="12" md="3">
              <v-text-field
                v-model="searchStore.query.allyClanTag"
                label="味方クランタグ"
                clearable
                hint="クラン戦のみ有効"
              ></v-text-field>
            </v-col>

            <!-- 敵クランタグ -->
            <v-col cols="12" md="3">
              <v-text-field
                v-model="searchStore.query.enemyClanTag"
                label="敵クランタグ"
                clearable
                hint="クラン戦のみ有効"
              ></v-text-field>
            </v-col>

            <!-- 日時範囲 From -->
            <v-col cols="12" md="3">
              <v-text-field
                v-model="searchStore.query.dateFrom"
                label="日時From"
                clearable
                type="date"
              ></v-text-field>
            </v-col>

            <!-- 日時範囲 To -->
            <v-col cols="12" md="3">
              <v-text-field
                v-model="searchStore.query.dateTo"
                label="日時To"
                clearable
                type="date"
              ></v-text-field>
            </v-col>
          </v-row>

          <v-row>
            <v-col>
              <v-btn color="primary" type="submit" :loading="searchStore.loading">
                <v-icon left>mdi-magnify</v-icon>
                検索
              </v-btn>
              <v-btn class="ml-2" @click="handleReset">
                <v-icon left>mdi-refresh</v-icon>
                リセット
              </v-btn>
            </v-col>
          </v-row>
        </v-form>
      </v-card-text>
    </v-card>

    <!-- 検索結果 -->
    <v-card>
      <v-card-title>
        検索結果
        <v-spacer></v-spacer>
        <span class="text-caption">{{ searchStore.totalCount }} 件</span>
      </v-card-title>

      <v-data-table
        :headers="headers"
        :items="searchStore.results || []"
        :loading="searchStore.loading || false"
        :items-per-page="searchStore.query?.limit || 50"
        hide-default-footer
        show-expand
        :expanded="expanded"
        @update:expanded="onExpandedChange"
      >
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

// Store初期化確認
console.log('SearchStore initialized:', searchStore)
console.log('Initial state - results:', searchStore.results)
console.log('Initial state - loading:', searchStore.loading)
console.log('Initial state - error:', searchStore.error)

// 初回検索
onMounted(async () => {
  console.log('Mounted, starting search...')
  console.log('Store before search:', {
    results: searchStore.results,
    loading: searchStore.loading,
    error: searchStore.error
  })

  await searchStore.search()

  console.log('Search completed')
  console.log('Store after search:', {
    results: searchStore.results,
    resultsLength: searchStore.results?.length,
    loading: searchStore.loading,
    totalCount: searchStore.totalCount,
    error: searchStore.error
  })

  if (searchStore.results && searchStore.results.length > 0) {
    console.log('First item:', searchStore.results[0])
  }
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

// テーブルヘッダー
const headers = [
  { title: '日時', key: 'dateTime', sortable: false },
  { title: 'マップ', key: 'mapDisplayName', sortable: false },
  { title: 'ゲームタイプ', key: 'gameType', sortable: false },
  { title: '勝敗', key: 'winLoss', sortable: false },
  { title: '自分', key: 'ownPlayer', sortable: false },
  { title: '味方クラン', key: 'allies', sortable: false },
  { title: '敵クラン', key: 'enemies', sortable: false },
  { title: 'リプレイ数', key: 'replayCount', sortable: false },
]

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
