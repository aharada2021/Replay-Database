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
    console.log('[API] searchReplays called with query:', query)
    console.log('[API] Base URL:', baseUrl)

    try {
      const url = `${baseUrl}/api/search`
      console.log('[API] Fetching:', url)

      const response = await $fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(query),
      })

      console.log('[API] Raw response:', response)
      console.log('[API] Response type:', typeof response)

      // レスポンスが文字列の場合、JSONをパース
      let parsedResponse: SearchResponse
      if (typeof response === 'string') {
        console.log('[API] Parsing JSON string...')
        parsedResponse = JSON.parse(response)
      } else {
        parsedResponse = response as SearchResponse
      }

      console.log('[API] Parsed response:', parsedResponse)
      console.log('[API] Response.items:', parsedResponse?.items)
      console.log('[API] Response.count:', parsedResponse?.count)

      return parsedResponse
    } catch (error) {
      console.error('[API] Search error:', error)
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
    console.log('[API] getReplayDetail called:', { arenaUniqueID, playerID })

    try {
      // 全件取得して該当レコードを探す
      // TODO: DynamoDB GetItemを使用する専用APIを作成すると効率的
      const response = await searchReplays({
        limit: 1000, // 全件取得
      })

      console.log('[API] Search response for detail:', response.items.length, 'items')

      // 検索結果から該当レコードを探す
      const record = response.items.find((item) => {
        const itemArenaId = String(item.arenaUniqueID)
        const searchArenaId = String(arenaUniqueID)
        const itemPlayerId = Number(item.playerID)
        const searchPlayerId = Number(playerID)

        return itemArenaId === searchArenaId && itemPlayerId === searchPlayerId
      })

      console.log('[API] Found record:', record ? 'yes' : 'no')
      if (record) {
        console.log('[API] Record details:', record)
      } else {
        console.log('[API] Looking for:', { arenaUniqueID, playerID })
        console.log('[API] Available items:', response.items.map(i => ({ arenaUniqueID: i.arenaUniqueID, playerID: i.playerID })))
      }

      return record || null
    } catch (error) {
      console.error('[API] Get detail error:', error)
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
