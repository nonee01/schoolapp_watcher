//! The resource store (`schoolapp/store.py`): one envelope
//! `{"fetched_at", "source", "data"}` per resource under
//! `$XDG_STATE_HOME/schoolapp/`, written atomically. The legacy snapshot and
//! changes.jsonl are not managed here.

use std::path::{Path, PathBuf};
use std::{env, fs, io};

use serde::Serialize;

use crate::json::to_store_json;
use crate::models::StudentData;

/// `StudentData` field -> resource name, shared with the CLI, watcher and API.
pub const RESOURCE_FILES: [(&str, &str); 12] = [
    ("profile", "student/profile"),
    ("element_grades", "student/elements"),
    ("module_grades", "student/modules"),
    ("semester_results", "student/semesters"),
    ("year_results", "student/years"),
    ("diploma", "student/diploma"),
    ("absences", "student/absences"),
    ("absence_summary", "student/absence_summary"),
    ("sanctions", "student/sanctions"),
    ("courses", "student/courses"),
    ("stats", "student/stats"),
    ("documents", "student/documents"),
];

/// `$XDG_STATE_HOME/schoolapp`, or `~/.local/state/schoolapp` when it is unset or blank.
pub fn state_dir() -> PathBuf {
    let base = env::var("XDG_STATE_HOME")
        .ok()
        .map(|v| v.trim().to_string())
        .filter(|v| !v.is_empty())
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from(env::var("HOME").unwrap_or_default()).join(".local/state"));
    base.join("schoolapp")
}

fn resource_path(name: &str, dir: Option<&Path>) -> PathBuf {
    let base = dir.map(Path::to_path_buf).unwrap_or_else(state_dir);
    base.join(format!("{name}.json"))
}

#[derive(Serialize)]
struct Envelope<'a, T: Serialize + ?Sized> {
    fetched_at: &'a str,
    source: &'a str,
    data: &'a T,
}

/// Atomic envelope write; `name` may be nested ("student/profile").
pub fn save_resource<T: Serialize + ?Sized>(name: &str, data: &T, source: &str, dir: Option<&Path>, now: &str) -> io::Result<PathBuf> {
    let path = resource_path(name, dir);
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    let file_name = path.file_name().map(|n| n.to_string_lossy().into_owned()).unwrap_or_default();
    let tmp = path.with_file_name(format!("{file_name}.tmp"));
    fs::write(&tmp, to_store_json(&Envelope { fetched_at: now, source, data }))?;
    fs::rename(&tmp, &path)?;
    Ok(path)
}

/// The envelope, or `None` when the file is missing, not JSON, or has no `data`.
pub fn load_resource(name: &str, dir: Option<&Path>) -> Option<serde_json::Value> {
    let text = fs::read_to_string(resource_path(name, dir)).ok()?;
    let envelope: serde_json::Value = serde_json::from_str(&text).ok()?;
    envelope.get("data").is_some().then_some(envelope)
}

/// `student/all` plus one envelope per resource, in `RESOURCE_FILES` order.
pub fn save_student_data(data: &StudentData, source: &str, dir: Option<&Path>, now: &str) -> io::Result<()> {
    save_resource("student/all", data, source, dir, now)?;
    save_resource("student/profile", &data.profile, source, dir, now)?;
    save_resource("student/elements", &data.element_grades, source, dir, now)?;
    save_resource("student/modules", &data.module_grades, source, dir, now)?;
    save_resource("student/semesters", &data.semester_results, source, dir, now)?;
    save_resource("student/years", &data.year_results, source, dir, now)?;
    save_resource("student/diploma", &data.diploma, source, dir, now)?;
    save_resource("student/absences", &data.absences, source, dir, now)?;
    save_resource("student/absence_summary", &data.absence_summary, source, dir, now)?;
    save_resource("student/sanctions", &data.sanctions, source, dir, now)?;
    save_resource("student/courses", &data.courses, source, dir, now)?;
    save_resource("student/stats", &data.stats, source, dir, now)?;
    save_resource("student/documents", &data.documents, source, dir, now)?;
    Ok(())
}
