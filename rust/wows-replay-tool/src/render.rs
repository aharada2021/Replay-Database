//! Minimap video rendering from a .wowsreplay file.

use std::borrow::Cow;
use std::io::Read;
use std::path::Path;

use anyhow::{bail, Context, Result};
use tracing::{info, warn};

use wows_replays::analyzer::battle_controller::BattleController;
use wows_replays::analyzer::Analyzer;
use wows_replays::game_constants::GameConstants;
use wows_replays::ReplayFile;

use wowsunpack::data::{DataFileWithCallback, Version};
use wowsunpack::game_params::provider::GameMetadataProvider;
use wowsunpack::game_params::types::{GameParamProvider, Param};
use wowsunpack::rpc::entitydefs::parse_scripts;
use wowsunpack::vfs::impls::physical::PhysicalFS;
use wowsunpack::vfs::VfsPath;

use wows_minimap_renderer::assets::{
    load_building_icons, load_consumable_icons, load_death_cause_icons, load_flag_icons,
    load_game_fonts, load_map_image, load_map_info, load_packed_image, load_plane_icons,
    load_powerup_icons, load_ship_icons, ICON_SIZE,
};
use wows_minimap_renderer::config::RenderOptions;
use wows_minimap_renderer::drawing::ImageTarget;
use wows_minimap_renderer::renderer::MinimapRenderer;
use wows_minimap_renderer::video::{RenderStage, VideoEncoder};

