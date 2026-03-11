<template>
  <div class="pa-4">
    <!-- Stats読み込み中 -->
    <v-row v-if="isLoadingStats">
      <v-col cols="12" class="text-center py-8">
        <v-progress-circular indeterminate color="primary" size="32"></v-progress-circular>
        <div class="text-caption mt-2">戦闘統計を読み込み中...</div>
      </v-col>
    </v-row>

    <!-- スコアボード + ミニマップ動画 横並び -->
    <v-row v-else-if="hasAllPlayersStats">
      <!-- 全プレイヤー戦闘統計（スコアボード） -->
      <v-col cols="12" lg="8">
        <div class="d-flex align-center mb-2">
          <h3 class="text-body-2">戦闘統計スコアボード</h3>
          <v-btn
            v-if="isCustomSorted"
            size="x-small"
            variant="text"
            color="primary"
            class="ml-2"
            @click="resetToDefaultSort"
          >
            <v-icon size="small" class="mr-1">mdi-sort</v-icon>
            デフォルト順に戻す
          </v-btn>
        </div>
        <v-data-table
          v-model:sort-by="sortBy"
          :headers="scoreboardHeaders"
          :items="sortedPlayersStats"
          :items-per-page="-1"
          density="compact"
          class="scoreboard-table"
          hide-default-footer
        >
          <!-- チーム -->
          <template v-slot:item.team="{ item }">
            <span :class="item.team === 'ally' ? 'text-success' : 'text-error'">
              {{ item.team === 'ally' ? '🟢' : '🔴' }}
            </span>
            <v-icon v-if="item.isOwn" size="x-small" color="primary">mdi-star</v-icon>
          </template>

          <!-- プレイヤー名（艦長スキル・艦艇コンポーネントツールチップ付き） -->
          <template v-slot:item.playerName="{ item }">
            <v-tooltip v-if="hasPlayerDetails(item)" location="right" max-width="350">
              <template v-slot:activator="{ props }">
                <span v-bind="props" class="cursor-help">
                  <span v-if="item.clanTag" class="font-weight-bold" :class="item.team === 'ally' ? 'text-success' : 'text-error'">
                    [{{ item.clanTag }}]
                  </span>
                  {{ item.playerName }}
                  <v-icon v-if="item.captainSkills?.length" size="x-small" color="amber" class="ml-1">mdi-star-circle</v-icon>
                </span>
              </template>
              <div class="player-details-tooltip">
                <!-- アップグレード -->
                <div v-if="item.upgrades?.length" class="mb-2">
                  <div class="tooltip-title">
                    <v-icon size="small" class="mr-1">mdi-wrench</v-icon>
                    アップグレード ({{ item.upgrades.length }})
                  </div>
                  <div class="upgrades-list">
                    <span v-for="(upgrade, idx) in item.upgrades" :key="idx" class="upgrade-chip">
                      {{ getUpgradeName(upgrade) }}
                    </span>
                  </div>
                </div>
                <!-- 艦長スキル -->
                <div v-if="item.captainSkills?.length">
                  <div class="tooltip-title">
                    <v-icon size="small" class="mr-1">mdi-account-star</v-icon>
                    艦長スキル ({{ item.captainSkills.length }})
                  </div>
                  <div class="captain-skills">
                    <span v-for="(skill, idx) in item.captainSkills" :key="idx" class="skill-chip">
                      {{ getSkillName(skill) }}
                    </span>
                  </div>
                </div>
              </div>
            </v-tooltip>
            <span v-else>
              <span v-if="item.clanTag" class="font-weight-bold" :class="item.team === 'ally' ? 'text-success' : 'text-error'">
                [{{ item.clanTag }}]
              </span>
              {{ item.playerName }}
            </span>
          </template>

          <!-- 艦種 -->
          <template v-slot:item.shipClass="{ item }">
            <v-tooltip v-if="item.shipClass" location="top">
              <template v-slot:activator="{ props }">
                <img
                  v-bind="props"
                  :src="getShipClassIcon(item.shipClass)"
                  :alt="getShipClassShortLabel(item.shipClass)"
                  class="ship-class-icon"
                />
              </template>
              {{ getShipClassShortLabel(item.shipClass) }}
            </v-tooltip>
            <span v-else class="text-grey">-</span>
          </template>

          <!-- 艦船 -->
          <template v-slot:item.shipName="{ item }">
            <span class="text-caption">{{ item.shipName || '-' }}</span>
          </template>

          <!-- 数値フォーマット -->
          <template v-slot:item.kills="{ item }">
            <span class="text-error font-weight-bold">{{ item.kills || 0 }}</span>
          </template>

          <template v-slot:item.damage="{ item }">
            <v-tooltip location="top">
              <template v-slot:activator="{ props }">
                <span v-bind="props" class="font-weight-bold cursor-help">{{ formatNumber(item.damage) }}</span>
              </template>
              <div class="tooltip-content">
                <div class="tooltip-title">ダメージ内訳</div>
                <div class="tooltip-row">
                  <span>主砲 AP:</span>
                  <span>{{ formatNumber(item.damageAP) }}</span>
                </div>
                <div class="tooltip-row">
                  <span>主砲 SAP:</span>
                  <span>{{ formatNumber(item.damageSAP) }}</span>
                </div>
                <div class="tooltip-row">
                  <span>主砲 HE:</span>
                  <span>{{ formatNumber(item.damageHE) }}</span>
                </div>
                <div class="tooltip-row">
                  <span>副砲 SAP:</span>
                  <span>{{ formatNumber(item.damageSAPSecondaries) }}</span>
                </div>
                <div class="tooltip-row">
                  <span>副砲 HE:</span>
                  <span>{{ formatNumber(item.damageHESecondaries) }}</span>
                </div>
                <div class="tooltip-row">
                  <span>魚雷:</span>
                  <span>{{ formatNumber(item.damageTorps) }}</span>
                </div>
                <div class="tooltip-row">
                  <span>深度魚雷:</span>
                  <span>{{ formatNumber(item.damageDeepWaterTorps) }}</span>
                </div>
                <div class="tooltip-row text-orange">
                  <span>火災:</span>
                  <span>{{ formatNumber(item.damageFire) }}</span>
                </div>
                <div class="tooltip-row text-blue">
                  <span>浸水:</span>
                  <span>{{ formatNumber(item.damageFlooding) }}</span>
                </div>
                <div class="tooltip-row">
                  <span>その他:</span>
                  <span>{{ formatNumber(item.damageOther) }}</span>
                </div>
              </div>
            </v-tooltip>
          </template>

          <template v-slot:item.spottingDamage="{ item }">
            {{ formatNumber(item.spottingDamage) }}
          </template>

          <template v-slot:item.receivedDamage="{ item }">
            <v-tooltip location="top">
              <template v-slot:activator="{ props }">
                <span v-bind="props" class="cursor-help">{{ formatNumber(item.receivedDamage) }}</span>
              </template>
              <div class="tooltip-content">
                <div class="tooltip-title">被ダメージ内訳</div>
                <div class="tooltip-row">
                  <span>主砲 AP:</span>
                  <span>{{ formatNumber(item.receivedDamageAP) }}</span>
                </div>
                <div class="tooltip-row">
                  <span>主砲 SAP:</span>
                  <span>{{ formatNumber(item.receivedDamageSAP) }}</span>
                </div>
                <div class="tooltip-row">
                  <span>主砲 HE:</span>
                  <span>{{ formatNumber(item.receivedDamageHE) }}</span>
                </div>
                <div class="tooltip-row">
                  <span>副砲 HE:</span>
                  <span>{{ formatNumber(item.receivedDamageHESecondaries) }}</span>
                </div>
                <div class="tooltip-row">
                  <span>魚雷:</span>
                  <span>{{ formatNumber(item.receivedDamageTorps) }}</span>
                </div>
                <div class="tooltip-row">
                  <span>深度魚雷:</span>
                  <span>{{ formatNumber(item.receivedDamageDeepWaterTorps) }}</span>
                </div>
                <div class="tooltip-row text-orange">
                  <span>火災:</span>
                  <span>{{ formatNumber(item.receivedDamageFire) }}</span>
                </div>
                <div class="tooltip-row text-blue">
                  <span>浸水:</span>
                  <span>{{ formatNumber(item.receivedDamageFlood) }}</span>
                </div>
              </div>
            </v-tooltip>
          </template>

          <template v-slot:item.potentialDamage="{ item }">
            <v-tooltip location="top">
              <template v-slot:activator="{ props }">
                <span v-bind="props" class="cursor-help">{{ formatNumber(item.potentialDamage) }}</span>
              </template>
              <div class="tooltip-content">
                <div class="tooltip-title">潜在ダメージ内訳</div>
                <div class="tooltip-row">
                  <span>砲撃:</span>
                  <span>{{ formatNumber(item.potentialDamageArt) }}</span>
                </div>
                <div class="tooltip-row">
                  <span>魚雷:</span>
                  <span>{{ formatNumber(item.potentialDamageTpd) }}</span>
                </div>
              </div>
            </v-tooltip>
          </template>

          <template v-slot:item.totalHits="{ item }">
            <v-tooltip location="top">
              <template v-slot:activator="{ props }">
                <span v-bind="props" class="cursor-help">{{ item.totalHits || 0 }}</span>
              </template>
              <div class="tooltip-content">
                <div class="tooltip-title">命中数内訳</div>
                <div class="tooltip-row">
                  <span>主砲 AP:</span>
                  <span>{{ item.hitsAP || 0 }} 発</span>
                </div>
                <div class="tooltip-row">
                  <span>主砲 SAP:</span>
                  <span>{{ item.hitsSAP || 0 }} 発</span>
                </div>
                <div class="tooltip-row">
                  <span>主砲 HE:</span>
                  <span>{{ item.hitsHE || 0 }} 発</span>
                </div>
                <div class="tooltip-row">
                  <span>副砲 SAP:</span>
                  <span>{{ item.hitsSecondariesSAP || 0 }} 発</span>
                </div>
                <div class="tooltip-row">
                  <span>副砲 HE:</span>
                  <span>{{ item.hitsSecondaries || 0 }} 発</span>
                </div>
              </div>
            </v-tooltip>
          </template>

          <template v-slot:item.fires="{ item }">
            <span class="text-orange">{{ item.fires || 0 }}</span>
          </template>

          <template v-slot:item.floods="{ item }">
            <span class="text-blue">{{ item.floods || 0 }}</span>
          </template>

          <template v-slot:item.citadels="{ item }">
            <v-tooltip location="top">
              <template v-slot:activator="{ props }">
                <span v-bind="props" class="text-purple font-weight-bold cursor-help">{{ item.citadels || 0 }}</span>
              </template>
              <div class="tooltip-content">
                <div class="tooltip-title">クリティカル内訳</div>
                <div class="tooltip-row">
                  <span>貫通 (Citadels):</span>
                  <span>{{ item.citadels || 0 }}</span>
                </div>
                <div class="tooltip-row">
                  <span>モジュール破壊 (Crits):</span>
                  <span>{{ item.crits || 0 }}</span>
                </div>
              </div>
            </v-tooltip>
          </template>

          <template v-slot:item.baseXP="{ item }">
            <span class="text-amber">{{ formatNumber(item.baseXP) }}</span>
          </template>
        </v-data-table>
      </v-col>

      <!-- 動画プレーヤー（スコアボードがある場合） -->
      <v-col cols="12" lg="4">
        <!-- 動画タイプ切り替えボタン -->
        <div class="d-flex align-center mb-2">
          <v-btn-toggle
            v-if="hasAnyVideo"
            v-model="selectedVideoType"
            mandatory
            density="compact"
            color="primary"
            variant="outlined"
          >
            <v-btn value="minimap" size="small" :disabled="!hasMinimapVideo">
              <v-icon size="small" class="mr-1">mdi-map</v-icon>
              ミニマップ
            </v-btn>
            <v-btn value="gameplay" size="small" :disabled="!hasGameplayVideo">
              <v-icon size="small" class="mr-1">mdi-gamepad-variant</v-icon>
              ゲームプレイ
            </v-btn>
          </v-btn-toggle>
          <v-chip v-if="selectedVideoType === 'minimap' && isDualVideo" color="purple" size="x-small" class="ml-2">
            <v-icon size="x-small" class="mr-1">mdi-eye-outline</v-icon>
            両陣営視点
          </v-chip>
        </div>

        <!-- ミニマップ動画 -->
        <div v-if="selectedVideoType === 'minimap'" class="video-container">
          <template v-if="videoReplay">
            <video
              controls
              class="video-player"
              :src="getVideoUrl(videoReplay.mp4S3Key)"
              :key="'minimap-' + videoReplay.playerID"
            >
              お使いのブラウザは動画タグをサポートしていません。
            </video>
            <div class="mt-1 text-caption">
              <v-icon size="small">mdi-account</v-icon>
              {{ isDualVideo ? '両陣営' : videoReplay.playerName }} のリプレイ
            </div>
          </template>
          <v-alert v-else :type="isPolling ? 'warning' : 'info'" density="compact" class="d-flex align-center">
            <template v-if="isPolling">
              <v-progress-circular size="16" width="2" indeterminate class="mr-2" />
              動画を生成中...
            </template>
            <template v-else>
              ミニマップ動画なし
            </template>
          </v-alert>
        </div>

        <!-- ゲームプレイ動画 -->
        <div v-else-if="selectedVideoType === 'gameplay'" class="video-container">
          <template v-if="gameplayVideoReplay">
            <!-- 複数プレイヤーがいる場合のプレイヤー選択 -->
            <div v-if="hasMultipleGameplayVideos" class="mb-2">
              <v-btn-toggle
                :model-value="gameplayVideoReplay.playerID"
                @update:model-value="onGameplayPlayerChange"
                mandatory
                density="compact"
                color="info"
                variant="outlined"
                class="gameplay-player-toggle"
              >
                <v-btn
                  v-for="replay in gameplayVideoReplays"
                  :key="replay.playerID"
                  :value="replay.playerID"
                  size="small"
                >
                  <v-icon size="x-small" class="mr-1">mdi-account</v-icon>
                  {{ replay.playerName }}
                </v-btn>
              </v-btn-toggle>
            </div>
            <video
              ref="gameplayVideoRef"
              controls
              class="video-player"
              :src="getGameplayVideoUrl(gameplayVideoReplay.gameplayVideoS3Key)"
              :key="'gameplay-' + gameplayVideoReplay.playerID"
              @loadedmetadata="onGameplayVideoLoaded"
            >
              お使いのブラウザは動画タグをサポートしていません。
            </video>
            <div class="mt-1 text-caption">
              <v-icon size="small">mdi-account</v-icon>
              {{ gameplayVideoReplay.playerName }} のゲームプレイ
              <span v-if="gameplayVideoReplay.gameplayVideoSize" class="text-grey ml-1">
                ({{ formatFileSize(gameplayVideoReplay.gameplayVideoSize) }})
              </span>
            </div>
          </template>
          <v-alert v-else type="info" density="compact">
            ゲームプレイ動画なし
          </v-alert>
        </div>
      </v-col>
    </v-row>

    <!-- プレイヤー一覧（allPlayersStatsがない場合のフォールバック） + ミニマップ動画 -->
    <v-row v-else>
      <!-- プレイヤー一覧 -->
      <v-col cols="12" md="6">
        <h3 class="mb-2">プレイヤー一覧</h3>
        <v-row dense>
          <!-- 自分 -->
          <v-col cols="12">
            <v-card variant="outlined" density="compact">
              <v-card-title class="text-caption bg-primary py-1">自分</v-card-title>
              <v-card-text class="pa-2">
                <div class="text-body-2">
                  <span v-if="match.ownPlayer.clanTag" class="text-primary font-weight-bold">
                    [{{ match.ownPlayer.clanTag }}]
                  </span>
                  {{ match.ownPlayer.name }}
                  <span class="text-caption text-grey ml-2">{{ match.ownPlayer.shipName }}</span>
                </div>
              </v-card-text>
            </v-card>
          </v-col>

          <!-- 味方 -->
          <v-col cols="6">
            <v-card variant="outlined" density="compact">
              <v-card-title class="text-caption bg-success py-1">味方 ({{ match.allies?.length || 0 }}名)</v-card-title>
              <v-card-text class="pa-2">
                <div v-for="(player, idx) in match.allies" :key="idx" class="mb-1">
                  <div class="text-body-2">
                    <span v-if="player.clanTag" class="text-primary font-weight-bold">
                      [{{ player.clanTag }}]
                    </span>
                    {{ player.name }}
                  </div>
                  <div class="text-caption text-grey">{{ player.shipName }}</div>
                </div>
              </v-card-text>
            </v-card>
          </v-col>

          <!-- 敵 -->
          <v-col cols="6">
            <v-card variant="outlined" density="compact">
              <v-card-title class="text-caption bg-error py-1">敵 ({{ match.enemies?.length || 0 }}名)</v-card-title>
              <v-card-text class="pa-2">
                <div v-for="(player, idx) in match.enemies" :key="idx" class="mb-1">
                  <div class="text-body-2">
                    <span v-if="player.clanTag" class="text-error font-weight-bold">
                      [{{ player.clanTag }}]
                    </span>
                    {{ player.name }}
                  </div>
                  <div class="text-caption text-grey">{{ player.shipName }}</div>
                </div>
              </v-card-text>
            </v-card>
          </v-col>
        </v-row>
      </v-col>

      <!-- 動画プレーヤー（スコアボードがない場合） -->
      <v-col cols="12" md="6">
        <!-- 動画タイプ切り替えボタン -->
        <div class="d-flex align-center mb-2">
          <v-btn-toggle
            v-if="hasAnyVideo"
            v-model="selectedVideoType"
            mandatory
            density="compact"
            color="primary"
            variant="outlined"
          >
            <v-btn value="minimap" size="small" :disabled="!hasMinimapVideo">
              <v-icon size="small" class="mr-1">mdi-map</v-icon>
              ミニマップ
            </v-btn>
            <v-btn value="gameplay" size="small" :disabled="!hasGameplayVideo">
              <v-icon size="small" class="mr-1">mdi-gamepad-variant</v-icon>
              ゲームプレイ
            </v-btn>
          </v-btn-toggle>
          <v-chip v-if="selectedVideoType === 'minimap' && isDualVideo" color="purple" size="x-small" class="ml-2">
            <v-icon size="x-small" class="mr-1">mdi-eye-outline</v-icon>
            両陣営視点
          </v-chip>
        </div>

        <!-- ミニマップ動画 -->
        <div v-if="selectedVideoType === 'minimap'" class="video-container">
          <template v-if="videoReplay">
            <video
              controls
              class="video-player"
              :src="getVideoUrl(videoReplay.mp4S3Key)"
              :key="'minimap-alt-' + videoReplay.playerID"
            >
              お使いのブラウザは動画タグをサポートしていません。
            </video>
            <div class="mt-1 text-caption">
              <v-icon size="small">mdi-account</v-icon>
              {{ isDualVideo ? '両陣営' : videoReplay.playerName }} のリプレイ
            </div>
          </template>
          <v-alert v-else :type="isPolling ? 'warning' : 'info'" density="compact" class="d-flex align-center">
            <template v-if="isPolling">
              <v-progress-circular size="16" width="2" indeterminate class="mr-2" />
              動画を生成中...
            </template>
            <template v-else>
              この試合の動画はまだ生成されていません
            </template>
          </v-alert>
        </div>

        <!-- ゲームプレイ動画 -->
        <div v-else-if="selectedVideoType === 'gameplay'" class="video-container">
          <template v-if="gameplayVideoReplay">
            <!-- 複数プレイヤーがいる場合のプレイヤー選択 -->
            <div v-if="hasMultipleGameplayVideos" class="mb-2">
              <v-btn-toggle
                :model-value="gameplayVideoReplay.playerID"
                @update:model-value="onGameplayPlayerChange"
                mandatory
                density="compact"
                color="info"
                variant="outlined"
                class="gameplay-player-toggle"
              >
                <v-btn
                  v-for="replay in gameplayVideoReplays"
                  :key="replay.playerID"
                  :value="replay.playerID"
                  size="small"
                >
                  <v-icon size="x-small" class="mr-1">mdi-account</v-icon>
                  {{ replay.playerName }}
                </v-btn>
              </v-btn-toggle>
            </div>
            <video
              ref="gameplayVideoRef"
              controls
              class="video-player"
              :src="getGameplayVideoUrl(gameplayVideoReplay.gameplayVideoS3Key)"
              :key="'gameplay-alt-' + gameplayVideoReplay.playerID"
              @loadedmetadata="onGameplayVideoLoaded"
            >
              お使いのブラウザは動画タグをサポートしていません。
            </video>
            <div class="mt-1 text-caption">
              <v-icon size="small">mdi-account</v-icon>
              {{ gameplayVideoReplay.playerName }} のゲームプレイ
              <span v-if="gameplayVideoReplay.gameplayVideoSize" class="text-grey ml-1">
                ({{ formatFileSize(gameplayVideoReplay.gameplayVideoSize) }})
              </span>
            </div>
          </template>
          <v-alert v-else type="info" density="compact">
            ゲームプレイ動画なし
          </v-alert>
        </div>
      </v-col>
    </v-row>

    <v-divider class="my-3"></v-divider>

    <!-- リプレイ提供者 -->
    <h3 class="mb-2">リプレイ提供者</h3>
    <v-list density="compact" class="py-0">
      <v-list-item v-for="(replay, index) in match.replays" :key="index" class="px-0">
        <template v-slot:prepend>
          <v-avatar size="small" color="primary">
            <v-icon v-if="replay.mp4S3Key" size="small">mdi-video</v-icon>
            <v-icon v-else size="small">mdi-account</v-icon>
          </v-avatar>
        </template>

        <v-list-item-title>
          <span v-if="replay.ownPlayer?.clanTag" class="text-primary font-weight-bold">
            [{{ replay.ownPlayer.clanTag }}]
          </span>
          {{ replay.playerName }}
          <v-chip v-if="replay.mp4S3Key" size="x-small" color="success" class="ml-1">
            動画あり
          </v-chip>
          <v-chip v-if="replay.gameplayVideoS3Key" size="x-small" color="info" class="ml-1">
            <v-icon size="x-small" class="mr-1">mdi-gamepad-variant</v-icon>
            ゲームプレイ
          </v-chip>
          <span class="text-caption text-grey ml-2">
            {{ replay.ownPlayer?.shipName || '-' }} | {{ formatDateTime(replay.uploadedAt) }}
          </span>
        </v-list-item-title>

        <template v-slot:append>
          <v-btn
            size="x-small"
            variant="text"
            icon="mdi-download"
            @click="downloadReplay(replay.s3Key)"
          ></v-btn>
        </template>
      </v-list-item>
    </v-list>

    <!-- デバッグセクション（?debug=trueで表示） -->
    <template v-if="isDebugMode && hasAllPlayersStats">
      <v-divider class="my-3"></v-divider>
      <div class="debug-section">
        <h3 class="mb-2 d-flex align-center">
          <v-icon color="warning" class="mr-1">mdi-bug</v-icon>
          BattleStats デバッグ情報
        </h3>
        <v-alert type="info" density="compact" class="mb-3">
          各プレイヤーのBattleStatsフィールドを表示しています。インデックス探索のデバッグに使用してください。
        </v-alert>

        <v-expansion-panels variant="accordion">
          <v-expansion-panel v-for="(player, idx) in sortedPlayersStats" :key="idx">
            <v-expansion-panel-title>
              <span :class="player.team === 'ally' ? 'text-success' : 'text-error'">
                {{ player.team === 'ally' ? '味方' : '敵' }}
              </span>
              <span class="ml-2">
                <span v-if="player.clanTag" class="font-weight-bold">[{{ player.clanTag }}]</span>
                {{ player.playerName }}
              </span>
              <span class="ml-2 text-grey">{{ player.shipName }}</span>
            </v-expansion-panel-title>
            <v-expansion-panel-text>
              <v-table density="compact" class="debug-table">
                <thead>
                  <tr>
                    <th>カテゴリ</th>
                    <th>フィールド名</th>
                    <th class="text-right">値</th>
                  </tr>
                </thead>
                <tbody>
                  <!-- 基本情報 -->
                  <tr class="category-header"><td colspan="3">基本情報</td></tr>
                  <tr><td></td><td>playerName</td><td class="text-right">{{ player.playerName }}</td></tr>
                  <tr><td></td><td>clanTag</td><td class="text-right">{{ player.clanTag || '-' }}</td></tr>
                  <tr><td></td><td>shipName</td><td class="text-right">{{ player.shipName || '-' }}</td></tr>
                  <tr><td></td><td>shipClass</td><td class="text-right">{{ player.shipClass || '-' }}</td></tr>
                  <tr><td></td><td>shipId</td><td class="text-right">{{ player.shipId || '-' }}</td></tr>

                  <!-- 基本統計 -->
                  <tr class="category-header"><td colspan="3">基本統計</td></tr>
                  <tr><td></td><td>damage</td><td class="text-right">{{ formatNumber(player.damage) }}</td></tr>
                  <tr><td></td><td>receivedDamage</td><td class="text-right">{{ formatNumber(player.receivedDamage) }}</td></tr>
                  <tr><td></td><td>spottingDamage</td><td class="text-right">{{ formatNumber(player.spottingDamage) }}</td></tr>
                  <tr><td></td><td>potentialDamage</td><td class="text-right">{{ formatNumber(player.potentialDamage) }}</td></tr>
                  <tr><td></td><td>kills</td><td class="text-right">{{ player.kills || 0 }}</td></tr>
                  <tr><td></td><td>fires</td><td class="text-right">{{ player.fires || 0 }}</td></tr>
                  <tr><td></td><td>floods</td><td class="text-right">{{ player.floods || 0 }}</td></tr>
                  <tr><td></td><td>baseXP</td><td class="text-right">{{ formatNumber(player.baseXP) }}</td></tr>
                  <tr><td></td><td>citadels</td><td class="text-right">{{ player.citadels || 0 }}</td></tr>
                  <tr><td></td><td>crits</td><td class="text-right">{{ player.crits || 0 }}</td></tr>

                  <!-- 命中数内訳 -->
                  <tr class="category-header"><td colspan="3">命中数内訳</td></tr>
                  <tr><td></td><td>hitsAP (主砲AP)</td><td class="text-right">{{ player.hitsAP || 0 }}</td></tr>
                  <tr><td></td><td>hitsSAP (主砲SAP)</td><td class="text-right">{{ player.hitsSAP || 0 }}</td></tr>
                  <tr><td></td><td>hitsHE (主砲HE)</td><td class="text-right">{{ player.hitsHE || 0 }}</td></tr>
                  <tr><td></td><td>hitsSecondariesSAP (副砲SAP)</td><td class="text-right">{{ player.hitsSecondariesSAP || 0 }}</td></tr>
                  <tr><td></td><td>hitsSecondariesAP (副砲AP)</td><td class="text-right">{{ player.hitsSecondariesAP || 0 }}</td></tr>
                  <tr><td></td><td>hitsSecondaries (副砲HE)</td><td class="text-right">{{ player.hitsSecondaries || 0 }}</td></tr>

                  <!-- 与ダメージ内訳 -->
                  <tr class="category-header"><td colspan="3">与ダメージ内訳</td></tr>
                  <tr><td></td><td>damageAP (主砲AP)</td><td class="text-right">{{ formatNumber(player.damageAP) }}</td></tr>
                  <tr><td></td><td>damageSAP (主砲SAP)</td><td class="text-right">{{ formatNumber(player.damageSAP) }}</td></tr>
                  <tr><td></td><td>damageHE (主砲HE)</td><td class="text-right">{{ formatNumber(player.damageHE) }}</td></tr>
                  <tr><td></td><td>damageSAPSecondaries (副砲SAP)</td><td class="text-right">{{ formatNumber(player.damageSAPSecondaries) }}</td></tr>
                  <tr><td></td><td>damageHESecondaries (副砲HE)</td><td class="text-right">{{ formatNumber(player.damageHESecondaries) }}</td></tr>
                  <tr><td></td><td>damageTorps (魚雷)</td><td class="text-right">{{ formatNumber(player.damageTorps) }}</td></tr>
                  <tr><td></td><td>damageDeepWaterTorps (深度魚雷)</td><td class="text-right">{{ formatNumber(player.damageDeepWaterTorps) }}</td></tr>
                  <tr><td></td><td>damageFire (火災)</td><td class="text-right">{{ formatNumber(player.damageFire) }}</td></tr>
                  <tr><td></td><td>damageFlooding (浸水)</td><td class="text-right">{{ formatNumber(player.damageFlooding) }}</td></tr>
                  <tr><td></td><td>damageOther (その他)</td><td class="text-right">{{ formatNumber(player.damageOther) }}</td></tr>

                  <!-- 被ダメージ内訳 -->
                  <tr class="category-header"><td colspan="3">被ダメージ内訳</td></tr>
                  <tr><td></td><td>receivedDamageAP (主砲AP)</td><td class="text-right">{{ formatNumber(player.receivedDamageAP) }}</td></tr>
                  <tr><td></td><td>receivedDamageSAP (主砲SAP)</td><td class="text-right">{{ formatNumber(player.receivedDamageSAP) }}</td></tr>
                  <tr><td></td><td>receivedDamageHE (主砲HE)</td><td class="text-right">{{ formatNumber(player.receivedDamageHE) }}</td></tr>
                  <tr><td></td><td>receivedDamageSAPSecondaries (副砲SAP)</td><td class="text-right">{{ formatNumber(player.receivedDamageSAPSecondaries) }}</td></tr>
                  <tr><td></td><td>receivedDamageHESecondaries (副砲HE)</td><td class="text-right">{{ formatNumber(player.receivedDamageHESecondaries) }}</td></tr>
                  <tr><td></td><td>receivedDamageTorps (魚雷)</td><td class="text-right">{{ formatNumber(player.receivedDamageTorps) }}</td></tr>
                  <tr><td></td><td>receivedDamageDeepWaterTorps (深度魚雷)</td><td class="text-right">{{ formatNumber(player.receivedDamageDeepWaterTorps) }}</td></tr>
                  <tr><td></td><td>receivedDamageFire (火災)</td><td class="text-right">{{ formatNumber(player.receivedDamageFire) }}</td></tr>
                  <tr><td></td><td>receivedDamageFlood (浸水)</td><td class="text-right">{{ formatNumber(player.receivedDamageFlood) }}</td></tr>
                  <tr><td></td><td>receivedDamageUnknown218 (旧)</td><td class="text-right">{{ formatNumber(player.receivedDamageUnknown218) }}</td></tr>

                  <!-- 潜在ダメージ内訳 -->
                  <tr class="category-header"><td colspan="3">潜在ダメージ内訳</td></tr>
                  <tr><td></td><td>potentialDamageArt (砲撃)</td><td class="text-right">{{ formatNumber(player.potentialDamageArt) }}</td></tr>
                  <tr><td></td><td>potentialDamageTpd (魚雷)</td><td class="text-right">{{ formatNumber(player.potentialDamageTpd) }}</td></tr>

                  <!-- 艦長スキル・アップグレード（生データ） -->
                  <tr class="category-header"><td colspan="3">艦長スキル・アップグレード</td></tr>
                  <tr>
                    <td></td>
                    <td>captainSkills (表示名)</td>
                    <td class="text-right">
                      <code class="raw-data">{{ JSON.stringify(player.captainSkills || []) }}</code>
                    </td>
                  </tr>
                  <tr>
                    <td></td>
                    <td>captainSkills 件数</td>
                    <td class="text-right">{{ player.captainSkills?.length || 0 }}</td>
                  </tr>
                  <tr>
                    <td></td>
                    <td>upgrades (配列)</td>
                    <td class="text-right">
                      <code class="raw-data">{{ JSON.stringify(player.upgrades || []) }}</code>
                    </td>
                  </tr>
                  <tr>
                    <td></td>
                    <td>upgrades 件数</td>
                    <td class="text-right">{{ player.upgrades?.length || 0 }}</td>
                  </tr>

                  <!-- 艦長スキル生データ（DEBUG_CAPTAIN_SKILLS=true時のみ） -->
                  <template v-if="player.captainSkillsRaw">
                    <tr class="category-header"><td colspan="3">艦長スキル生データ (DEBUG_CAPTAIN_SKILLS=true)</td></tr>
                    <tr>
                      <td></td>
                      <td>crew_id</td>
                      <td class="text-right">{{ player.captainSkillsRaw.crew_id }}</td>
                    </tr>
                    <tr>
                      <td></td>
                      <td>ship_params_id</td>
                      <td class="text-right">{{ player.captainSkillsRaw.ship_params_id }}</td>
                    </tr>
                    <tr>
                      <td></td>
                      <td>detected_ship_class</td>
                      <td class="text-right">{{ player.captainSkillsRaw.detected_ship_class || '(検出失敗)' }}</td>
                    </tr>
                    <tr>
                      <td></td>
                      <td>used_ship_class</td>
                      <td class="text-right">{{ player.captainSkillsRaw.used_ship_class }}</td>
                    </tr>
                    <tr>
                      <td></td>
                      <td>is_fallback</td>
                      <td class="text-right" :class="player.captainSkillsRaw.is_fallback ? 'text-warning' : ''">
                        {{ player.captainSkillsRaw.is_fallback ? '⚠️ YES (フォールバック使用)' : 'NO' }}
                      </td>
                    </tr>
                    <tr>
                      <td></td>
                      <td>raw_skill_names (内部名)</td>
                      <td class="text-right">
                        <code class="raw-data">{{ JSON.stringify(player.captainSkillsRaw.raw_skill_names || []) }}</code>
                      </td>
                    </tr>
                    <tr>
                      <td></td>
                      <td>all_learned_skills_keys</td>
                      <td class="text-right">
                        <code class="raw-data">{{ JSON.stringify(player.captainSkillsRaw.all_learned_skills_keys || []) }}</code>
                      </td>
                    </tr>
                  </template>
                </tbody>
              </v-table>
            </v-expansion-panel-text>
          </v-expansion-panel>
        </v-expansion-panels>
      </div>
    </template>

  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import type { MatchRecord, PlayerStats, ShipClass } from '~/types/replay'

