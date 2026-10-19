mod common;

use common::NOW;
use common::fake::FakeHttp;
use schoolapp::client::Client;

fn now() -> String {
    NOW.to_string()
}

#[test]
fn login_then_fetch_all_reads_every_resource() {
    let mut c = Client::new(FakeHttp::default(), now);
    c.login("e", "p").unwrap();
    let data = c.fetch_all(true, false);
    assert!(data.errors.is_empty(), "{:?}", data.errors);
    assert_eq!(data.fetched_at, NOW);
    assert_eq!(data.profile.as_ref().map(|p| p.nom.as_str()), Some("Doe"));
    // the counts tests/test_fetch_all.py asserts on the same fixtures
    assert_eq!(data.element_grades.len(), 46);
    assert_eq!(data.module_grades.len(), 28);
    assert_eq!(data.semester_results.len(), 3);
    assert_eq!(data.absences.len(), 6);
    assert_eq!(data.absence_summary.len(), 23);
    assert_eq!(data.documents.len(), 5);
    assert!(data.stats.is_empty());
}

#[test]
fn a_failing_page_is_recorded_and_the_rest_still_fetched() {
    let fake = FakeHttp { fail_paths: vec!["/student/notessem".into()], ..Default::default() };
    let mut c = Client::new(fake, now);
    c.login("e", "p").unwrap();
    let data = c.fetch_all(true, false);
    assert_eq!(data.errors.get("semester_results").map(String::as_str), Some("boom /student/notessem"));
    assert_eq!(data.errors.len(), 1);
    assert!(data.semester_results.is_empty() && !data.year_results.is_empty());
}

#[test]
fn session_expiry_triggers_one_relogin() {
    let mut c = Client::new(FakeHttp { expire_after: Some(3), ..Default::default() }, now);
    c.login("e", "p").unwrap();
    let data = c.fetch_all(true, false);
    assert!(data.errors.is_empty(), "{:?}", data.errors);
    assert_eq!(c.http_mut().log.iter().filter(|p| *p == "POST /login").count(), 2);
}

#[test]
fn a_page_still_on_the_login_form_after_relogin_fails() {
    let fake = FakeHttp { login_form_paths: vec!["/student/notessem".into()], ..Default::default() };
    let mut c = Client::new(fake, now);
    c.login("e", "p").unwrap();
    let err = c.get_page("/student/notessem").unwrap_err();
    assert_eq!(err.to_string(), "Session expired and re-authentication failed");
    assert_eq!(c.http_mut().log.iter().filter(|p| *p == "POST /login").count(), 2);
}

#[test]
fn wrong_password_and_missing_credentials() {
    let mut c = Client::new(FakeHttp { reject_login: true, ..Default::default() }, now);
    assert_eq!(c.login("e", "bad").unwrap_err().to_string(), "Login failed: verify email/password");
    let mut anon = Client::new(FakeHttp::default(), now);
    assert_eq!(anon.get_page("/index").unwrap_err().to_string(), "Session expired and re-authentication failed");
}

#[test]
fn last_pages_keeps_each_successful_page() {
    let mut c = Client::new(FakeHttp::default(), now);
    c.login("e", "p").unwrap();
    let html = c.get_page("/student/notesmod-encours").unwrap();
    assert_eq!(c.last_pages.get("/student/notesmod-encours"), Some(&html));
}

#[test]
fn stats_follow_each_graded_element() {
    let mut c = Client::new(FakeHttp::default(), now);
    c.login("e", "p").unwrap();
    let data = c.fetch_all(false, true);
    assert!(!data.stats.is_empty());
    assert!(
        c.http_mut().log.iter().any(|p| p.starts_with("GET /notes-stat/elemevalsat?eval=MoyElem&codeelem=")),
        "{:?}",
        c.http_mut().log
    );
}
