use std::path::Path;
use std::process::ExitCode;
use std::time::Duration;

use clap::{Args, Parser, Subcommand};
use schoolapp::client::{Client, SCHOOLAPP_BASE};
use schoolapp::models::StudentData;
use schoolapp::store::{save_student_data, state_dir};
use schoolapp::ureq_http::UreqHttp;

/// SchoolApp portal client, grade watcher and API.
#[derive(Parser)]
#[command(name = "schoolapp-rs", version)]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand)]
enum Command {
    /// Fetch every per-student resource; persist to the store unless --no-save.
    FetchAll(FetchAllArgs),
}

#[derive(Args)]
struct FetchAllArgs {
    /// SchoolApp email (overrides SCHOOLAPP_EMAIL)
    #[arg(long)]
    email: Option<String>,
    /// SchoolApp password (overrides SCHOOLAPP_PASSWORD)
    #[arg(long)]
    password: Option<String>,
    /// HTTP timeout in seconds
    #[arg(long, default_value_t = 20, value_parser = clap::value_parser!(u64).range(5..))]
    timeout: u64,
    /// Include past-year grade pages (default)
    #[arg(long = "history", overrides_with = "no_history")]
    _history: bool,
    /// Skip past-year grade pages
    #[arg(long)]
    no_history: bool,
    /// Also fetch per-element statistics popups
    #[arg(long)]
    stats: bool,
    /// Persist to the state store (default)
    #[arg(long = "save", overrides_with = "no_save")]
    _save: bool,
    /// Do not write the state store
    #[arg(long)]
    no_save: bool,
    /// Print a JSON summary instead of the table
    #[arg(long)]
    json: bool,
}

fn utc_now() -> String {
    chrono::Utc::now().format("%Y-%m-%dT%H:%M:%S+00:00").to_string()
}

fn from_flag_or_env(flag: Option<String>, var: &str) -> Option<String> {
    flag.or_else(|| std::env::var(var).ok()).filter(|v| !v.is_empty())
}

fn counts(data: &StudentData) -> [(&'static str, usize); 10] {
    [
        ("element_grades", data.element_grades.len()),
        ("module_grades", data.module_grades.len()),
        ("semester_results", data.semester_results.len()),
        ("year_results", data.year_results.len()),
        ("absences", data.absences.len()),
        ("absence_summary", data.absence_summary.len()),
        ("sanctions", data.sanctions.len()),
        ("courses", data.courses.len()),
        ("stats", data.stats.len()),
        ("documents", data.documents.len()),
    ]
}

fn diploma_state(data: &StudentData) -> Option<&'static str> {
    data.diploma.as_ref().map(|d| if d.empty { "empty" } else { "ok" })
}

/// The `--json` summary, keys in the Python CLI's order.
fn summary(data: &StudentData, saved_to: Option<&Path>) -> serde_json::Value {
    serde_json::json!({
        "profile": data.profile.is_some(),
        "diploma": diploma_state(data),
        "counts": counts(data).into_iter().collect::<indexmap::IndexMap<_, _>>(),
        "errors": data.errors,
        "saved_to": saved_to.map(|p| p.display().to_string()),
    })
}

fn fetch_all(args: FetchAllArgs) -> ExitCode {
    let (Some(email), Some(password)) = (
        from_flag_or_env(args.email, "SCHOOLAPP_EMAIL"),
        from_flag_or_env(args.password, "SCHOOLAPP_PASSWORD"),
    ) else {
        eprintln!("Missing credentials: provide --email/--password or SCHOOLAPP_EMAIL/SCHOOLAPP_PASSWORD");
        return ExitCode::from(2);
    };

    let mut client = Client::new(UreqHttp::new(SCHOOLAPP_BASE, Duration::from_secs(args.timeout)), utc_now);
    if let Err(err) = client.login(&email, &password) {
        eprintln!("error: {err}");
        return ExitCode::from(1);
    }
    let data = client.fetch_all(!args.no_history, args.stats);

    let saved_to = if args.no_save {
        None
    } else {
        if let Err(err) = save_student_data(&data, "fetch_all", None, &utc_now()) {
            eprintln!("error: could not write the store in {}: {err}", state_dir().display());
            return ExitCode::from(1);
        }
        Some(state_dir())
    };

    if args.json {
        let text = serde_json::to_string_pretty(&summary(&data, saved_to.as_deref())).expect("summary serializes");
        println!("{text}");
        return ExitCode::SUCCESS;
    }

    println!("profile {}", if data.profile.is_some() { "ok" } else { "--" });
    println!("diploma {}", diploma_state(&data).unwrap_or("--"));
    for (name, count) in counts(&data) {
        println!("{name} {count}");
    }
    if let Some(dir) = saved_to {
        eprintln!("Saved to {}", dir.display());
    }
    for (name, err) in &data.errors {
        eprintln!("{name}: {err}");
    }
    ExitCode::SUCCESS
}

fn main() -> ExitCode {
    match Cli::parse().command {
        Command::FetchAll(args) => fetch_all(args),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn json_summary_keeps_python_key_order() {
        let mut data = StudentData::default();
        data.errors.insert("semester_results".into(), "boom".into());
        data.errors.insert("absences".into(), "boom".into());
        let text = serde_json::to_string(&summary(&data, None)).unwrap();
        let at = |key: &str| text.find(&format!("\"{key}\"")).unwrap_or_else(|| panic!("{key} missing in {text}"));
        assert!(at("profile") < at("diploma") && at("diploma") < at("counts"), "{text}");
        assert!(at("counts") < at("errors") && at("errors") < at("saved_to"), "{text}");
        assert!(at("element_grades") < at("module_grades") && at("courses") < at("stats"), "{text}");
        // errors stay in the order the fetch recorded them
        let first = text.find(r#""semester_results":"boom""#).unwrap();
        let second = text.find(r#""absences":"boom""#).unwrap();
        assert!(first < second, "{text}");
    }
}
