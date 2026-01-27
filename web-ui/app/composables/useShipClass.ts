/**
 * 艦種表示用composable
 */

import type { ShipClass } from '~/types/replay'

// 艦種の日本語名マッピング
const SHIP_CLASS_LABELS: Record<ShipClass, string> = {
  Destroyer: '駆逐',
  Cruiser: '巡洋',
  Battleship: '戦艦',
  AirCarrier: '空母',
  Submarine: '潜水',
  Auxiliary: '補助',
}

// 艦種の短縮名マッピング
const SHIP_CLASS_SHORT_LABELS: Record<ShipClass, string> = {
  Destroyer: 'DD',
  Cruiser: 'CA',
  Battleship: 'BB',
  AirCarrier: 'CV',
  Submarine: 'SS',
  Auxiliary: 'AX',
}

export const useShipClass = () => {
  /**
   * 艦種の日本語名を取得
   */
  const getShipClassLabel = (shipClass: ShipClass | undefined | null): string => {
    if (!shipClass) return '-'
    return SHIP_CLASS_LABELS[shipClass] || shipClass
  }

  /**
   * 艦種の短縮名を取得
   */
  const getShipClassShortLabel = (shipClass: ShipClass | undefined | null): string => {
    if (!shipClass) return '-'
    return SHIP_CLASS_SHORT_LABELS[shipClass] || shipClass
  }

  /**
   * 艦種アイコンのURLを取得
   */
  const getShipClassIcon = (shipClass: ShipClass | undefined | null): string => {
    if (!shipClass) return ''
    return `/icons/ships/${shipClass}.png`
  }

  return {
    getShipClassLabel,
    getShipClassShortLabel,
    getShipClassIcon,
  }
}
