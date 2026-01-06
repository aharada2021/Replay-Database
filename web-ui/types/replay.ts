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

export interface BattleStats {
  // 基本統計
  damage?: number
  receivedDamage?: number
  spottingDamage?: number
  potentialDamage?: number
  kills?: number
  fires?: number
  floods?: number
  baseXP?: number
  // 命中数内訳
  hitsAP?: number
  hitsHE?: number
  hitsSecondaries?: number
  // ダメージ内訳
  damageAP?: number
  damageHE?: number
  damageHESecondaries?: number
  damageTorps?: number
  damageDeepWaterTorps?: number
  damageOther?: number
  damageFire?: number
  damageFlooding?: number
}

export interface ReplayProvider extends BattleStats {
  arenaUniqueID: string
  playerID: number
  playerName: string
  uploadedBy: string
  uploadedAt: string
  s3Key: string
  fileName: string
  fileSize: number
  mp4S3Key?: string
  mp4GeneratedAt?: string
  ownPlayer?: PlayerInfo
}

export interface MatchRecord extends BattleStats {
  arenaUniqueID: string

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

  // クラン情報（クラン戦のみ）
  allyMainClanTag?: string
  enemyMainClanTag?: string

  // リプレイ提供者情報
  replays: ReplayProvider[]
  replayCount: number

  // 代表リプレイ情報（一覧表示用）
  representativePlayerID?: number
  representativePlayerName?: string
  uploadedBy?: string
  uploadedAt?: string
  s3Key?: string
  fileName?: string
  fileSize?: number
  mp4S3Key?: string
  mp4GeneratedAt?: string
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
  allyClanTag?: string
  enemyClanTag?: string
  winLoss?: string
  dateFrom?: string
  dateTo?: string
  limit?: number
  offset?: number
}

export interface SearchResponse {
  items: MatchRecord[]
  count: number
  scannedCount?: number
  lastEvaluatedKey?: any
}

export interface MatchDetailResponse {
  arenaUniqueID: string
  dateTime: string
  mapId: string
  mapDisplayName: string
  gameType: 'clan' | 'pvp' | 'ranked' | 'brawl' | string
  clientVersion: string
  winLoss?: 'win' | 'loss' | 'draw' | 'unknown'
  experienceEarned?: number
  ownPlayer: PlayerInfo
  allies: PlayerInfo[]
  enemies: PlayerInfo[]
  allyMainClanTag?: string
  enemyMainClanTag?: string
  replays: ReplayProvider[]
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

export interface User {
  id: string
  username: string
  globalName: string | null
  avatar: string | null
}
