/**
 * マップ名変換用composable
 * config/map_names.yamlの内容をTypeScriptオブジェクトとして定義
 */

// マップID（短縮形） → 日本語マップ名のマッピング
const MAP_NAMES: Record<string, string> = {
  OC_prey: '罠',
  solomon_islands: 'ソロモン諸島',
  Ring: 'リング',
  NE_passage: '海峡',
  NE_ice_islands: '氷の群島',
  OC_new_dawn: '新たなる夜明け',
  Atlantic: '大西洋',
  NE_north: '北方',
  OC_bees_to_honey: 'ホットスポット',
  NA_fault_line: '断層線',
  NE_two_brothers: '二人の兄弟',
  tierra_del_fuego: '火の地',
  Shards: '破片',
  Greece: 'ギリシャ',
  naval_mission: '砂漠の涙',
  new_tierra: '極地',
  OC_islands: '群島',
  NE_north_winter: '北極光',
  Ridge: '山岳地帯',
  Canada: '粉砕',
  Okinawa: '沖縄',
  Conquest: 'トライデント',
  Neighbors: '隣接勢力',
  Path_warrior: '戦士の道',
  Zigzag: 'ループ',
  Estuary: '河口',
  Sleeping_Giant: '眠れる巨人',
  Gold_harbor: '安息の地',
  Shoreside: '北方海域',
  sea_hope: '幸運の海',
  Britain: 'クラッシュゾーンα',
  Faroe: 'フェロー諸島',
  Seychelles: 'セーシェル',
  CO_ocean: '大海原',
  big_race: 'ビッグレース',
  Archipelago: '列島',
  AngelWings: '夕暮れの島々',
  military_navigation: '反撃',
}

// 完全なマップID（spaces/XX_形式）→ 短縮形のマッピング
// DynamoDBに実際に保存されている形式
const FULL_MAP_IDS: Record<string, string> = {
  'spaces/16_OC_bees_to_honey': 'OC_bees_to_honey',
  'spaces/19_OC_prey': 'OC_prey',
  'spaces/22_tierra_del_fuego': 'tierra_del_fuego',
  'spaces/25_sea_hope': 'sea_hope',
  'spaces/44_Path_warrior': 'Path_warrior',
  'spaces/50_Gold_harbor': 'Gold_harbor',
  'spaces/53_Shoreside': 'Shoreside',
}

const DEFAULT_MAP_NAME = 'その他のマップ'

export const useMapNames = () => {
  /**
   * マップIDから日本語名を取得
   */
  const getMapName = (mapId: string): string => {
    if (!mapId) return DEFAULT_MAP_NAME

    // mapIdから "spaces/" プレフィックスと数字プレフィックス（例: "22_"）を除去
    // 例: "spaces/22_tierra_del_fuego" → "tierra_del_fuego"
    let cleanMapId = mapId.replace(/^spaces\//, '') // "spaces/" を除去
    cleanMapId = cleanMapId.replace(/^\d+_/, '') // 先頭の数字とアンダースコアを除去

    return MAP_NAMES[cleanMapId] || DEFAULT_MAP_NAME
  }

  /**
   * マップ一覧を取得（検索フィルター用）
   * DBに実際に存在するマップのみを返す
   */
  const getMapList = (): Array<{ text: string; value: string }> => {
    const maps = Object.entries(FULL_MAP_IDS)
      .map(([fullId, shortId]) => ({
        text: MAP_NAMES[shortId] || shortId,
        value: fullId, // 完全なmapId（spaces/XX_形式）を使用
      }))
      .sort((a, b) => a.text.localeCompare(b.text, 'ja'))

    return [{ text: 'すべて', value: '' }, ...maps]
  }

  /**
   * 全マップIDのリストを取得（完全なID形式）
   */
  const getMapIds = (): string[] => {
    return Object.keys(FULL_MAP_IDS)
  }

  return {
    getMapName,
    getMapList,
    getMapIds,
  }
}
