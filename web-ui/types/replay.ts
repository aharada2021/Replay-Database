/**
 * リプレイデータの型定義
 */

export interface PlayerInfo {
  name: string
  shipId: number
  shipName: string
  clanTag?: string
  relation?: string
}

export interface ReplayRecord {
  arenaUniqueID: string
  playerID: number
  playerName: string
  uploadedBy: string
  uploadedAt: string

  // 試合情報
  dateTime: string
  mapId: string
  mapDisplayName: string
  gameType: 'clan' | 'pvp' | 'ranked' | 'brawl' | string
  clientVersion: string

  // 勝敗情報
  winLoss?: 'win' | 'loss' | 'draw' | 'unknown'
  experienceEarned?: number

  // プレイヤー情報
  ownPlayer: PlayerInfo
  allies: PlayerInfo[]
  enemies: PlayerInfo[]

  // ファイル情報
  s3Key: string
  fileName: string
  fileSize: number

  // 動画情報
  mp4GeneratedAt?: string
  mp4S3Key?: string
}

export interface SearchQuery {
  gameType?: string
  mapId?: string
  playerName?: string
  enemyShipName?: string
  winLoss?: string
  dateFrom?: string
  dateTo?: string
  limit?: number
  offset?: number
}

export interface SearchResponse {
  items: ReplayRecord[]
  count: number
  scannedCount?: number
  lastEvaluatedKey?: any
}

export interface GenerateVideoRequest {
  arenaUniqueID: string
  playerID: number
}

export interface GenerateVideoResponse {
  status: 'generated' | 'already_exists' | 'generating'
  videoUrl?: string
  mp4S3Key?: string
  expiresIn?: number
}

export interface MapInfo {
  id: number
  name: string
  displayName: string
}

export interface ShipInfo {
  id: number
  name: string
  tier?: number
  type?: string
}
