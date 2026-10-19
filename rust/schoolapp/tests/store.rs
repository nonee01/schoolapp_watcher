mod common;

use common::fake::FakeHttp;
use common::{NOW, golden};
use schoolapp::client::Client;
use schoolapp::models::StudentProfile;
use schoolapp::store::{RESOURCE_FILES, load_resource, save_resource, save_student_data};

fn now() -> String {
    NOW.to_string()
}

fn assert_tree(case: &str, include_history: bool, include_stats: bool, fail: &[&str]) {
    let tmp = tempfile::tempdir().unwrap();
    let fake = FakeHttp { fail_paths: fail.iter().map(|s| s.to_string()).collect(), ..Default::default() };
    let mut c = Client::new(fake, now);
    c.login("e", "p").unwrap();
    save_student_data(&c.fetch_all(include_history, include_stats), "fetch_all", Some(tmp.path()), NOW).unwrap();
    for name in std::iter::once("student/all").chain(RESOURCE_FILES.iter().map(|(_, n)| *n)) {
        let got = std::fs::read_to_string(tmp.path().join(format!("{name}.json"))).unwrap();
        pretty_assertions::assert_eq!(got, golden(&format!("{case}/{name}.json")), "{case}/{name}");
    }
}

#[test]
fn default_tree_matches_python() {
    assert_tree("store_default", true, false, &[]);
}

#[test]
fn stats_without_history_matches_python() {
    assert_tree("store_stats_nohistory", false, true, &[]);
}

#[test]
fn failed_page_tree_matches_python() {
    assert_tree("store_fail_semesters", true, false, &["/student/notessem"]);
}

#[test]
fn a_loaded_resource_reserializes_byte_for_byte() {
    let tmp = tempfile::tempdir().unwrap();
    let profile = StudentProfile { nom: "Doe".into(), ..Default::default() };
    let path = save_resource("student/profile", &profile, "x", Some(tmp.path()), NOW).unwrap();
    let loaded = load_resource("student/profile", Some(tmp.path())).unwrap();
    assert_eq!(schoolapp::json::to_store_json(&loaded), std::fs::read_to_string(path).unwrap());
}

#[test]
fn load_resource_rejects_missing_and_corrupt_files() {
    let tmp = tempfile::tempdir().unwrap();
    assert!(load_resource("student/profile", Some(tmp.path())).is_none());
    std::fs::create_dir_all(tmp.path().join("student")).unwrap();
    std::fs::write(tmp.path().join("student/profile.json"), "{oops").unwrap();
    assert!(load_resource("student/profile", Some(tmp.path())).is_none());
    save_resource("student/profile", &StudentProfile::default(), "x", Some(tmp.path()), NOW).unwrap();
    assert_eq!(load_resource("student/profile", Some(tmp.path())).unwrap()["source"], "x");
    assert!(!tmp.path().join("student/profile.json.tmp").exists());
}
