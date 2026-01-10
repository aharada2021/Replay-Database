import type {
  SearchQuery,
  SearchResponse,
  ReplayRecord,
  MatchDetailResponse,
  GenerateVideoRequest,
  GenerateVideoResponse,
  Comment,
} from '~/types/replay'

export const useApi = () => {
  const config = useRuntimeConfig()
  const baseUrl = config.public.apiBaseUrl

  /**
   * リプレイ検索
   */
  const searchReplays = async (query: SearchQuery): Promise<SearchResponse> => {
    try {
      const url = `${baseUrl}/api/search`

      const response = await $fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(query),
      })

      // レスポンスが文字列の場合、JSONをパース
      let parsedResponse: SearchResponse
      if (typeof response === 'string') {
        parsedResponse = JSON.parse(response)
      } else {
        parsedResponse = response as SearchResponse
      }

      return parsedResponse
    } catch (error) {
      console.error('[API] Search error:', error)
      throw error
    }
  }

  /**
   * 試合詳細取得（全リプレイを含む）
   */
  const getMatchDetail = async (
    arenaUniqueID: string
  ): Promise<MatchDetailResponse | null> => {
    try {
      const url = `${baseUrl}/api/match/${encodeURIComponent(arenaUniqueID)}`

      const response = await $fetch(url, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      })

      // レスポンスが文字列の場合、JSONをパース
      let parsedResponse: MatchDetailResponse
      if (typeof response === 'string') {
        parsedResponse = JSON.parse(response)
      } else {
        parsedResponse = response as MatchDetailResponse
      }

      return parsedResponse
    } catch (error) {
      console.error('[API] Get match detail error:', error)
      return null
    }
  }

  /**
   * リプレイ詳細取得（後方互換性のため残す）
   */
  const getReplayDetail = async (
    arenaUniqueID: string,
    playerID: number
  ): Promise<ReplayRecord | null> => {
    try {
      // 試合詳細を取得
      const matchDetail = await getMatchDetail(arenaUniqueID)
      if (!matchDetail) {
        return null
      }

      // 該当するリプレイを探す
      const replay = matchDetail.replays.find((r) => r.playerID === playerID)
      if (!replay) {
        return null
      }

      // ReplayRecord形式に変換
      const record: ReplayRecord = {
        arenaUniqueID: matchDetail.arenaUniqueID,
        playerID: replay.playerID,
        playerName: replay.playerName,
        uploadedBy: replay.uploadedBy,
        uploadedAt: replay.uploadedAt,
        dateTime: matchDetail.dateTime,
        mapId: matchDetail.mapId,
        mapDisplayName: matchDetail.mapDisplayName,
        gameType: matchDetail.gameType,
        clientVersion: matchDetail.clientVersion,
        winLoss: matchDetail.winLoss,
        experienceEarned: matchDetail.experienceEarned,
        ownPlayer: replay.ownPlayer || matchDetail.ownPlayer,
        allies: matchDetail.allies,
        enemies: matchDetail.enemies,
        s3Key: replay.s3Key,
        fileName: replay.fileName,
        fileSize: replay.fileSize,
        mp4S3Key: replay.mp4S3Key,
        mp4GeneratedAt: replay.mp4GeneratedAt,
      }

      return record
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

  /**
   * コメント一覧取得
   */
  const getComments = async (arenaUniqueID: string): Promise<Comment[]> => {
    try {
      const url = `${baseUrl}/api/comments/${encodeURIComponent(arenaUniqueID)}`

      const response = await $fetch(url, {
        method: 'GET',
        credentials: 'include',
      })

      let parsedResponse: { comments: Comment[] }
      if (typeof response === 'string') {
        parsedResponse = JSON.parse(response)
      } else {
        parsedResponse = response as { comments: Comment[] }
      }

      return parsedResponse.comments || []
    } catch (error) {
      console.error('[API] Get comments error:', error)
      return []
    }
  }

  /**
   * コメント投稿
   */
  const postComment = async (
    arenaUniqueID: string,
    content: string
  ): Promise<Comment | null> => {
    try {
      const url = `${baseUrl}/api/comments/${encodeURIComponent(arenaUniqueID)}`

      const response = await $fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({ content }),
      })

      let parsedResponse: Comment
      if (typeof response === 'string') {
        parsedResponse = JSON.parse(response)
      } else {
        parsedResponse = response as Comment
      }

      return parsedResponse
    } catch (error) {
      console.error('[API] Post comment error:', error)
      throw error
    }
  }

  /**
   * コメント編集
   */
  const updateComment = async (
    arenaUniqueID: string,
    commentId: string,
    content: string
  ): Promise<Comment | null> => {
    try {
      const url = `${baseUrl}/api/comments/${encodeURIComponent(arenaUniqueID)}/${encodeURIComponent(commentId)}`

      const response = await $fetch(url, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({ content }),
      })

      let parsedResponse: Comment
      if (typeof response === 'string') {
        parsedResponse = JSON.parse(response)
      } else {
        parsedResponse = response as Comment
      }

      return parsedResponse
    } catch (error) {
      console.error('[API] Update comment error:', error)
      throw error
    }
  }

  /**
   * コメント削除
   */
  const deleteComment = async (
    arenaUniqueID: string,
    commentId: string
  ): Promise<void> => {
    try {
      const url = `${baseUrl}/api/comments/${encodeURIComponent(arenaUniqueID)}/${encodeURIComponent(commentId)}`

      await $fetch(url, {
        method: 'DELETE',
        credentials: 'include',
      })
    } catch (error) {
      console.error('[API] Delete comment error:', error)
      throw error
    }
  }

  /**
   * コメントいいね（トグル）
   */
  const likeComment = async (
    arenaUniqueID: string,
    commentId: string
  ): Promise<Comment | null> => {
    try {
      const url = `${baseUrl}/api/comments/${encodeURIComponent(arenaUniqueID)}/${encodeURIComponent(commentId)}/like`

      const response = await $fetch(url, {
        method: 'POST',
        credentials: 'include',
      })

      let parsedResponse: Comment
      if (typeof response === 'string') {
        parsedResponse = JSON.parse(response)
      } else {
        parsedResponse = response as Comment
      }

      return parsedResponse
    } catch (error) {
      console.error('[API] Like comment error:', error)
      throw error
    }
  }

  return {
    searchReplays,
    getMatchDetail,
    getReplayDetail,
    generateVideo,
    getReplayDownloadUrl,
    getComments,
    postComment,
    updateComment,
    deleteComment,
    likeComment,
  }
}