const props = defineProps<{
  match: MatchRecord
  isPolling?: boolean
}>()

const route = useRoute()
const api = useApi()

// デバッグモード（URLに?debug=trueがある場合に有効）
const isDebugMode = computed(() => route.query.debug === 'true')
const { getShipClassShortLabel, getShipClassIcon } = useShipClass()
const { getSkillName } = useCaptainSkills()
const { getUpgradeName } = useUpgrades()
const config = useRuntimeConfig()

// Stats取得用のstate
const fetchedStats = ref<PlayerStats[]>([])
const isLoadingStats = ref(false)
const statsError = ref<string | null>(null)

// コンポーネントがマウントされた時にstatsを取得
onMounted(async () => {
  // 既にallPlayersStatsがあればfetch不要
  if (props.match.allPlayersStats && props.match.allPlayersStats.length > 0) {
    return
  }

  // arenaUniqueIDがなければfetch不可
  const arenaId = props.match.arenaUniqueID
  if (!arenaId) {
    return
  }

  // statsを取得
  isLoadingStats.value = true
  statsError.value = null

  try {
    const statsData = await api.getMatchStats(arenaId)
    if (statsData && statsData.allPlayersStats) {
      fetchedStats.value = statsData.allPlayersStats
    }
  } catch (err: any) {
    console.error('Failed to fetch stats:', err)
    statsError.value = err.message || 'Stats取得エラー'
  } finally {
    isLoadingStats.value = false
  }
})

