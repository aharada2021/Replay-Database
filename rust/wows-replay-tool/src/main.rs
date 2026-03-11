mod dump_ship_names;
mod extract;
mod output;
mod render;

use clap::{Parser, Subcommand};
use std::path::PathBuf;

#[derive(Parser)]
#[command(name = "wows-replay-tool", version, about = "WoWS replay extraction and rendering tool")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Parse a replay file and output structured JSON to stdout
    Extract {
        /// Path to the .wowsreplay file
        #[arg(short, long)]
        replay: PathBuf,

        /// Path to pre-extracted game data directory (from wows-data-mgr dump-renderer-data)
        #[arg(short, long)]
        game_data: PathBuf,
    },

    /// Generate a minimap MP4 video from a replay
    Render {
        /// Path to the .wowsreplay file
        #[arg(short, long)]
        replay: PathBuf,

        /// Path to pre-extracted game data directory
        #[arg(short, long)]
        game_data: PathBuf,

        /// Output MP4 file path
        #[arg(short, long)]
        output: PathBuf,
    },

    /// Dump all ship names from game data as JSON mapping { shipId: localizedName }
    DumpShipNames {
        /// Path to pre-extracted game data directory
        #[arg(short, long)]
        game_data: PathBuf,
    },

    /// Print version and check encoder availability
    Check,
}

fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt()
        .with_target(false)
        .with_writer(std::io::stderr)
        .init();

    let cli = Cli::parse();

    match cli.command {
        Commands::Extract { replay, game_data } => {
            extract::run(&replay, &game_data)?;
        }
        Commands::Render {
            replay,
            game_data,
            output,
        } => {
            render::run(&replay, &game_data, &output)?;
        }
        Commands::DumpShipNames { game_data } => {
            dump_ship_names::run(&game_data)?;
        }
        Commands::Check => {
            println!("wows-replay-tool v{}", env!("CARGO_PKG_VERSION"));
            let status = wows_minimap_renderer::check_encoder();
            print!("{status}");
        }
    }

    Ok(())
}
