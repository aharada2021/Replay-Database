//! Replay extraction: parse a .wowsreplay file and output structured JSON.

use std::borrow::Cow;
use std::io::Read;
use std::path::Path;

use std::collections::HashMap;

use anyhow::{bail, Context, Result};
use tracing::info;

use wows_replays::analyzer::battle_controller::BattleResult;
use wows_replays::analyzer::battle_controller::BattleController;
use wows_replays::analyzer::Analyzer;
use wows_replays::game_constants::GameConstants;
use wows_replays::ReplayFile;

use wowsunpack::data::DataFileWithCallback;
use wowsunpack::data::Version;
use wowsunpack::game_params::provider::GameMetadataProvider;
use wowsunpack::game_params::types::{GameParamProvider, Param, Species};
use wowsunpack::game_types::{DamageStatCategory, DamageStatWeapon};
use wowsunpack::recognized::Recognized;
use wowsunpack::rpc::entitydefs::parse_scripts;
use wowsunpack::vfs::VfsPath;
use wowsunpack::vfs::impls::physical::PhysicalFS;

use wowsunpack::data::ResourceLoader;
use wowsunpack::game_params::translations::{translate_map_name, translate_module, translate_consumable};

use crate::output::*;

pub fn run(replay_path: &Path, game_data_dir: &Path) -> Result<()> {
    // 1. Parse replay file
    info!("Parsing replay: {}", replay_path.display());
    let replay = ReplayFile::from_file(replay_path)
        .map_err(|e| anyhow::anyhow!("Failed to parse replay file: {e}"))?;

    let replay_version = Version::from_client_exe(&replay.meta.clientVersionFromExe);
    info!(
        "Replay version: {}.{}.{} (build {})",
        replay_version.major, replay_version.minor, replay_version.patch, replay_version.build
    );

    // 2. Load game data from extracted directory
    let resolved_dir = resolve_game_data_dir(game_data_dir, &replay_version)?;
    let (vfs, specs, game_params, controller_game_params) =
        load_extracted_game_data(&resolved_dir)?;

    // 3. Load game constants from VFS
    let game_constants = GameConstants::from_vfs(&vfs);

    // 4. Run BattleController analysis
    info!("Analyzing replay packets");
    let mut controller =
        BattleController::new(&replay.meta, &controller_game_params, Some(&game_constants));

    let mut parser = wows_replays::packet2::Parser::new(&specs);
    let mut remaining = &replay.packet_data[..];
    let mut packet_count = 0u64;
    let mut error_count = 0u64;

    while !remaining.is_empty() {
        match parser.parse_packet(&mut remaining) {
            Ok(packet) => {
                // controller.process() may panic on unexpected data formats
                let result = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
                    controller.process(&packet);
                }));
                if result.is_err() {
                    error_count += 1;
                    // Continue processing remaining packets
                }
                packet_count += 1;
            }
            Err(_) => {
                error_count += 1;
                break;
            }
        }
    }
    controller.finish();
    info!(
        "Processed {} packets ({} errors)",
        packet_count, error_count
    );

    // 5. Build report (consumes controller)
    let report = controller.build_report();

    // 6. Build output from report
    let result = build_extraction_result(&replay, &report, &game_params)?;

    // 7. Write JSON to stdout
    serde_json::to_writer(std::io::stdout().lock(), &result)?;

    Ok(())
}

