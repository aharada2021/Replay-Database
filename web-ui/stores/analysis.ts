import { defineStore } from 'pinia'
import type {
  AnalyzeRequest,
  AnalyzeResponse,
  AnalysisHistoryItem,
} from '~/types/replay'

// ローカルストレージのキー
const HISTORY_STORAGE_KEY = 'analysis_history'
const MAX_HISTORY_ITEMS = 10

export const useAnalysisStore = defineStore('analysis', {
  state: () => ({
    query: '',
    gameType: '' as string,
    dateFrom: '',
    dateTo: '',
    response: null as AnalyzeResponse | null,
    loading: false,
    error: null as string | null,
    history: [] as AnalysisHistoryItem[],
  }),

  actions: {
    /**
     * 分析を実行
     */
    async analyze() {
      if (!this.query.trim()) {
        this.error = '質問を入力してください'
        return
      }

      this.loading = true
      this.error = null
      this.response = null

      try {
        const { analyzeData } = useAnalysis()

        const params: AnalyzeRequest = {
          query: this.query.trim(),
        }

        if (this.gameType) {
          params.gameType = this.gameType
        }

        if (this.dateFrom && this.dateTo) {
          params.dateRange = {
            from: this.dateFrom,
            to: this.dateTo,
          }
        }

        const response = await analyzeData(params)
        this.response = response

        // 履歴に追加
        this.addToHistory({
          query: this.query.trim(),
          response,
          timestamp: new Date().toISOString(),
        })
      } catch (err: unknown) {
        console.error('[Analysis] Error:', err)
        if (err instanceof Error) {
          this.error = err.message
        } else {
          this.error = '分析中にエラーが発生しました'
        }
      } finally {
        this.loading = false
      }
    },

    /**
     * 履歴に追加
     */
    addToHistory(item: AnalysisHistoryItem) {
      // 重複チェック（同じクエリが直前にある場合はスキップ）
      if (this.history.length > 0 && this.history[0].query === item.query) {
        this.history[0] = item // 更新
      } else {
        this.history.unshift(item)
      }

      // 最大件数を超えた場合は古いものを削除
      if (this.history.length > MAX_HISTORY_ITEMS) {
        this.history = this.history.slice(0, MAX_HISTORY_ITEMS)
      }

      // ローカルストレージに保存
      this.saveHistoryToStorage()
    },

    /**
     * 履歴をローカルストレージに保存
     */
    saveHistoryToStorage() {
      try {
        localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(this.history))
      } catch (err) {
        console.error('[Analysis] Failed to save history:', err)
      }
    },

    /**
     * 履歴をローカルストレージから読み込み
     */
    loadHistoryFromStorage() {
      try {
        const saved = localStorage.getItem(HISTORY_STORAGE_KEY)
        if (saved) {
          this.history = JSON.parse(saved)
        }
      } catch (err) {
        console.error('[Analysis] Failed to load history:', err)
        this.history = []
      }
    },

    /**
     * 履歴からクエリを復元
     */
    restoreFromHistory(item: AnalysisHistoryItem) {
      this.query = item.query
      this.response = item.response
    },

    /**
     * 履歴をクリア
     */
    clearHistory() {
      this.history = []
      this.saveHistoryToStorage()
    },

    /**
     * 状態をリセット
     */
    reset() {
      this.query = ''
      this.gameType = ''
      this.dateFrom = ''
      this.dateTo = ''
      this.response = null
      this.error = null
    },
  },

  getters: {
    /**
     * 残りクエリ数
     */
    remainingQueries: (state) => {
      return state.response?.remainingQueries ?? null
    },

    /**
     * 分析結果があるか
     */
    hasResponse: (state) => {
      return state.response !== null && state.response.analysis.length > 0
    },

    /**
     * 履歴があるか
     */
    hasHistory: (state) => {
      return state.history.length > 0
    },
  },
})
