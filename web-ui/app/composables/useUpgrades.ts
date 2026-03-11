/**
 * アップグレード（近代化改修）翻訳用composable
 * Rust extractorの内部名からPCMコードを抽出し、日本語/英語名に変換
 *
 * 内部名の形式: "PCM030_MainWeapon_Mod_I" → PCMコード "PCM030"
 */

// PCMコード → 日本語名
const UPGRADES_JA: Record<string, string> = {
  PCM001: '主砲改良1',
  PCM002: '副兵装改良1',
  PCM003: '航空機改良1',
  PCM004: '対空兵装改良1',
  PCM005: '副砲改良1',
  PCM006: '主砲改良2',
  PCM007: '魚雷発射管改良1',
  PCM008: '射撃システム改良1',
  PCM009: '飛行制御改良1',
  PCM010: '戦闘機改良1',
  PCM011: '対空兵装改良2',
  PCM012: '副砲改良2',
  PCM013: '主砲改良3',
  PCM014: '魚雷発射管改良2',
  PCM015: '射撃管制システム改良2',
  PCM016: '飛行制御改良2',
  PCM017: '航空機改良2',
  PCM018: '対空砲改良1',
  PCM019: '副砲改良3',
  PCM020: 'ダメージコントロールシステム改良1',
  PCM021: '推進システム改良1',
  PCM022: '操舵システム改良1',
  PCM023: 'ダメージコントロールシステム改良2',
  PCM024: '推進システム改良1',
  PCM025: '操舵システム改良1',
  PCM026: '魚雷警戒システム',
  PCM027: '隠蔽システム改良1',
  PCM028: '射撃管制室改良1',
  PCM029: '射撃管制室改良2',
  PCM030: '主兵装改良1',
  PCM031: '補助兵装改良1',
  PCM032: '特殊改良（空）',
  PCM033: '照準システム改良1',
  PCM034: '照準システム改良0',
  PCM035: '操舵システム改良2',
  PCM036: 'エンジンブースト改良1',
  PCM037: '発煙装置改良1',
  PCM038: '水上機改良1',
  PCM039: '応急工作班改良1',
  PCM040: '対空防御砲火改良1',
  PCM041: '水中聴音改良1',
  PCM042: 'レーダー改良1',
  PCM043: '主砲装填ブースター改良1',
  PCM044: '主砲装填ブースター改良2',
  PCM045: '主砲装填ブースター改良3',
  PCM046: '主砲射撃装置改良1',
  PCM047: 'ダメコン改良特殊1',
  PCM048: '照準改良特殊1',
  PCM049: 'ダメコン改良特殊2',
  PCM050: '主砲改良特殊1',
  PCM051: '隠蔽改良特殊1',
  PCM052: '推進改良特殊1',
  PCM053: '消耗品改良特殊1',
  PCM054: '主砲射撃改良1',
  PCM055: '主砲射撃改良2',
  PCM056: '魚雷改良特殊1',
  PCM057: '魚雷改良特殊2',
  PCM058: '隠蔽改良特殊2',
  PCM059: '煙幕改良特殊1',
  PCM060: '装填改良特殊1',
  PCM061: '爆撃機改良特殊1',
  PCM062: '航空機速度改良1',
  PCM063: '攻撃機改良2',
  PCM064: '雷撃機改良2',
  PCM065: '爆撃機改良1',
  PCM066: '雷撃機改良1',
  PCM067: '攻撃機改良1',
  PCM068: '航空機エンジン改良1',
  PCM069: '機関室防護',
  PCM070: '魚雷発射管改良1',
  PCM071: '航空魚雷改良1',
  PCM072: '艦艇消耗品改良1',
  PCM073: '航空隊消耗品改良1',
  PCM074: '補助兵装改良2',
  PCM075: '魚雷改良特殊3',
  PCM076: '隠蔽改良特殊3',
  PCM077: '煙幕改良特殊2',
  PCM078: '主砲改良特殊2',
  PCM079: '推進・隠蔽改良1',
  PCM080: '主砲射撃改良3',
  PCM081: 'スキップボマー改良2',
  PCM082: '潜航容量改良1',
  PCM083: '聴音改良特殊1',
  PCM084: 'ソナー改良1',
  PCM085: 'ソナー改良2',
  PCM086: '潜航容量改良2',
  PCM087: '航空攻撃改良1',
  PCM088: '爆雷改良特殊1',
  PCM089: '爆雷改良1',
  PCM090: '潜水艦操舵システム',
  PCM091: '潜水艦操舵改良1',
  PCM092: 'スキップボマー改良1',
  PCM093: '航空機改良3',
  PCM094: '特殊改良1',
  PCM095: '煙幕改良特殊3',
  PCM096: '主砲改良特殊3',
  PCM097: '雷撃機改良特殊1',
  PCM098: '駆逐艦改良特殊1',
  PCM099: '爆雷改良特殊2',
  PCM100: 'ダメコンシステム改良3',
  PCM101: '魚雷発射管改良3',
  PCM102: '強化隔壁',
  PCM103: '潜水艦改良特殊1',
  PCM104: '潜水艦探知改良1',
  PCM105: '対空・爆雷改良1',
  PCM106: '主砲改良特殊4',
  PCM107: '装填改良特殊2',
  PCM108: '魚雷改良特殊4',
  PCM109: '火災改良特殊1',
  PCM110: 'ミサイル改良1',
  PCM111: '船体改良特殊1',
  PCM112: '速度改良特殊1',
  PCM113: '消耗品改良特殊2',
  PCM114: '速度改良特殊2',
  PCM115: '隠蔽改良特殊4',
  PCM116: '操舵改良特殊1',
  PCM117: '装填改良特殊3',
  PCM118: '魚雷改良特殊5',
}

/**
 * 内部名からPCMコードを抽出
 * 例: "PCM030_MainWeapon_Mod_I" → "PCM030"
 */
function extractPcmCode(internalName: string): string | null {
  const match = internalName.match(/^(PCM\d+)/)
  return match ? match[1] : null
}

export const useUpgrades = () => {
  /**
   * 内部アップグレード名から表示名を取得
   */
  const getUpgradeName = (internalName: string, locale: string = 'ja'): string => {
    if (locale !== 'ja') return internalName

    const pcm = extractPcmCode(internalName)
    if (!pcm) return internalName

    return UPGRADES_JA[pcm] || internalName
  }

  /**
   * アップグレード名配列を一括変換
   */
  const translateUpgrades = (upgrades: string[], locale: string = 'ja'): string[] => {
    return upgrades.map(u => getUpgradeName(u, locale))
  }

  return {
    getUpgradeName,
    translateUpgrades,
  }
}
