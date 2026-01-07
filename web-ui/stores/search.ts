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
      winLoss: '',
      dateFrom: '',
      dateTo: '',
      limit: ITEMS_PER_PAGE,
      lastEvaluatedKey: null as any,
    } as SearchQuery,
    results: [] as MatchRecord[],
    loading: false,
    error: null as string | null,
    totalCount: 0,
    // ページング用の状態
    currentPageNum: 1,
    lastEvaluatedKeyHistory: [] as any[],  // 各ページのlastEvaluatedKeyを保存
    lastEvaluatedKeyFromResponse: null as any,  // 最新のレスポンスからのlastEvaluatedKey
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
        winLoss: '',
        dateFrom: '',
        dateTo: '',
        limit: ITEMS_PER_PAGE,
        lastEvaluatedKey: null,
      }
      this.currentPageNum = 1
      this.lastEvaluatedKeyHistory = []
      this.lastEvaluatedKeyFromResponse = null
    },

    async search(resetPagination: boolean = true) {
      this.loading = true
      this.error = null

      // 新規検索の場合はページング状態をリセット
      if (resetPagination) {
        this.currentPageNum = 1
        this.lastEvaluatedKeyHistory = []
        this.query.lastEvaluatedKey = null
      }

      try {
        const api = useApi()
        const response = await api.searchReplays(this.query)

        this.results = response.items
        this.totalCount = response.count
        this.lastEvaluatedKeyFromResponse = response.lastEvaluatedKey || null
      } catch (err: any) {
        console.error('[Store] Search error:', err)
        this.error = err.message || 'Search failed'
        this.results = []
        this.totalCount = 0
        this.lastEvaluatedKeyFromResponse = null
      } finally {
        this.loading = false
      }
    },

    async nextPage() {
      if (!this.hasNextPage) return

      // 現在のlastEvaluatedKeyを履歴に保存（戻るボタン用）
      this.lastEvaluatedKeyHistory.push(this.query.lastEvaluatedKey)

      // 次のページのキーを設定
      this.query.lastEvaluatedKey = this.lastEvaluatedKeyFromResponse
      this.currentPageNum++

      await this.search(false)
    },

    async prevPage() {
      if (!this.hasPrevPage) return

      this.currentPageNum--

      // 履歴から前のページのキーを取得
      if (this.lastEvaluatedKeyHistory.length > 0) {
        this.query.lastEvaluatedKey = this.lastEvaluatedKeyHistory.pop()
      } else {
        this.query.lastEvaluatedKey = null
      }

      await this.search(false)
    },
  },

  getters: {
    currentPage: (state) => state.currentPageNum,

    totalPages: (state) => {
      // カーソルベースのページングでは総ページ数は不明
      // hasNextPageがtrueなら少なくとも次のページがある
      if (state.lastEvaluatedKeyFromResponse) {
        return state.currentPageNum + 1  // 最低でも次のページがある
      }
      return state.currentPageNum
    },

    hasNextPage: (state) => {
      // レスポンスにlastEvaluatedKeyがあれば次のページがある
      return !!state.lastEvaluatedKeyFromResponse
    },

    hasPrevPage: (state) => {
      return state.currentPageNum > 1
    },
  },
})