// 艦種のソート優先度（空母→戦艦→巡洋艦→駆逐艦→潜水艦）
const SHIP_CLASS_PRIORITY: Record<string, number> = {
  'AirCarrier': 0,
  'Battleship': 1,
  'Cruiser': 2,
  'Destroyer': 3,
  'Submarine': 4,
  'Auxiliary': 5,
}

// v-data-tableのソート状態
const sortBy = ref<{ key: string; order: 'asc' | 'desc' }[]>([])

// カスタムソートが適用されているか
const isCustomSorted = computed(() => sortBy.value.length > 0)

// 全プレイヤー統計（propsまたはfetch結果を使用）
const allPlayersStats = computed(() => {
  // propsにあればそちらを優先
  if (props.match.allPlayersStats && props.match.allPlayersStats.length > 0) {
    return props.match.allPlayersStats
  }
  // なければfetch結果を使用
  return fetchedStats.value
})

// 全プレイヤー統計があるかどうか
const hasAllPlayersStats = computed(() => {
  return allPlayersStats.value && allPlayersStats.value.length > 0
})

// スコアボードのヘッダー（圧縮版）
const scoreboardHeaders = [
  { title: '', key: 'team', sortable: true, width: '30px' },
  { title: 'プレイヤー', key: 'playerName', sortable: true },
  { title: '', key: 'shipClass', sortable: true, width: '30px' },
  { title: '艦船', key: 'shipName', sortable: true },
  { title: '撃沈', key: 'kills', sortable: true, align: 'end' as const, width: '40px' },
  { title: '与ダメ', key: 'damage', sortable: true, align: 'end' as const, width: '65px' },
  { title: '観測', key: 'spottingDamage', sortable: true, align: 'end' as const, width: '55px' },
  { title: '被ダメ', key: 'receivedDamage', sortable: true, align: 'end' as const, width: '55px' },
  { title: '潜在', key: 'potentialDamage', sortable: true, align: 'end' as const, width: '60px' },
  { title: '命中', key: 'totalHits', sortable: true, align: 'end' as const, width: '40px' },
  { title: '火', key: 'fires', sortable: true, align: 'end' as const, width: '30px' },
  { title: '浸', key: 'floods', sortable: true, align: 'end' as const, width: '30px' },
  { title: '貫通', key: 'citadels', sortable: true, align: 'end' as const, width: '35px' },
  { title: 'XP', key: 'baseXP', sortable: true, align: 'end' as const, width: '50px' },
]