pub fn run(replay_path: &Path, game_data_dir: &Path, output_path: &Path) -> Result<()> {
    // 1. Parse replay file
    info!("Parsing replay: {}", replay_path.display());
    let replay = ReplayFile::from_file(replay_path)
        .map_err(|e| anyhow::anyhow!("Failed to parse replay file: {e}"))?;

    let replay_version = Version::from_client_exe(&replay.meta.clientVersionFromExe);
    info!(
        "Replay version: {}.{}.{} (build {})",
        replay_version.major, replay_version.minor, replay_version.patch, replay_version.build
    );

    // 2. Load game data
    let resolved_dir = resolve_game_data_dir(game_data_dir, &replay_version)?;
    let (vfs, specs, game_params, controller_game_params) = load_game_data(&resolved_dir)?;

    // 3. Load assets
    info!("Loading fonts and icons");
    let game_fonts = load_game_fonts(&vfs);
    let ship_icons = load_ship_icons(&vfs);
    let plane_icons = load_plane_icons(&vfs);
    let building_icons = load_building_icons(&vfs);
    let consumable_icons = load_consumable_icons(&vfs);
    let death_cause_icons = load_death_cause_icons(&vfs, ICON_SIZE);
    let powerup_icons = load_powerup_icons(&vfs, ICON_SIZE);
    let flag_icons = load_flag_icons(&vfs);

    // 4. Load game constants and map data
    let game_constants = GameConstants::from_vfs(&vfs);
    let map_name = &replay.meta.mapName;
    let map_image = load_map_image(map_name, &vfs);
    let map_info = load_map_info(map_name, &vfs);

    // 5. Create render target
    let options = RenderOptions::default();
    let mut target = ImageTarget::with_stats_panel(
        map_image,
        game_fonts.clone(),
        ship_icons,
        plane_icons,
        building_icons,
        consumable_icons,
        death_cause_icons,
        powerup_icons,
        options.show_stats_panel,
    );

    // 6. Load self player silhouette for stats panel
    let self_silhouette = replay
        .meta
        .vehicles
        .iter()
        .find(|v| v.relation == 0)
        .and_then(|v| {
            let param = GameParamProvider::game_param_by_id(&game_params, v.shipId)?;
            let path = format!("gui/ships_silhouettes/{}.png", param.index());
            let img = load_packed_image(&path, &vfs)?;
            Some(img.into_rgba8())
        });

    // 7. Create renderer
    let mut renderer =
        MinimapRenderer::new(map_info, &game_params, replay_version, options);
    renderer.set_fonts(game_fonts);
    renderer.set_flag_icons(flag_icons);
    if let Some(sil) = self_silhouette {
        renderer.set_self_silhouette(sil);
    }

    // 8. Create video encoder
    let game_duration = replay.meta.duration as f32;
    let (cw, ch) = target.canvas_size();
    let output_str = output_path
        .to_str()
        .context("Output path must be valid UTF-8")?;
    let mut encoder = VideoEncoder::new(output_str, None, game_duration, cw, ch);
    encoder.set_prefer_cpu(true); // Use CPU encoder for compatibility
    encoder.init().map_err(|e| anyhow::anyhow!("Encoder init failed: {e}"))?;

    // Progress callback (log-based)
    encoder.set_progress_callback(move |p| {
        if p.current % 100 == 0 || p.current == p.total {
            let stage = match p.stage {
                RenderStage::Encoding => "Encoding",
                RenderStage::Muxing => "Muxing",
            };
            eprintln!("{}: {}/{}", stage, p.current, p.total);
        }
    });

    // 9. Pre-scan packets for accurate progress
    {
        let mut scan_parser = wows_replays::packet2::Parser::new(&specs);
        let mut scan_remaining = &replay.packet_data[..];
        let mut last_clock = wows_replays::types::GameClock(0.0);
        while !scan_remaining.is_empty() {
            match scan_parser.parse_packet(&mut scan_remaining) {
                Ok(packet) => {
                    last_clock =
                        wows_replays::types::GameClock(packet.clock.0.max(last_clock.0));
                }
                Err(_) => break,
            }
        }
        if last_clock.seconds() > 0.0 {
            encoder.set_battle_duration(last_clock);
        }
    }

    // 10. Process packets and render frames
    info!("Rendering minimap video");
    let mut controller =
        BattleController::new(&replay.meta, &controller_game_params, Some(&game_constants));

    let mut parser = wows_replays::packet2::Parser::new(&specs);
    let mut remaining = &replay.packet_data[..];
    let mut prev_clock = wows_replays::types::GameClock(0.0);

    while !remaining.is_empty() {
        match parser.parse_packet(&mut remaining) {
            Ok(packet) => {
                // Render when clock changes
                if packet.clock != prev_clock && prev_clock.seconds() > 0.0 {
                    renderer.populate_players(&controller);
                    renderer.update_squadron_info(&controller);
                    renderer.update_ship_abilities(&controller);
                    encoder.advance_clock(
                        prev_clock,
                        &controller,
                        &mut renderer,
                        &mut target,
                    );
                    prev_clock = packet.clock;
                } else if prev_clock.seconds() == 0.0 {
                    prev_clock = packet.clock;
                }

                // Process packet (catch panics from decoder bugs)
                let _ = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
                    controller.process(&packet);
                }));
            }
            Err(_) => break,
        }
    }

    // Render final tick
    if prev_clock.seconds() > 0.0 {
        renderer.populate_players(&controller);
        renderer.update_squadron_info(&controller);
        renderer.update_ship_abilities(&controller);
        encoder.advance_clock(prev_clock, &controller, &mut renderer, &mut target);
    }

    controller.finish();
    encoder
        .finish(&controller, &mut renderer, &mut target)
        .map_err(|e| anyhow::anyhow!("Encoder finish failed: {e}"))?;

    info!("Rendered to {}", output_path.display());
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
        warn!(
            "No exact build match for replay (build {}). Using available data.",
            version.build
        );
        return Ok(candidates[0].0.clone());
    }
    if candidates.is_empty() {
        bail!("No extracted game data found in {}.", base.display());
    }
    bail!("No game data matches replay build {}.", version.build);
}

/// Load game data from a pre-extracted directory.
fn load_game_data(
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

    let rkyv_path = extracted_dir.join("game_params.rkyv");
    info!("Loading game params from {}", rkyv_path.display());
    let rkyv_data = std::fs::read(&rkyv_path)
        .with_context(|| format!("Failed to read {}", rkyv_path.display()))?;
    let params: Vec<Param> = rkyv::from_bytes::<Vec<Param>, rkyv::rancor::Error>(&rkyv_data)
        .map_err(|e| anyhow::anyhow!("Failed to deserialize GameParams: {e}"))?;

    let game_params = GameMetadataProvider::from_params_no_specs(params.clone())
        .map_err(|e| anyhow::anyhow!("Failed to build GameMetadataProvider: {e:?}"))?;
    let controller_game_params = GameMetadataProvider::from_params_no_specs(params)
        .map_err(|e| anyhow::anyhow!("Failed to build controller GameMetadataProvider: {e:?}"))?;

    // Load translations
    let mo_path = extracted_dir.join("translations/en/LC_MESSAGES/global.mo");
    if mo_path.exists() {
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
    } else {
        warn!("Translations not found at {}", mo_path.display());
    }

    Ok((vfs, specs, game_params, controller_game_params))
}
