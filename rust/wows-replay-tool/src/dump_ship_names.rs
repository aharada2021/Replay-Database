//! Dump all ship names from game data as a JSON mapping: { shipId: localizedName }.

use std::borrow::Cow;
use std::collections::BTreeMap;
use std::io::Read;
use std::path::Path;

use anyhow::{bail, Context, Result};
use tracing::info;

use wowsunpack::data::DataFileWithCallback;
use wowsunpack::game_params::provider::GameMetadataProvider;
use wowsunpack::game_params::types::{GameParamProvider, Param, Species};
use wowsunpack::rpc::entitydefs::parse_scripts;
use wowsunpack::vfs::VfsPath;
use wowsunpack::vfs::impls::physical::PhysicalFS;

use wowsunpack::data::ResourceLoader;

/// Ship species that represent playable/relevant ship types.
const SHIP_SPECIES: &[Species] = &[
    Species::Destroyer,
    Species::Cruiser,
    Species::Battleship,
    Species::AirCarrier,
    Species::Submarine,
    Species::Auxiliary,
];

pub fn run(game_data_dir: &Path) -> Result<()> {
    let mut all_mappings: BTreeMap<u64, String> = BTreeMap::new();

    // Iterate all version subdirectories (or use base if it has metadata.toml)
    let dirs = collect_game_data_dirs(game_data_dir)?;

    for dir in &dirs {
        info!("Loading game data from {}", dir.display());
        let game_params = load_game_params(dir)?;

        let params = GameParamProvider::params(&game_params);
        for param in params {
            let is_ship = param
                .species()
                .and_then(|s| s.known())
                .map(|s| SHIP_SPECIES.contains(s))
                .unwrap_or(false);

            if !is_ship {
                continue;
            }

            let ship_id = param.id().raw();
            if all_mappings.contains_key(&ship_id) {
                continue;
            }

            let localized = game_params
                .localized_name_from_param(&param)
                .unwrap_or_else(|| param.name().to_string());

            all_mappings.insert(ship_id, localized);
        }
    }

    info!("Found {} ship names across {} game data dirs", all_mappings.len(), dirs.len());

    serde_json::to_writer_pretty(std::io::stdout().lock(), &all_mappings)?;

    Ok(())
}

/// Collect all game data directories that contain metadata.toml.
fn collect_game_data_dirs(base: &Path) -> Result<Vec<std::path::PathBuf>> {
    if base.join("metadata.toml").exists() {
        return Ok(vec![base.to_path_buf()]);
    }

    let entries = std::fs::read_dir(base)
        .with_context(|| format!("Failed to read game data directory: {}", base.display()))?;

    let mut dirs = Vec::new();
    for entry in entries.flatten() {
        let sub = entry.path();
        if sub.join("metadata.toml").exists() {
            dirs.push(sub);
        }
    }

    if dirs.is_empty() {
        bail!("No extracted game data found in {}.", base.display());
    }

    Ok(dirs)
}

/// Load GameMetadataProvider with English translations from a single game data directory.
fn load_game_params(extracted_dir: &Path) -> Result<GameMetadataProvider> {
    let vfs_root = extracted_dir.join("vfs");
    if !vfs_root.exists() {
        bail!("VFS directory not found: {}", vfs_root.display());
    }
    let vfs = VfsPath::new(PhysicalFS::new(&vfs_root));

    // Load entity specs (required for GameMetadataProvider construction)
    let _specs = {
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

    let params: Vec<Param> =
        rkyv::from_bytes::<Vec<Param>, rkyv::rancor::Error>(&rkyv_data)
            .map_err(|e| anyhow::anyhow!("Failed to deserialize GameParams: {e}"))?;

    let game_params = GameMetadataProvider::from_params_no_specs(params)
        .map_err(|e| anyhow::anyhow!("Failed to build GameMetadataProvider: {e:?}"))?;

    // Load English translations
    let mo_path = extracted_dir.join("translations/en/LC_MESSAGES/global.mo");
    if mo_path.exists() {
        info!("Loading translations from {}", mo_path.display());
        if let Ok(file) = std::fs::File::open(&mo_path) {
            if let Ok(catalog) = gettext::Catalog::parse(file) {
                game_params.set_translations(catalog);
            }
        }
    }

    Ok(game_params)
}