// 命中数を計算するヘルパー
const getTotalHits = (player: PlayerStats): number => {
  return (player.hitsAP || 0) + (player.hitsSAP || 0) + (player.hitsHE || 0) +
         (player.hitsSecondariesSAP || 0) + (player.hitsSecondaries || 0)
}

// デフォルトソート: 味方→敵、艦種順、XP順、ダメージ順
const defaultSortedPlayersStats = computed(() => {
  if (!allPlayersStats.value || allPlayersStats.value.length === 0) return []
  return [...allPlayersStats.value]
    .map(p => ({ ...p, totalHits: getTotalHits(p) }))
    .sort((a, b) => {
      // 1. チーム（味方が先）
      const teamOrder = (a.team === 'ally' ? 0 : 1) - (b.team === 'ally' ? 0 : 1)
      if (teamOrder !== 0) return teamOrder

      // 2. 艦種（空母→戦艦→巡洋艦→駆逐艦→潜水艦）
      const classA = SHIP_CLASS_PRIORITY[a.shipClass || ''] ?? 99
      const classB = SHIP_CLASS_PRIORITY[b.shipClass || ''] ?? 99
      if (classA !== classB) return classA - classB

      // 3. 経験値（高い方が先）
      const xpDiff = (b.baseXP || 0) - (a.baseXP || 0)
      if (xpDiff !== 0) return xpDiff

      // 4. ダメージ（高い方が先）
      return (b.damage || 0) - (a.damage || 0)
    })
})

