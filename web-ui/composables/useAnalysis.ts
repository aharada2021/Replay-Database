import type {
  AnalyzeRequest,
  AnalyzeResponse,
  AnalyzeError,
} from '~/types/replay'

/**
 * Claude AI データ分析 composable
 */
export const useAnalysis = () => {
  const config = useRuntimeConfig()
  const baseUrl = config.public.apiBaseUrl

  /**
   * 戦闘データを分析
   */
  const analyzeData = async (params: AnalyzeRequest): Promise<AnalyzeResponse> => {
    try {
      const url = `${baseUrl}/api/analyze`

      const response = await $fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(params),
        credentials: 'include', // セッションCookieを送信
      })

      // レスポンスが文字列の場合、JSONをパース
      let parsedResponse: AnalyzeResponse
      if (typeof response === 'string') {
        parsedResponse = JSON.parse(response)
      } else {
        parsedResponse = response as AnalyzeResponse
      }

      return parsedResponse
    } catch (error: unknown) {
      console.error('[Analysis] Analyze error:', error)

      // FetchErrorの場合、レスポンスからエラー情報を取得
      if (error && typeof error === 'object' && 'data' in error) {
        const errorData = (error as { data: AnalyzeError }).data
        if (errorData?.error) {
          throw new Error(errorData.error)
        }
      }

      throw error
    }
  }

  return {
    analyzeData,
  }
}