/// Resolve the game data directory, handling version subdirectories.
fn resolve_game_data_dir(base: &Path, version: &Version) -> Result<std::path::PathBuf> {
    if base.join("metadata.toml").exists() {
        return Ok(base.to_path_buf());
    }

    let entries = std::fs::read_dir(base)
        .with_context(|| format!("Failed to read game data directory: {}", base.display()))?;

    let mut candidates: Vec<(std::path::PathBuf, u32)> = Vec::new();
    for entry in entries.flatten() {
        let sub = entry.path();
        if sub.join("metadata.toml").exists() {
            if let Ok(contents) = std::fs::read_to_string(sub.join("metadata.toml")) {
                let build = contents
                    .lines()
                    .find_map(|l| l.strip_prefix("build = ").map(|b| b.trim().parse().unwrap_or(0)))
                    .unwrap_or(0);
                candidates.push((sub, build));
            }
        }
    }

    if let Some(matched) = candidates.iter().find(|(_, b)| *b == version.build) {
        return Ok(matched.0.clone());
    }
    if candidates.len() == 1 {
        return Ok(candidates[0].0.clone());
    }
    if candidates.is_empty() {
        bail!("No extracted game data found in {}.", base.display());
    }
    bail!("No game data matches replay build {}.", version.build);
}

/// Load game data from a pre-extracted directory (dump-renderer-data output).
fn load_extracted_game_data(
    extracted_dir: &Path,
) -> Result<(
    VfsPath,
    Vec<wowsunpack::rpc::entitydefs::EntitySpec>,
    GameMetadataProvider,
    GameMetadataProvider,
)> {
    let vfs_root = extracted_dir.join("vfs");
    if !vfs_root.exists() {
        bail!("VFS directory not found: {}", vfs_root.display());
    }
    let vfs = VfsPath::new(PhysicalFS::new(&vfs_root));

    info!("Loading entity specs");
    let specs = {
        let vfs_ref = &vfs;
        let loader = DataFileWithCallback::new(move |path: &str| {
            let mut data = Vec::new();
            vfs_ref.join(path)?.open_file()?.read_to_end(&mut data)?;
            Ok(Cow::Owned(data))
        });
        parse_scripts(&loader).context("Failed to parse entity specs")?
    };

    for (i, spec) in specs.iter().enumerate() {
        info!(
            "Entity[{}] {}: {} properties, {} internal_properties, {} base_properties, {} client_methods",
            i, spec.name, spec.properties.len(), spec.internal_properties.len(),
            spec.base_properties.len(), spec.client_methods.len()
        );
    }

    let rkyv_path = extracted_dir.join("game_params.rkyv");
    info!("Loading game params from {}", rkyv_path.display());
    let rkyv_data = std::fs::read(&rkyv_path)
        .with_context(|| format!("Failed to read {}", rkyv_path.display()))?;

    let params: Vec<Param> =
        rkyv::from_bytes::<Vec<Param>, rkyv::rancor::Error>(&rkyv_data)
            .map_err(|e| anyhow::anyhow!("Failed to deserialize GameParams: {e}"))?;

    let game_params = GameMetadataProvider::from_params_no_specs(params.clone())
        .map_err(|e| anyhow::anyhow!("Failed to build GameMetadataProvider: {e:?}"))?;
    let controller_game_params = GameMetadataProvider::from_params_no_specs(params)
        .map_err(|e| anyhow::anyhow!("Failed to build controller GameMetadataProvider: {e:?}"))?;

    // Load translations (prefer ja, fallback to en)
    let lang = std::env::var("WOWS_LANG").unwrap_or_else(|_| "ja".to_string());
    let mo_path = extracted_dir.join(format!("translations/{lang}/LC_MESSAGES/global.mo"));
    let mo_path = if mo_path.exists() {
        mo_path
    } else {
        info!("Translation not found for '{lang}', falling back to 'en'");
        extracted_dir.join("translations/en/LC_MESSAGES/global.mo")
    };
    if mo_path.exists() {
        info!("Loading translations from {}", mo_path.display());
        if let Ok(file) = std::fs::File::open(&mo_path) {
            if let Ok(catalog) = gettext::Catalog::parse(file) {
                game_params.set_translations(catalog);
            }
        }
        if let Ok(file2) = std::fs::File::open(&mo_path) {
            if let Ok(catalog2) = gettext::Catalog::parse(file2) {
                controller_game_params.set_translations(catalog2);
            }
        }
    }

    Ok((vfs, specs, game_params, controller_game_params))
}

