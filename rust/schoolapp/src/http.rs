//! The HTTP surface the portal client needs, so tests can swap in a fake.

use std::fmt;

/// GET and form-POST against the portal; paths are relative to its base URL.
pub trait Http {
    fn get(&mut self, path: &str, query: &[(&str, &str)]) -> Result<String, HttpError>;
    fn post_form(&mut self, path: &str, form: &[(&str, &str)]) -> Result<String, HttpError>;
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum HttpError {
    /// The portal answered with an HTTP status of 400 or more.
    Status(u16),
    /// No usable answer: DNS, connection, timeout, TLS…
    Transport(String),
}

impl fmt::Display for HttpError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            HttpError::Status(code) => write!(f, "status {code}"),
            HttpError::Transport(message) => f.write_str(message),
        }
    }
}

impl std::error::Error for HttpError {}
