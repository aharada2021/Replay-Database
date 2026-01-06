/**
 * マップ名変換用composable
 * config/map_names.yamlの内容をTypeScriptオブジェクトとして定義
 */

// マップID → 日本語マップ名のマッピング
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

const DEFAULT_MAP_NAME = 'その他のマップ'

export const useMapNames = () => {
  /**
   * マップIDから日本語名を取得
   */
  const getMapName = (mapId: string): string => {
    if (!mapId) return DEFAULT_MAP_NAME
    return MAP_NAMES[mapId] || DEFAULT_MAP_NAME
  }

  /**
   * マップ一覧を取得（検索フィルター用）
   */
  const getMapList = (): Array<{ text: string; value: string }> => {
    const maps = Object.entries(MAP_NAMES)
      .map(([value, text]) => ({ text, value }))
      .sort((a, b) => a.text.localeCompare(b.text, 'ja'))

    return [{ text: 'すべて', value: '' }, ...maps]
  }

  /**
   * 全マップIDのリストを取得
   */
  const getMapIds = (): string[] => {
    return Object.keys(MAP_NAMES)
  }

  return {
    getMapName,
    getMapList,
    getMapIds,
  }
}
