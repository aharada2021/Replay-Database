<template>
  <div>
    <v-card class="mb-2" density="compact">
      <v-card-text class="py-2">
        <v-form @submit.prevent="handleSearch">
          <div class="search-filters">
            <!-- ゲームタイプ -->
            <div class="filter-item filter-item--medium">
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
            </div>

            <!-- マップ -->
            <div class="filter-item filter-item--wide">
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
            </div>

            <!-- 勝敗 -->
            <div class="filter-item filter-item--small">
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
            </div>

            <!-- 味方クランタグ -->
            <div class="filter-item filter-item--clan">
              <v-text-field
                v-model="searchStore.query.allyClanTag"
                label="味方クラン"
                clearable
                density="compact"
                hide-details
              ></v-text-field>
            </div>

            <!-- 敵クランタグ -->
            <div class="filter-item filter-item--clan">
              <v-text-field
                v-model="searchStore.query.enemyClanTag"
                label="敵クラン"
                clearable
                density="compact"
                hide-details
              ></v-text-field>
            </div>

            <!-- 艦艇名 -->
            <div class="filter-item filter-item--ship">
              <v-text-field
                v-model="searchStore.query.shipName"
                label="艦艇名"
                clearable
                density="compact"
                hide-details
              ></v-text-field>
            </div>

            <!-- 艦艇チーム -->
            <div class="filter-item filter-item--small">
              <v-select
                v-model="searchStore.query.shipTeam"
                :items="shipTeamTypes"
                label="チーム"
                clearable
                density="compact"
                hide-details
                item-title="text"
                item-value="value"
              ></v-select>
            </div>

            <!-- 艦艇最小数 -->
            <div class="filter-item filter-item--count">
              <v-select
                v-model="searchStore.query.shipMinCount"
                :items="shipCountOptions"
                label="隻数"
                density="compact"
                hide-details
                item-title="text"
                item-value="value"
              ></v-select>
            </div>

            <!-- 日時範囲 From -->
            <div class="filter-item filter-item--date">
              <v-text-field
                v-model="searchStore.query.dateFrom"
                label="From"
                clearable
                density="compact"
                hide-details
                type="date"
              ></v-text-field>
            </div>

            <!-- 日時範囲 To -->
            <div class="filter-item filter-item--date">
              <v-text-field
                v-model="searchStore.query.dateTo"
                label="To"
                clearable
                density="compact"
                hide-details
                type="date"
              ></v-text-field>
            </div>

            <!-- ボタン -->
            <div class="filter-item filter-item--buttons">
              <v-btn color="primary" type="submit" :loading="searchStore.loading" size="small" class="mr-1">
                <v-icon size="small">mdi-magnify</v-icon>
              </v-btn>
              <v-btn @click="handleReset" size="small">
                <v-icon size="small">mdi-refresh</v-icon>
              </v-btn>
            </div>
          </div>
        </v-form>
      </v-card-text>
    </v-card>

    <!-- 検索結果 -->
    <v-card>
      <v-data-table
        :headers="headers"
        :items="searchStore.results || []"
        :loading="searchStore.loading || false"
        :items-per-page="-1"
        hide-default-footer
        show-expand
        :expanded="expanded"
        @update:expanded="onExpandedChange"
        @click:row="onRowClick"
        item-value="matchKey"
        v-model:sort-by="sortBy"
        :custom-key-sort="customKeySort"
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

        <!-- 味方クラン -->
        <template v-slot:item.allyMainClanTag="{ item }">
          <span v-if="item?.allyMainClanTag || item?.raw?.allyMainClanTag" class="text-success font-weight-medium">
            [{{ item?.allyMainClanTag || item?.raw?.allyMainClanTag }}]
          </span>
          <span v-else class="text-grey">-</span>
        </template>

        <!-- 敵クラン -->
        <template v-slot:item.enemyMainClanTag="{ item }">
          <span v-if="item?.enemyMainClanTag || item?.raw?.enemyMainClanTag" class="text-error font-weight-medium">
            [{{ item?.enemyMainClanTag || item?.raw?.enemyMainClanTag }}]
          </span>
          <span v-else class="text-grey">-</span>
        </template>

        <!-- 自分 -->
        <template v-slot:item.ownPlayer="{ item }">
          <div v-if="item?.ownPlayer || item?.raw?.ownPlayer">
            <span v-if="(item?.ownPlayer || item?.raw?.ownPlayer)?.clanTag" class="text-primary">[{{ (item?.ownPlayer || item?.raw?.ownPlayer).clanTag }}]</span>
            {{ (item?.ownPlayer || item?.raw?.ownPlayer)?.name || '-' }}
            <div class="text-caption text-grey">{{ (item?.ownPlayer || item?.raw?.ownPlayer)?.shipName || '-' }}</div>
          </div>
        </template>

        <!-- 味方艦艇 -->
        <template v-slot:item.allyShips="{ item }">
          <div class="ship-list">
            <span
              v-for="(ship, idx) in getShipList(item?.allies || item?.raw?.allies)"
              :key="idx"
              class="ship-name text-caption"
            >{{ ship }}</span>
          </div>
        </template>

        <!-- 敵艦艇 -->
        <template v-slot:item.enemyShips="{ item }">
          <div class="ship-list ship-list--enemy">
            <span
              v-for="(ship, idx) in getShipList(item?.enemies || item?.raw?.enemies)"
              :key="idx"
              class="ship-name text-caption"
            >{{ ship }}</span>
          </div>
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
          ページ {{ searchStore.currentPage }}{{ searchStore.hasNextPage ? '+' : '' }}
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
  { text: 'コープ戦', value: 'cooperative' },
]

