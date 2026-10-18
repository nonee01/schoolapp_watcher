//! `FakeHttp`: the Rust twin of `tests/test_fetch_all.py::FakeSession`.

use schoolapp::http::{Http, HttpError};

use super::fixture;

pub const LOGIN_FORM: &str =
    r#"<html><form action="/login"><input name="_csrf" value="tok"/><input name="password"/></form></html>"#;

const PAGES: &[(&str, &str)] = &[
    ("/index", "profile"),
    ("/student/noteselem-encours", "elements_encours"),
    ("/student/noteselem", "elements_history"),
    ("/student/notesmod-encours", "modules_encours"),
    ("/student/notesmod", "modules_history"),
    ("/student/notessem", "semesters"),
    ("/student/notesannee", "years"),
    ("/student/notesdiplome", "diploma"),
    ("/student/absence/bilan", "absences"),
    ("/student/absence/sanctions", "sanctions"),
    ("/student/inscriptioncours", "courses"),
    ("/notes-stat/elemevalsat", "stats"),
];

/// Serves the sanitized fixtures and requires a login POST first, like the portal.
#[derive(Default)]
pub struct FakeHttp {
    /// Paths answered with a transport error `boom <path>`.
    pub fail_paths: Vec<String>,
    /// Serve the login form once after this many requests (an expired session).
    pub expire_after: Option<usize>,
    /// Keep serving the login form after the login POST (a wrong password).
    pub reject_login: bool,
    /// `"GET <path>"`, `"GET <path>?k=v&k=v"` or `"POST <path>"`, one per request.
    pub log: Vec<String>,
    // Public only so tests can build a FakeHttp with `..Default::default()`.
    pub logged_in: bool,
    pub expired: bool,
}

impl FakeHttp {
    fn page(&self, path: &str) -> String {
        if path == "/login" || !self.logged_in {
            return LOGIN_FORM.to_string();
        }
        match PAGES.iter().find(|(p, _)| *p == path) {
            Some((_, name)) => fixture(name),
            None => "<html><body>rien</body></html>".to_string(),
        }
    }
}

impl Http for FakeHttp {
    fn get(&mut self, path: &str, query: &[(&str, &str)]) -> Result<String, HttpError> {
        if query.is_empty() {
            self.log.push(format!("GET {path}"));
        } else {
            let q: Vec<String> = query.iter().map(|(k, v)| format!("{k}={v}")).collect();
            self.log.push(format!("GET {path}?{}", q.join("&")));
        }
        if self.fail_paths.iter().any(|p| p == path) {
            return Err(HttpError::Transport(format!("boom {path}")));
        }
        if let Some(n) = self.expire_after {
            if !self.expired && self.log.len() > n {
                self.expired = true;
                self.logged_in = false;
            }
        }
        Ok(self.page(path))
    }

    fn post_form(&mut self, path: &str, _form: &[(&str, &str)]) -> Result<String, HttpError> {
        self.log.push(format!("POST {path}"));
        if path == "/login" {
            if self.reject_login {
                return Ok(LOGIN_FORM.to_string());
            }
            self.logged_in = true;
            return Ok("<html><body>bienvenue</body></html>".to_string());
        }
        Ok(self.page(path))
    }
}
