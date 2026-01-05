import type {
  SearchQuery,
  SearchResponse,
  ReplayRecord,
  GenerateVideoRequest,
  GenerateVideoResponse,
} from '~/types/replay'

export const useApi = () => {
  const config = useRuntimeConfig()
  const baseUrl = config.public.apiBaseUrl

  /**
   * リプレイ検索
   */
  const searchReplays = async (query: SearchQuery): Promise<SearchResponse> => {
    try {
      const response = await $fetch<SearchResponse>(`${baseUrl}/api/search`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(query),
      })
      return response
    } catch (error) {
      console.error('Search error:', error)
      throw error
    }
  }

  /**
   * リプレイ詳細取得
   */
  const getReplayDetail = async (
    arenaUniqueID: string,
    playerID: number
  ): Promise<ReplayRecord | null> => {
    try {
      const response = await searchReplays({
        limit: 1,
      })

      // 検索結果から該当レコードを探す
      const record = response.items.find(
        (item) => item.arenaUniqueID === arenaUniqueID && item.playerID === playerID
      )

      return record || null
    } catch (error) {
      console.error('Get detail error:', error)
      return null
    }
  }

  /**
   * MP4動画生成
   */
  const generateVideo = async (
    request: GenerateVideoRequest
  ): Promise<GenerateVideoResponse> => {
    try {
      const response = await $fetch<GenerateVideoResponse>(
        `${baseUrl}/api/generate-video`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(request),
        }
      )
      return response
    } catch (error) {
      console.error('Generate video error:', error)
      throw error
    }
  }

  /**
   * リプレイファイルのダウンロードURL取得
   */
  const getReplayDownloadUrl = (s3Key: string): string => {
    // S3の署名付きURLを生成するAPIが必要
    // 今は仮実装
    return `${baseUrl}/api/download?key=${encodeURIComponent(s3Key)}`
  }

  return {
    searchReplays,
    getReplayDetail,
    generateVideo,
    getReplayDownloadUrl,
  }
}
