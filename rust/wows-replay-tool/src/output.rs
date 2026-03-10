//! JSON output types matching the DynamoDB record schema.
//!
//! These types define the contract between the Rust binary and the Python
//! `battle_result_extractor.py` Lambda handler.

use serde::Serialize;

/// Top-level extraction result written to stdout as JSON.
#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ExtractionResult {
    /// Unique arena/match identifier from the replay
    pub arena_unique_id: i64,

    /// Replay metadata
    pub metadata: ReplayMetadata,

    /// Win/loss result: "win", "loss", "draw", or "unknown"
    pub win_loss: String,

    /// Base experience earned (before modifiers)
    pub experience_earned: i64,

    /// All players in the match with their stats and builds
    pub players: Vec<PlayerData>,

    /// Recording player's account ID
    pub self_player_id: i64,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ReplayMetadata {
    pub date_time: String,
    pub game_type: String,
    pub match_group: String,
    pub map_id: String,
    pub map_display_name: String,
    pub client_version: String,
    pub player_name: String,
    pub player_id: i64,
    pub duration: u32,
    pub players_per_team: u32,
    pub scenario: String,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PlayerData {
    pub account_id: i64,
    pub player_name: String,
    pub clan_tag: String,
    pub team_id: u32,
    pub relation: u32,
    pub ship_id: u64,
    pub ship_name: String,
    pub ship_class: String,
    pub max_health: i64,

    /// Combat statistics
    pub stats: PlayerStats,

    /// Build information (captain skills, upgrades, consumables)
    pub build: PlayerBuild,
}

/// Combat statistics matching the DynamoDB field names.
#[derive(Serialize, Default, Clone)]
#[serde(rename_all = "camelCase")]
pub struct PlayerStats {
    // Total damage
    pub damage: i64,

    // Damage breakdown by ammo type
    pub damage_ap: i64,
    pub damage_sap: i64,
    pub damage_he: i64,
    pub damage_sap_secondaries: i64,
    pub damage_he_secondaries: i64,
    pub damage_torps: i64,
    pub damage_deep_water_torps: i64,
    pub damage_fire: i64,
    pub damage_flooding: i64,
    pub damage_other: i64,

    // Received damage breakdown
    pub received_damage: i64,
    pub received_damage_ap: i64,
    pub received_damage_sap: i64,
    pub received_damage_he: i64,
    pub received_damage_torps: i64,
    pub received_damage_deep_water_torps: i64,
    pub received_damage_he_secondaries: i64,
    pub received_damage_sap_secondaries: i64,
    pub received_damage_fire: i64,
    pub received_damage_flood: i64,

    // Hit counts
    pub hits_ap: i64,
    pub hits_sap: i64,
    pub hits_he: i64,
    pub hits_secondaries: i64,
    pub hits_secondaries_sap: i64,

    // Potential damage
    pub potential_damage: i64,
    pub potential_damage_art: i64,
    pub potential_damage_tpd: i64,

    // Spotting
    pub spotting_damage: i64,

    // Ribbons / kill stats
    pub kills: i64,
    pub fires: i64,
    pub floods: i64,
    pub citadels: i64,
    pub crits: i64,

    // XP
    pub base_xp: i64,

    // Survival
    pub life_time_sec: i64,
    pub distance: i64,
}

#[derive(Serialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct PlayerBuild {
    pub captain_skills: Vec<String>,
    pub upgrades: Vec<String>,
    pub consumables: Vec<String>,
    pub signals: Vec<String>,
}
