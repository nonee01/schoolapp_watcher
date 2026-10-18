//! Authenticated portal session (`schoolapp/client.py`): logs in with the CSRF
//! form, logs in again once when a page comes back as the login form, and
//! fetches every per-student resource.

use std::sync::LazyLock;

use anyhow::{Result, anyhow, bail};
use indexmap::IndexMap;
use scraper::{Html, Selector};

use crate::extract::{
    build_documents, parse_absence_summary, parse_absences, parse_courses, parse_diploma, parse_element_grades,
    parse_mark_statistics, parse_module_grades, parse_profile, parse_sanctions, parse_semester_results,
    parse_year_results,
};
use crate::http::Http;
use crate::models::{ElementGrade, MarkStatistics, Raw, StudentData};

pub const SCHOOLAPP_BASE: &str = "https://schoolapp.ensam-umi.ac.ma";
pub const LOGIN_PATH: &str = "/login";
pub const INDEX_PATH: &str = "/index";
pub const ELEMENTS_PATH: &str = "/student/noteselem-encours";
pub const ELEMENTS_HISTORY_PATH: &str = "/student/noteselem";
pub const MODULES_PATH: &str = "/student/notesmod-encours";
pub const MODULES_HISTORY_PATH: &str = "/student/notesmod";
pub const SEMESTERS_PATH: &str = "/student/notessem";
pub const YEARS_PATH: &str = "/student/notesannee";
pub const DIPLOMA_PATH: &str = "/student/notesdiplome";
pub const ABSENCES_PATH: &str = "/student/absence/bilan";
pub const SANCTIONS_PATH: &str = "/student/absence/sanctions";
pub const COURSES_PATH: &str = "/student/inscriptioncours";
pub const STATS_PATH: &str = "/notes-stat/elemevalsat";

fn selector(css: &str) -> Selector {
    Selector::parse(css).expect("static selector")
}

