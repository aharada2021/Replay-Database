import { defineStore } from 'pinia'
import type { SearchQuery, MatchRecord } from '~/types/replay'

export const useSearchStore = defineStore('search', {
  state: () => ({
    query: {
      gameType: '',
      mapId: '',
      playerName: '',
      enemyShipName: '',
      winLoss: '',
      dateFrom: '',
      dateTo: '',
      limit: 50,
      offset: 0,
    } as SearchQuery,
    results: [] as MatchRecord[],
    loading: false,
    error: null as string | null,
    totalCount: 0,
  }),

  actions: {
    updateQuery(newQuery: Partial<SearchQuery>) {
      this.query = { ...this.query, ...newQuery }
    },

    resetQuery() {
      this.query = {
        gameType: '',
        mapId: '',
        playerName: '',
        enemyShipName: '',
        winLoss: '',
        dateFrom: '',
        dateTo: '',
        limit: 50,
        offset: 0,
      }
    },

    async search() {
      console.log('[Store] Starting search with query:', this.query)
      this.loading = true
      this.error = null

      try {
        const api = useApi()
        console.log('[Store] Calling API...')
        const response = await api.searchReplays(this.query)
        console.log('[Store] API response:', response)
        console.log('[Store] Items count:', response.items?.length)

        this.results = response.items
        this.totalCount = response.count

        console.log('[Store] State updated - results:', this.results?.length, 'totalCount:', this.totalCount)
      } catch (err: any) {
        console.error('[Store] Search error:', err)
        this.error = err.message || 'Search failed'
        this.results = []
        this.totalCount = 0
      } finally {
        this.loading = false
        console.log('[Store] Search completed, loading:', this.loading)
      }
    },

    nextPage() {
      this.query.offset = (this.query.offset || 0) + (this.query.limit || 50)
      this.search()
    },

    prevPage() {
      const newOffset = (this.query.offset || 0) - (this.query.limit || 50)
      this.query.offset = Math.max(0, newOffset)
      this.search()
    },
  },

  getters: {
    currentPage: (state) => {
      const offset = state.query.offset || 0
      const limit = state.query.limit || 50
      return Math.floor(offset / limit) + 1
    },

    totalPages: (state) => {
      const limit = state.query.limit || 50
      return Math.ceil(state.totalCount / limit)
    },

    hasNextPage: (state) => {
      const offset = state.query.offset || 0
      return offset + (state.query.limit || 50) < state.totalCount
    },

    hasPrevPage: (state) => {
      return (state.query.offset || 0) > 0
    },
  },
})