/// Build the structured extraction result from BattleReport.
fn build_extraction_result(
    replay: &ReplayFile,
    report: &wows_replays::analyzer::battle_controller::BattleReport,
    game_params: &GameMetadataProvider,
) -> Result<ExtractionResult> {
    let meta = &replay.meta;
    let game_type = classify_game_type(&meta.matchGroup, &meta.gameType);

    // Translate map display name (e.g. "20_NE_two_brothers" -> "二人の兄弟")
    let map_display_name = translate_map_name(&format!("spaces/{}", meta.mapName), game_params);

    let metadata = ReplayMetadata {
        date_time: meta.dateTime.clone(),
        game_type: game_type.clone(),
        match_group: meta.matchGroup.clone(),
        map_id: meta.mapName.clone(),
        map_display_name,
        client_version: meta.clientVersionFromExe.replace(',', "."),
        player_name: meta.playerName.clone(),
        player_id: meta.playerID.0,
        duration: meta.duration,
        players_per_team: meta.playersPerTeam,
        scenario: meta.scenario.clone(),
    };

    // Win/loss from BattleResult
    let win_loss = match report.battle_result() {
        Some(BattleResult::Win(_)) => "win",
        Some(BattleResult::Loss(_)) => "loss",
        Some(BattleResult::Draw) => "draw",
        None => "unknown",
    }
    .to_string();

    // Parse battle_results JSON
    let battle_results_json: Option<serde_json::Value> = report
        .battle_results()
        .and_then(|raw| serde_json::from_str(raw).ok());

    // Experience from raw battle_results JSON
    let experience = battle_results_json
        .as_ref()
        .and_then(|v| {
            v.get("privateDataList")?
                .get(7)?
                .get(0)?
                .as_i64()
                .map(|x| x / 10)
        })
        .unwrap_or(0);

    // Parse playersPublicInfo for all player stats
    let public_stats = parse_players_public_info(&battle_results_json);

    // Build player data from report + battle_results stats
    let players = build_player_data(report, game_params, &public_stats)?;

    Ok(ExtractionResult {
        arena_unique_id: report.arena_id(),
        metadata,
        win_loss,
        experience_earned: experience,
        players,
        self_player_id: meta.playerID.0,
    })
}

fn classify_game_type(match_group: &str, game_type: &str) -> String {
    match match_group {
        "clan" => "clan",
        "ranked" => "ranked",
        "cooperative" => "cooperative",
        _ if game_type.contains("pvp") => "pvp",
        _ => "other",
    }
    .to_string()
}

fn build_player_data(
    report: &wows_replays::analyzer::battle_controller::BattleReport,
    game_params: &GameMetadataProvider,
    public_stats: &HashMap<i64, PlayerStats>,
) -> Result<Vec<PlayerData>> {
    let mut players = Vec::new();

    for player in report.players() {
        let initial = player.initial_state();
        let vehicle = player.vehicle();

        // Resolve ship name from GameParams (localized display name)
        let ship_name = GameParamProvider::game_param_by_id(game_params, vehicle.id())
            .map(|p| {
                game_params
                    .localized_name_from_param(&p)
                    .unwrap_or_else(|| p.name().to_string())
            })
            .unwrap_or_default();

        // Resolve ship class from species
        let ship_class = vehicle
            .species()
            .and_then(|s| s.known().cloned())
            .map(species_to_class_name)
            .unwrap_or_default();

        let species = vehicle
            .species()
            .and_then(|s| s.known().cloned());

        // Extract build
        let build = extract_player_build(player.vehicle_entity(), species, game_params);

        // Extract stats from battle_results playersPublicInfo
        let account_id = initial.db_id().0;
        let is_self = player.relation().value() == 0;
        let stats = if is_self {
            // For self player: merge self_damage_stats (server-authoritative damage)
            // with battle_results (received damage, hits, kills, etc.)
            build_self_stats(report, public_stats.get(&account_id))
        } else {
            // For other players: use battle_results stats
            public_stats.get(&account_id).cloned().unwrap_or_default()
        };

        players.push(PlayerData {
            account_id,
            player_name: initial.username().to_string(),
            clan_tag: initial.clan().to_string(),
            team_id: initial.team_id() as u32,
            relation: player.relation().value(),
            ship_id: vehicle.id().raw(),
            ship_name,
            ship_class,
            max_health: initial.max_health(),
            stats,
            build,
        });
    }

    Ok(players)
}