static CSRF: LazyLock<Selector> = LazyLock::new(|| selector(r#"input[name="_csrf"]"#));
static LOGIN_FORM: LazyLock<Selector> = LazyLock::new(|| selector(r#"form[action="/login"]"#));
static PASSWORD: LazyLock<Selector> = LazyLock::new(|| selector(r#"input[name="password"]"#));

/// The `_csrf` hidden input's value, if the page has a non-empty one.
pub fn extract_csrf(html: &str) -> Option<String> {
    let doc = Html::parse_document(html);
    let value = doc.select(&CSRF).next()?.value().attr("value")?;
    (!value.is_empty()).then(|| value.to_string())
}

/// The portal's login form: a form posting to /login with a password field.
pub fn looks_like_login_page(html: &str) -> bool {
    let doc = Html::parse_document(html);
    doc.select(&LOGIN_FORM).next().is_some() && doc.select(&PASSWORD).next().is_some()
}

/// The result of one isolated resource fetch: a failure is recorded under `name`
/// in `errors` and replaced by `default`, so it never stops the others.
fn grab<T>(errors: &mut Raw, name: &str, result: Result<T>, default: T) -> T {
    result.unwrap_or_else(|err| {
        errors.insert(name.to_string(), err.to_string());
        default
    })
}

pub struct Client<H: Http> {
    http: H,
    credentials: Option<(String, String)>,
    /// Raw HTML of the last successful answer per path, for consumers that need
    /// the exact bytes `fetch_all` parsed (the watcher's legacy snapshot).
    pub last_pages: IndexMap<String, String>,
    now: fn() -> String,
}

impl<H: Http> Client<H> {
    /// `now` stamps `StudentData.fetched_at` (UTC, ISO 8601 to the second).
    pub fn new(http: H, now: fn() -> String) -> Self {
        Self { http, credentials: None, last_pages: IndexMap::new(), now }
    }

    pub fn http_mut(&mut self) -> &mut H {
        &mut self.http
    }

    /// Keep credentials without logging in now; login happens when a request
    /// lands on the login form (a still-valid session costs nothing).
    pub fn set_credentials(&mut self, email: &str, password: &str) {
        self.credentials = Some((email.to_string(), password.to_string()));
    }

    pub fn login(&mut self, email: &str, password: &str) -> Result<()> {
        self.set_credentials(email, password);
        self.do_login()
    }

    fn do_login(&mut self) -> Result<()> {
        let (email, password) = self.credentials.clone().ok_or_else(|| anyhow!("no credentials"))?;
        let page = self.http.get(LOGIN_PATH, &[])?;
        let csrf = extract_csrf(&page).ok_or_else(|| anyhow!("Login page changed: CSRF token missing"))?;
        let answer = self
            .http
            .post_form(LOGIN_PATH, &[("email", &email), ("password", &password), ("_csrf", &csrf)])?;
        if looks_like_login_page(&answer) {
            bail!("Login failed: verify email/password");
        }
        Ok(())
    }

    /// Raw HTML of a portal page, logging in again if the session expired.
    pub fn get_page(&mut self, path: &str) -> Result<String> {
        self.get(path, &[])
    }

    fn get(&mut self, path: &str, query: &[(&str, &str)]) -> Result<String> {
        self.request(path, query, false)
    }

    fn request(&mut self, path: &str, query: &[(&str, &str)], retried: bool) -> Result<String> {
        let text = self.http.get(path, query)?;
        if looks_like_login_page(&text) {
            if retried || self.credentials.is_none() {
                bail!("Session expired and re-authentication failed");
            }
            self.do_login()?;
            return self.request(path, query, true);
        }
        self.last_pages.insert(path.to_string(), text.clone());
        Ok(text)
    }

    /// Every per-student resource; a failing resource lands in `errors`.
    pub fn fetch_all(&mut self, include_history: bool, include_stats: bool) -> StudentData {
        let mut data = StudentData { fetched_at: (self.now)(), ..Default::default() };
        let e = &mut data.errors;

        data.profile = grab(e, "profile", self.get_page(INDEX_PATH).map(|h| Some(parse_profile(&h))), None);

        let current = grab(e, "element_grades", self.get_page(ELEMENTS_PATH).map(|h| parse_element_grades(&h)), vec![]);
        let history = if include_history {
            let r = self.get_page(ELEMENTS_HISTORY_PATH).map(|h| parse_element_grades(&h));
            grab(e, "element_grades_history", r, vec![])
        } else {
            vec![]
        };
        data.element_grades = merge_by(&current, history, |g| (g.code.clone(), g.au.clone()));

        let mods = grab(e, "module_grades", self.get_page(MODULES_PATH).map(|h| parse_module_grades(&h)), vec![]);
        let mods_history = if include_history {
            let r = self.get_page(MODULES_HISTORY_PATH).map(|h| parse_module_grades(&h));
            grab(e, "module_grades_history", r, vec![])
        } else {
            vec![]
        };
        data.module_grades = merge_by(&mods, mods_history, |m| (m.code.clone(), m.au.clone()));

        let r = self.get_page(SEMESTERS_PATH).map(|h| parse_semester_results(&h));
        data.semester_results = grab(e, "semester_results", r, vec![]);
        data.year_results = grab(e, "year_results", self.get_page(YEARS_PATH).map(|h| parse_year_results(&h)), vec![]);
        data.diploma = grab(e, "diploma", self.get_page(DIPLOMA_PATH).map(|h| Some(parse_diploma(&h))), None);

        if let Some(html) = grab(e, "absences", self.get_page(ABSENCES_PATH).map(Some), None) {
            data.absences = parse_absences(&html);
            data.absence_summary = parse_absence_summary(&html);
        }

        data.sanctions = grab(e, "sanctions", self.get_page(SANCTIONS_PATH).map(|h| parse_sanctions(&h)), vec![]);
        data.courses = grab(e, "courses", self.get_page(COURSES_PATH).map(|h| parse_courses(&h)), vec![]);
        data.documents = build_documents(&data.year_results, &data.semester_results);

        if include_stats {
            let r = self.all_stats(&current);
            data.stats = grab(&mut data.errors, "stats", r, vec![]);
        }
        data
    }

    /// One popup per (element moyenne, rattrapage note when taken).
    fn all_stats(&mut self, grades: &[ElementGrade]) -> Result<Vec<MarkStatistics>> {
        let mut out = Vec::new();
        for g in grades {
            for (eval_kind, note) in [("MoyElem", &g.moy), ("NoteRAT", &g.rat)] {
                if note.is_empty() || note == "--" {
                    continue;
                }
                let code = g.code.to_uppercase();
                let query = [("eval", eval_kind), ("codeelem", code.as_str()), ("au", g.au.as_str()), ("note", note.as_str())];
                let html = self.get(STATS_PATH, &query)?;
                out.extend(parse_mark_statistics(&html, &code, eval_kind, &g.au, note));
            }
        }
        Ok(out)
    }
}

/// `current + [x for x in history if key(x) not in {key(c) for c in current}]`.
fn merge_by<T: Clone, K: Eq + std::hash::Hash>(current: &[T], history: Vec<T>, key: impl Fn(&T) -> K) -> Vec<T> {
    let seen: std::collections::HashSet<K> = current.iter().map(&key).collect();
    current.iter().cloned().chain(history.into_iter().filter(|x| !seen.contains(&key(x)))).collect()
}