// 表示用のプレイヤー統計（デフォルトソートを使用）
const sortedPlayersStats = computed(() => defaultSortedPlayersStats.value)

// デフォルトソートにリセット
const resetToDefaultSort = () => {
  sortBy.value = []
}

// 数値をカンマ区切りでフォーマット
const formatNumber = (value: number | undefined | null): string => {
  if (value === undefined || value === null) return '0'
  return value.toLocaleString()
}

// プレイヤー詳細情報があるかどうか
const hasPlayerDetails = (player: PlayerStats): boolean => {
  return !!(player.captainSkills?.length || player.upgrades?.length)
}

// 動画タイプ選択（minimap/gameplay）
const selectedVideoType = ref<'minimap' | 'gameplay'>('minimap')

// ミニマップ動画があるリプレイを取得（Dual動画を優先）
const videoReplay = computed(() => {
  if (!props.match.replays) return null
  // まずDual動画を探す
  const dualReplay = props.match.replays.find(r => r.dualMp4S3Key)
  if (dualReplay) return dualReplay
  // なければ通常動画を探す
  return props.match.replays.find(r => r.mp4S3Key) || null
})

// ゲームプレイ動画があるリプレイをすべて取得
const gameplayVideoReplays = computed(() => {
  if (!props.match.replays) return []
  return props.match.replays.filter(r => r.gameplayVideoS3Key)
})