fn species_to_class_name(species: Species) -> String {
    match species {
        Species::Destroyer => "Destroyer",
        Species::Cruiser => "Cruiser",
        Species::Battleship => "Battleship",
        Species::AirCarrier => "AirCarrier",
        Species::Submarine => "Submarine",
        Species::Auxiliary => "Auxiliary",
        _ => "",
    }
    .to_string()
}

fn extract_player_build(
    vehicle_entity: Option<&wows_replays::analyzer::battle_controller::VehicleEntity>,
    species: Option<Species>,
    game_params: &GameMetadataProvider,
) -> PlayerBuild {
    let mut build = PlayerBuild::default();

    let ve = match vehicle_entity {
        Some(ve) => ve,
        None => return build,
    };

    // Captain skills (translated display names)
    if let Some(sp) = species {
        if let Some(skills) = ve.commander_skills(sp) {
            build.captain_skills = skills
                .iter()
                .map(|s| {
                    s.translated_name(game_params)
                        .unwrap_or_else(|| s.internal_name().to_string())
                })
                .collect();
        }
    }

    // Ship config
    let config = ve.props().ship_config();

    // Modernizations/upgrades (translated display names)
    build.upgrades = config
        .modernization()
        .iter()
        .filter_map(|id| {
            GameParamProvider::game_param_by_id(game_params, *id).map(|p| {
                let (name, _desc) = translate_module(p.name(), game_params);
                name.unwrap_or_else(|| p.name().to_string())
            })
        })
        .collect();

    // Consumables (translated display names)
    build.consumables = config
        .abilities()
        .iter()
        .filter_map(|id| {
            GameParamProvider::game_param_by_id(game_params, *id).map(|p| {
                translate_consumable(p.name(), game_params)
                    .unwrap_or_else(|| p.name().to_string())
            })
        })
        .collect();

    // Signals/exteriors (translated display names)
    build.signals = config
        .exteriors()
        .iter()
        .filter_map(|id| {
            GameParamProvider::game_param_by_id(game_params, *id).map(|p| {
                game_params
                    .localized_name_from_param(&p)
                    .unwrap_or_else(|| p.name().to_string())
            })
        })
        .collect();

    build
}

/// Build stats for the self (recording) player.
/// Uses server-authoritative damage stats from packets for dealt damage,
/// and battle_results for everything else (received damage, hits, kills, etc.).
fn build_self_stats(
    report: &wows_replays::analyzer::battle_controller::BattleReport,
    public: Option<&PlayerStats>,
) -> PlayerStats {
    // Start with battle_results stats as base (has received damage, hits, kills, etc.)
    let mut stats = public.cloned().unwrap_or_default();

    // Override dealt damage with server-authoritative self_damage_stats
    // (more accurate than battle_results for the recording player)
    let has_damage_stats = !report.self_damage_stats().is_empty();
    if has_damage_stats {
        // Reset dealt damage fields before re-populating from damage stats
        stats.damage = 0;
        stats.damage_ap = 0;
        stats.damage_sap = 0;
        stats.damage_he = 0;
        stats.damage_sap_secondaries = 0;
        stats.damage_he_secondaries = 0;
        stats.damage_torps = 0;
        stats.damage_deep_water_torps = 0;
        stats.damage_fire = 0;
        stats.damage_flooding = 0;
        stats.damage_other = 0;
        stats.spotting_damage = 0;
        stats.potential_damage_art = 0;
        stats.potential_damage_tpd = 0;

        for entry in report.self_damage_stats() {
            let amount = entry.total as i64;
            let is_enemy = matches!(entry.category.known(), Some(&DamageStatCategory::Enemy));
            let is_spot = matches!(entry.category.known(), Some(&DamageStatCategory::Spot));
            let is_agro = matches!(entry.category.known(), Some(&DamageStatCategory::Agro));

            if is_enemy {
                stats.damage += amount;
                categorize_damage_dealt(&mut stats, &entry.weapon, amount);
            } else if is_spot {
                stats.spotting_damage += amount;
            } else if is_agro {
                categorize_potential_damage(&mut stats, &entry.weapon, amount);
            }
        }

        stats.potential_damage = stats.potential_damage_art + stats.potential_damage_tpd;
    }

    // Override kills from report frags if available
    let self_player = report.self_player();
    if let Some(frags) = report.frags().get(self_player) {
        stats.kills = frags.len() as i64;
    }

    stats
}