const winLossTypes = [
  { text: 'すべて', value: '' },
  { text: '勝利', value: 'win' },
  { text: '敗北', value: 'loss' },
  { text: '引き分け', value: 'draw' },
]

const shipTeamTypes = [
  { text: 'すべて', value: '' },
  { text: '味方', value: 'ally' },
  { text: '敵', value: 'enemy' },
]

const shipCountOptions = [
  { text: '1隻以上', value: 1 },
  { text: '2隻以上', value: 2 },
  { text: '3隻以上', value: 3 },
  { text: '4隻以上', value: 4 },
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

// カスタムソート関数（日時用）
const customKeySort = {
  dateTime: (a: string, b: string) => {
    const aTime = parseDateTimeForSort(a)
    const bTime = parseDateTimeForSort(b)
    return aTime - bTime
  }
}

// テーブルヘッダー
const headers = [
  { title: '日時', key: 'dateTime', sortable: true },
  { title: 'マップ', key: 'mapDisplayName', sortable: true },
  { title: 'ゲームタイプ', key: 'gameType', sortable: true },
  { title: '勝敗', key: 'winLoss', sortable: true },
  { title: '味方クラン', key: 'allyMainClanTag', sortable: true },
  { title: '敵クラン', key: 'enemyMainClanTag', sortable: true },
  { title: '初回アップロード者', key: 'ownPlayer', sortable: false },
  { title: '味方艦艇', key: 'allyShips', sortable: false },
  { title: '敵艦艇', key: 'enemyShips', sortable: false },
]

// ハンドラー
const handleSearch = () => {
  searchStore.search()  // resetPagination=true がデフォルト
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
    cooperative: 'コープ',
  }
  return types[type] || type
}

const getGameTypeColor = (type: string) => {
  const colors: Record<string, string> = {
    clan: 'purple',
    pvp: 'blue',
    ranked: 'orange',
    cooperative: 'green',
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

// 艦艇リストを取得（艦名のみの配列を返す）
const getShipList = (players: PlayerInfo[] | undefined): string[] => {
  if (!players || players.length === 0) return []
  return players.map(p => p.shipName || '-').filter(Boolean)
}
</script>

<style scoped>
.clickable-rows :deep(tbody tr:not(.v-data-table__expanded__content)) {
  cursor: pointer;
}

.clickable-rows :deep(tbody tr:not(.v-data-table__expanded__content):hover) {
  background-color: rgba(var(--v-theme-primary), 0.08);
}

/* 検索フィルターのレイアウト */
.search-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.filter-item {
  flex-shrink: 0;
}

/* サイズバリエーション */
.filter-item--small {
  width: 145px;
}

.filter-item--medium {
  width: 170px;
}

.filter-item--wide {
  width: 220px;
}

.filter-item--clan {
  width: 120px;
}

.filter-item--ship {
  width: 160px;
}

.filter-item--count {
  width: 100px;
}

.filter-item--date {
  width: 185px;
}

.filter-item--buttons {
  display: flex;
  gap: 4px;
}

/* モバイル対応 */
@media (max-width: 960px) {
  .filter-item--small,
  .filter-item--medium,
  .filter-item--wide,
  .filter-item--clan,
  .filter-item--ship,
  .filter-item--count,
  .filter-item--date {
    width: calc(50% - 4px);
    min-width: 120px;
  }

  .filter-item--buttons {
    width: 100%;
    justify-content: flex-end;
  }
}

@media (max-width: 600px) {
  .filter-item--small,
  .filter-item--medium,
  .filter-item--wide,
  .filter-item--clan,
  .filter-item--ship,
  .filter-item--count,
  .filter-item--date {
    width: 100%;
  }
}

/* 艦艇リスト表示 */
.ship-list {
  display: flex;
  flex-wrap: wrap;
  gap: 2px 6px;
  max-width: 200px;
}

.ship-list .ship-name {
  color: rgba(var(--v-theme-success), 0.9);
}

.ship-list--enemy .ship-name {
  color: rgba(var(--v-theme-error), 0.9);
}
</style>