// 選択中のゲームプレイ動画のプレイヤーID
const selectedGameplayPlayerId = ref<number | null>(null)

// ゲームプレイ動画があるリプレイを取得（選択中のプレイヤー）
const gameplayVideoReplay = computed(() => {
  const replays = gameplayVideoReplays.value
  if (replays.length === 0) return null

  // 選択されていない場合は最初のプレイヤーを選択
  if (selectedGameplayPlayerId.value === null) {
    return replays[0]
  }

  // 選択中のプレイヤーの動画を返す
  return replays.find(r => r.playerID === selectedGameplayPlayerId.value) || replays[0]
})

// 複数のゲームプレイ動画があるか
const hasMultipleGameplayVideos = computed(() => gameplayVideoReplays.value.length > 1)

// ゲームプレイ動画プレイヤーの参照（タイムスタンプ維持用）
const gameplayVideoRef = ref<HTMLVideoElement | null>(null)
const savedGameplayTimestamp = ref<number>(0)

// プレイヤー切り替え時のタイムスタンプ保存
const onGameplayPlayerChange = (playerId: number) => {
  // 現在の再生位置を保存
  if (gameplayVideoRef.value) {
    savedGameplayTimestamp.value = gameplayVideoRef.value.currentTime
  }
  selectedGameplayPlayerId.value = playerId
}