fn categorize_damage_dealt(stats: &mut PlayerStats, weapon: &Recognized<DamageStatWeapon>, amount: i64) {
    match weapon.known() {
        Some(DamageStatWeapon::MainAp) | Some(DamageStatWeapon::MainAiAp) => stats.damage_ap += amount,
        Some(DamageStatWeapon::MainHe) | Some(DamageStatWeapon::MainAiHe) => stats.damage_he += amount,
        Some(DamageStatWeapon::MainCs) => stats.damage_sap += amount,
        Some(DamageStatWeapon::AtbaHe) => stats.damage_he_secondaries += amount,
        Some(DamageStatWeapon::AtbaCs) | Some(DamageStatWeapon::AtbaAp) => stats.damage_sap_secondaries += amount,
        Some(DamageStatWeapon::TorpedoDeep) => stats.damage_deep_water_torps += amount,
        Some(DamageStatWeapon::Torpedo)
        | Some(DamageStatWeapon::TorpedoAcc)
        | Some(DamageStatWeapon::TorpedoAlter)
        | Some(DamageStatWeapon::TorpedoMag)
        | Some(DamageStatWeapon::TorpedoAccOff)
        | Some(DamageStatWeapon::TorpedoPhoton) => stats.damage_torps += amount,
        Some(DamageStatWeapon::Burn) => stats.damage_fire += amount,
        Some(DamageStatWeapon::Flood) => stats.damage_flooding += amount,
        _ => stats.damage_other += amount,
    }
}

fn categorize_potential_damage(stats: &mut PlayerStats, weapon: &Recognized<DamageStatWeapon>, amount: i64) {
    match weapon.known() {
        Some(DamageStatWeapon::Torpedo)
        | Some(DamageStatWeapon::TorpedoAcc)
        | Some(DamageStatWeapon::TorpedoDeep)
        | Some(DamageStatWeapon::TorpedoAlter)
        | Some(DamageStatWeapon::TorpedoMag)
        | Some(DamageStatWeapon::TorpedoAccOff)
        | Some(DamageStatWeapon::TorpedoPhoton) => stats.potential_damage_tpd += amount,
        _ => stats.potential_damage_art += amount,
    }
}

