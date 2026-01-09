import { defineStore } from 'pinia'
import type { SearchQuery, MatchRecord } from '~/types/replay'

// 固定の表示件数
const ITEMS_PER_PAGE = 30

export const useSearchStore = defineStore('search', {
  state: () => ({
    query: {
      gameType: 'clan',  // デフォルトでクラン戦を選択
      mapId: '',
      allyClanTag: '',
      enemyClanTag: '',
      shipName: '',
      shipTeam: '',
      shipMinCount: 1,
      playerName: '',  // プレイヤー名検索
      winLoss: '',
      dateFrom: '',
      dateTo: '',
      limit: ITEMS_PER_PAGE,
      cursorDateTime: null as string | null,
    } as SearchQuery,
    results: [] as MatchRecord[],
    loading: false,
    error: null as string | null,
    totalCount: 0,
    // ページング用の状態
    currentPageNum: 1,
    cursorHistory: [] as (string | null)[],  // 各ページのカーソルを保存
    cursorFromResponse: null as string | null,  // 最新のレスポンスからのカーソル
    hasMoreFromResponse: false,  // 次のページがあるか
  }),

  actions: {
    updateQuery(newQuery: Partial<SearchQuery>) {
      this.query = { ...this.query, ...newQuery }
    },

    resetQuery() {
      this.query = {
        gameType: 'clan',  // デフォルトでクラン戦を選択
        mapId: '',
        allyClanTag: '',
        enemyClanTag: '',
        shipName: '',
        shipTeam: '',
        shipMinCount: 1,
        playerName: '',  // プレイヤー名検索
        winLoss: '',
        dateFrom: '',
        dateTo: '',
        limit: ITEMS_PER_PAGE,
        cursorDateTime: null,
      }
      this.currentPageNum = 1
      this.cursorHistory = []
      this.cursorFromResponse = null
      this.hasMoreFromResponse = false
    },

    async search(resetPagination: boolean = true) {
      this.loading = true
      this.error = null

      // 新規検索の場合はページング状態をリセット
      if (resetPagination) {
        this.currentPageNum = 1
        this.cursorHistory = []
        this.query.cursorDateTime = null
      }

      try {
        const api = useApi()
        const response = await api.searchReplays(this.query)

        this.results = response.items
        this.totalCount = response.count
        this.cursorFromResponse = response.cursorDateTime || null
        this.hasMoreFromResponse = response.hasMore || false
      } catch (err: any) {
        console.error('[Store] Search error:', err)
        this.error = err.message || 'Search failed'
        this.results = []
        this.totalCount = 0
        this.cursorFromResponse = null
        this.hasMoreFromResponse = false
      } finally {
        this.loading = false
      }
    },

    async nextPage() {
      if (!this.hasNextPage) return

      // 現在のカーソルを履歴に保存（戻るボタン用）
      this.cursorHistory.push(this.query.cursorDateTime)

      // 次のページのカーソルを設定
      this.query.cursorDateTime = this.cursorFromResponse
      this.currentPageNum++

      await this.search(false)
    },

    async prevPage() {
      if (!this.hasPrevPage) return

      this.currentPageNum--

      // 履歴から前のページのカーソルを取得
      if (this.cursorHistory.length > 0) {
        this.query.cursorDateTime = this.cursorHistory.pop() || null
      } else {
        this.query.cursorDateTime = null
      }

      await this.search(false)
    },
  },

  getters: {
    currentPage: (state) => state.currentPageNum,

    totalPages: (state) => {
      // カーソルベースのページングでは総ページ数は不明
      // hasMoreがtrueなら少なくとも次のページがある
      if (state.hasMoreFromResponse) {
        return state.currentPageNum + 1  // 最低でも次のページがある
      }
      return state.currentPageNum
    },

    hasNextPage: (state) => {
      // レスポンスのhasMoreフラグを使用
      return state.hasMoreFromResponse
    },

    hasPrevPage: (state) => {
      return state.currentPageNum > 1
    },
  },
})
