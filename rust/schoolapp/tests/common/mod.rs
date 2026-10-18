#![allow(dead_code)]

pub mod fake;

use std::path::{Path, PathBuf};

/// The fixed clock the golden files were generated with.
pub const NOW: &str = "2026-01-01T00:00:00+00:00";

fn manifest_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
}

fn read(path: &Path) -> String {
    std::fs::read_to_string(path).unwrap_or_else(|e| panic!("{}: {e}", path.display()))
}

/// A sanitized portal page from the Python test suite (`tests/fixtures/<name>.html`).
pub fn fixture(name: &str) -> String {
    read(&manifest_dir().join("../../tests/fixtures").join(format!("{name}.html")))
}

/// A file written by `rust/tools/make_golden.py`.
pub fn golden(path: &str) -> String {
    read(&manifest_dir().join("tests/golden").join(path))
}