// 動画読み込み完了時にタイムスタンプを復元
const onGameplayVideoLoaded = () => {
  if (gameplayVideoRef.value && savedGameplayTimestamp.value > 0) {
    gameplayVideoRef.value.currentTime = savedGameplayTimestamp.value
  }
}

// ミニマップ動画があるかどうか
const hasMinimapVideo = computed(() => {
  return videoReplay.value !== null
})

// ゲームプレイ動画があるかどうか
const hasGameplayVideo = computed(() => {
  return gameplayVideoReplay.value !== null
})

// 何らかの動画があるかどうか
const hasAnyVideo = computed(() => {
  return hasMinimapVideo.value || hasGameplayVideo.value
})

// Dual動画があるかどうか
const isDualVideo = computed(() => {
  return videoReplay.value?.dualMp4S3Key ? true : false
})

// ミニマップ動画URLを生成（Dual優先）
const getVideoUrl = (mp4S3Key: string | undefined) => {
  const replay = videoReplay.value
  // Dual動画があればそちらを優先
  const keyToUse = replay?.dualMp4S3Key || mp4S3Key
  if (!keyToUse) return ''
  // S3バケットURLは環境変数から取得（末尾スラッシュを除去）
  const s3BucketUrl = config.public.s3BucketUrl.replace(/\/+$/, '')
  return `${s3BucketUrl}/${keyToUse}`
}

