use clap::Parser;

/// SchoolApp portal client, grade watcher and API.
#[derive(Parser)]
#[command(name = "schoolapp-rs", version)]
struct Cli {}

fn main() {
    Cli::parse();
}