/// Parse playersPublicInfo from battle_results JSON into per-player stats.
/// Each player's data is an array of 460+ elements with stats at fixed indices.
fn parse_players_public_info(
    battle_results: &Option<serde_json::Value>,
) -> HashMap<i64, PlayerStats> {
    let mut result = HashMap::new();

    let players_info = match battle_results
        .as_ref()
        .and_then(|v| v.get("playersPublicInfo"))
        .and_then(|v| v.as_object())
    {
        Some(info) => info,
        None => return result,
    };

    for (_player_id, player_data) in players_info {
        let arr = match player_data.as_array() {
            Some(a) if a.len() >= 460 => a,
            _ => continue,
        };

        let account_id = val_i64(arr, 0);
        if account_id == 0 {
            continue;
        }

        // Index mapping from wows-toolkit/embedded_resources/constants.json
        // CLIENT_PUBLIC_RESULTS_INDICES (15.x format)
        let received_damage_ap = val_i64(arr, 199);       // received_damage_main_ap
        let received_damage_sap = val_i64(arr, 200);      // received_damage_main_cs
        let received_damage_he = val_i64(arr, 201);       // received_damage_main_he
        let received_damage_torps = val_i64(arr, 202);    // received_damage_tpd_normal
        let received_damage_deep_water_torps = val_i64(arr, 203); // received_damage_tpd_deep
        let received_damage_sap_secondaries = val_i64(arr, 215);  // received_damage_atba_cs
        let received_damage_he_secondaries = val_i64(arr, 216);   // received_damage_atba_he
        let received_damage_fire = val_i64(arr, 220);     // received_damage_fire
        let received_damage_flood = val_i64(arr, 221);    // received_damage_flood
        let received_damage = received_damage_ap
            + received_damage_sap
            + received_damage_he
            + received_damage_torps
            + received_damage_deep_water_torps
            + received_damage_sap_secondaries
            + received_damage_he_secondaries
            + received_damage_fire
            + received_damage_flood;

        let potential_damage_art = val_i64(arr, 416);     // agro_art
        let potential_damage_tpd = val_i64(arr, 417);     // agro_tpd

        let stats = PlayerStats {
            // Total damage
            damage: val_i64(arr, 426),                     // damage
            // Damage breakdown
            damage_ap: val_i64(arr, 155),                  // damage_main_ap
            damage_sap: val_i64(arr, 156),                 // damage_main_cs
            damage_he: val_i64(arr, 157),                  // damage_main_he
            damage_sap_secondaries: val_i64(arr, 159),     // damage_atba_cs
            damage_he_secondaries: val_i64(arr, 160),      // damage_atba_he
            damage_torps: val_i64(arr, 164),               // damage_tpd_normal
            damage_deep_water_torps: val_i64(arr, 165),    // damage_tpd_deep
            damage_other: 0,                               // computed below
            damage_fire: val_i64(arr, 176),                // damage_fire
            damage_flooding: val_i64(arr, 177),            // damage_flood
            // Received damage
            received_damage,
            received_damage_ap,
            received_damage_sap,
            received_damage_he,
            received_damage_torps,
            received_damage_deep_water_torps,
            received_damage_he_secondaries,
            received_damage_sap_secondaries,
            received_damage_fire,
            received_damage_flood,
            // Hits
            hits_ap: val_i64(arr, 66),                     // hits_main_ap
            hits_sap: val_i64(arr, 67),                    // hits_main_cs
            hits_he: val_i64(arr, 68),                     // hits_main_he
            hits_secondaries_sap: val_i64(arr, 70),        // hits_atba_cs
            hits_secondaries: val_i64(arr, 71),            // hits_atba_he
            // Potential damage
            potential_damage: potential_damage_art + potential_damage_tpd,
            potential_damage_art,
            potential_damage_tpd,
            // Spotting
            spotting_damage: val_i64(arr, 412),            // scouting_damage
            // Ribbons
            kills: val_i64(arr, 451),                      // RIBBON_FRAG
            fires: val_i64(arr, 452),                      // RIBBON_BURN
            floods: val_i64(arr, 453),                     // RIBBON_FLOOD
            citadels: val_i64(arr, 454),                   // RIBBON_CITADEL
            crits: val_i64(arr, 450),                      // RIBBON_CRIT
            // XP
            base_xp: val_i64(arr, 404),                   // exp
            // Survival
            life_time_sec: val_i64(arr, 22),               // life_time_sec
            distance: val_i64(arr, 23),                    // distance
        };

        result.insert(account_id, stats);
    }

    result
}

/// Safely extract an i64 value from a JSON array at the given index.
fn val_i64(arr: &[serde_json::Value], index: usize) -> i64 {
    arr.get(index)
        .and_then(|v| v.as_i64().or_else(|| v.as_f64().map(|f| f as i64)))
        .unwrap_or(0)
}