// ゲームプレイ動画URLを生成
const getGameplayVideoUrl = (s3Key: string | undefined) => {
  if (!s3Key) return ''
  const s3BucketUrl = config.public.s3BucketUrl.replace(/\/+$/, '')
  return `${s3BucketUrl}/${s3Key}`
}

// ファイルサイズをフォーマット
const formatFileSize = (bytes: number | undefined): string => {
  if (!bytes) return ''
  const mb = bytes / (1024 * 1024)
  if (mb >= 1000) {
    return `${(mb / 1024).toFixed(1)} GB`
  }
  return `${mb.toFixed(1)} MB`
}

// リプレイをダウンロード
const downloadReplay = (s3Key: string) => {
  const url = api.getReplayDownloadUrl(s3Key)
  window.open(url, '_blank')
}

// 日時フォーマット
const formatDateTime = (dateTime: string) => {
  if (!dateTime) return '-'

  try {
    const parts = dateTime.match(/(\d{2})\.(\d{2})\.(\d{4}) (\d{2}):(\d{2}):(\d{2})/)
    if (parts) {
      const [_, day, month, year, hour, minute, second] = parts
      return `${year}/${month}/${day} ${hour}:${minute}`
    }

    const date = new Date(dateTime)
    if (!isNaN(date.getTime())) {
      const year = date.getFullYear()
      const month = String(date.getMonth() + 1).padStart(2, '0')
      const day = String(date.getDate()).padStart(2, '0')
      const hour = String(date.getHours()).padStart(2, '0')
      const minute = String(date.getMinutes()).padStart(2, '0')
      return `${year}/${month}/${day} ${hour}:${minute}`
    }
  } catch (e) {
    console.error('Date format error:', e)
  }

  return dateTime
}
</script>

<style scoped>
.scoreboard-table {
  font-size: 0.7rem;
}

.scoreboard-table :deep(th),
.scoreboard-table :deep(td) {
  padding: 2px 4px !important;
  white-space: nowrap;
}

.scoreboard-table :deep(th) {
  font-size: 0.65rem !important;
}

.ship-class-icon {
  width: 20px;
  height: 20px;
  object-fit: contain;
  filter: invert(1);
  opacity: 0.8;
}

.video-container {
  display: flex;
  flex-direction: column;
}

.gameplay-player-toggle {
  flex-wrap: wrap;
}

.gameplay-player-toggle .v-btn {
  text-transform: none;
  font-size: 0.75rem;
}

.video-player {
  width: 100%;
  max-height: calc(100vh - 200px);
  object-fit: contain;
}

.cursor-help {
  cursor: help;
  text-decoration: underline dotted;
  text-underline-offset: 2px;
}

.tooltip-content {
  min-width: 140px;
}

.tooltip-title {
  font-weight: bold;
  margin-bottom: 4px;
  padding-bottom: 4px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.3);
}

.tooltip-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 0.85rem;
  line-height: 1.4;
}

/* プレイヤー詳細ツールチップ */
.player-details-tooltip {
  max-width: 350px;
  background: #ffffff;
  color: #000000;
  padding: 8px;
  border-radius: 4px;
}

.player-details-tooltip .tooltip-title {
  font-weight: bold;
  margin-bottom: 6px;
  padding-bottom: 4px;
  border-bottom: 1px solid #cccccc;
  display: flex;
  align-items: center;
  color: #000000;
}

.captain-skills {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.skill-chip {
  background: #f0f0f0;
  color: #000000;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 0.7rem;
  white-space: nowrap;
}

.upgrades-list {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.upgrade-chip {
  background: #e3f2fd;
  color: #1565c0;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 0.7rem;
  white-space: nowrap;
}

/* デバッグセクション */
.debug-section {
  background: rgba(255, 152, 0, 0.05);
  border: 1px dashed rgba(255, 152, 0, 0.3);
  border-radius: 4px;
  padding: 16px;
}

.debug-table {
  font-size: 0.75rem;
}

.debug-table :deep(th),
.debug-table :deep(td) {
  padding: 4px 8px !important;
}

.debug-table :deep(.category-header td) {
  background: rgba(255, 255, 255, 0.1);
  font-weight: bold;
  padding-top: 12px !important;
}

/* 生データ表示用 */
.raw-data {
  background: rgba(0, 0, 0, 0.3);
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 0.7rem;
  word-break: break-all;
  max-width: 400px;
  display: inline-block;
  text-align: left;
}
</style>
