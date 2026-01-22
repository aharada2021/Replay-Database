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
  citadels?: number
  crits?: number
  // 命中数内訳
  hitsAP?: number
  hitsSAP?: number
  hitsHE?: number
  hitsSecondariesSAP?: number
  hitsSecondariesAP?: number
  hitsSecondaries?: number
  // ダメージ内訳
  damageAP?: number
  damageSAP?: number
  damageHE?: number
  damageSAPSecondaries?: number
  damageUnknown161?: number
  damageHESecondaries?: number
  damageTorps?: number
  damageDeepWaterTorps?: number
  damageOther?: number
  damageFire?: number
  damageFlooding?: number
  // 被ダメージ内訳
  receivedDamageAP?: number
  receivedDamageSAP?: number
  receivedDamageHE?: number
  receivedDamageTorps?: number
  receivedDamageDeepWaterTorps?: number
  receivedDamageSAPSecondaries?: number  // 副砲SAP被ダメージ
  receivedDamageUnknown218?: number  // 旧フィールド（互換性のため維持）
  receivedDamageHESecondaries?: number
  receivedDamageFire?: number
  receivedDamageFlood?: number
  // 潜在ダメージ内訳
  potentialDamageArt?: number
  potentialDamageTpd?: number
}

// 艦種タイプ
export type ShipClass = 'Destroyer' | 'Cruiser' | 'Battleship' | 'AirCarrier' | 'Submarine' | 'Auxiliary'

// 艦長スキル生データ（DEBUG_CAPTAIN_SKILLS=true時のみ）
export interface CaptainSkillsRaw {
  crew_id: number
  ship_params_id: number
  detected_ship_class: string | null
  used_ship_class: string | null
  is_fallback: boolean
  raw_skill_names: string[]
  all_learned_skills_keys: string[]
}

// 全プレイヤーの統計（チーム情報付き）
export interface PlayerStats extends BattleStats {
  playerName: string
  clanTag?: string
  shipId?: number
  shipName?: string
  shipClass?: ShipClass
  team: 'ally' | 'enemy' | 'unknown'
  isOwn?: boolean
  // 艦長スキル
  captainSkills?: string[]
  // 艦長スキル生データ（DEBUG_CAPTAIN_SKILLS=true時のみ）
  captainSkillsRaw?: CaptainSkillsRaw
  // アップグレード
  upgrades?: string[]
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
  // Dual Render
  dualMp4S3Key?: string
  dualMp4GeneratedAt?: string
  hasDualReplay?: boolean
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

  // 全プレイヤー統計
  allPlayersStats?: PlayerStats[]

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
  // Dual Render
  dualMp4S3Key?: string
  dualMp4GeneratedAt?: string
  hasDualReplay?: boolean

  // コメント数
  commentCount?: number
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
  shipName?: string
  shipTeam?: 'ally' | 'enemy' | ''  // 艦艇チーム条件
  shipMinCount?: number  // 艦艇最小数
  playerName?: string  // プレイヤー名検索
  winLoss?: string
  dateFrom?: string
  dateTo?: string
  limit?: number
  cursorUnixTime?: number | null  // カーソルベースのページネーション用（Unix時間）
}

export interface SearchResponse {
  items: MatchRecord[]
  count: number
  cursorUnixTime?: number | null  // 次のページ用カーソル（Unix時間）
  hasMore?: boolean  // 次のページがあるか
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
  allPlayersStats?: PlayerStats[]
  replays: ReplayProvider[]
  // Dual Render
  hasDualReplay?: boolean
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

export interface Comment {
  arenaUniqueID: string
  commentId: string
  discordUserId: string
  discordUsername: string
  discordGlobalName: string | null
  discordAvatar: string | null
  content: string
  createdAt: string
  updatedAt: string | null
  likes: string[]
  likeCount: number
}

// ========================================
// 分析API（Claude AI）
// ========================================

export interface AnalyzeRequest {
  query: string
  gameType?: string
  dateRange?: {
    from: string
    to: string
  }
  limit?: number
}

export interface AnalyzeResponse {
  analysis: string
  dataUsed: {
    totalBattles: number
    dateRange: {
      from: string | null
      to: string | null
    }
    gameType: string | null
  }
  tokensUsed: number
  remainingQueries: number
  remainingTokens: number
}

export interface AnalyzeError {
  error: string
  usageInfo?: {
    queryCount: number
    tokensUsed: number
    remainingQueries: number
    remainingTokens: number
    cooldownRemaining?: number
  }
}

export interface AnalysisHistoryItem {
  query: string
  response: AnalyzeResponse
  timestamp: string
}
