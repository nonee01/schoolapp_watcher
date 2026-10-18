//! The live transport: one `ureq` agent with a cookie store, like the
//! `requests.Session` the Python client used.

use std::time::Duration;

use crate::http::{Http, HttpError};

const USER_AGENT: &str = "schoolapp-cli/0.2";
const MAX_REDIRECTS: usize = 5;

pub struct UreqHttp {
    agent: ureq::Agent,
    base_url: String,
}

impl UreqHttp {
    pub fn new(base_url: &str, timeout: Duration) -> Self {
        // Redirects are followed by hand below, so a POST answered with a
        // redirect continues with a GET, as `requests` does.
        let agent = ureq::AgentBuilder::new()
            .timeout(timeout)
            .user_agent(USER_AGENT)
            .redirects(0)
            .build();
        Self { agent, base_url: base_url.trim_end_matches('/').to_string() }
    }

    fn absolute(&self, location: &str) -> String {
        if location.starts_with("http://") || location.starts_with("https://") {
            location.to_string()
        } else if location.starts_with('/') {
            format!("{}{location}", self.origin())
        } else {
            format!("{}/{location}", self.base_url)
        }
    }

    /// `scheme://host[:port]` of the base URL.
    fn origin(&self) -> &str {
        let after_scheme = self.base_url.find("://").map_or(0, |i| i + 3);
        match self.base_url[after_scheme..].find('/') {
            Some(i) => &self.base_url[..after_scheme + i],
            None => &self.base_url,
        }
    }

    /// Follow 3xx answers with GETs, then read the final body.
    fn finish(&self, mut result: Result<ureq::Response, ureq::Error>) -> Result<String, HttpError> {
        for _ in 0..=MAX_REDIRECTS {
            let response = match result {
                Ok(response) => response,
                Err(ureq::Error::Status(code, _)) => return Err(HttpError::Status(code)),
                Err(ureq::Error::Transport(t)) => return Err(HttpError::Transport(t.to_string())),
            };
            let redirect = matches!(response.status(), 301 | 302 | 303 | 307 | 308);
            match response.header("Location").filter(|_| redirect) {
                Some(location) => {
                    let url = self.absolute(location);
                    result = self.agent.get(&url).call();
                }
                None => {
                    return response.into_string().map_err(|e| HttpError::Transport(e.to_string()));
                }
            }
        }
        Err(HttpError::Transport(format!("more than {MAX_REDIRECTS} redirects")))
    }
}

impl Http for UreqHttp {
    fn get(&mut self, path: &str, query: &[(&str, &str)]) -> Result<String, HttpError> {
        let mut request = self.agent.get(&format!("{}{path}", self.base_url));
        for (key, value) in query {
            request = request.query(key, value);
        }
        self.finish(request.call())
    }

    fn post_form(&mut self, path: &str, form: &[(&str, &str)]) -> Result<String, HttpError> {
        let request = self.agent.post(&format!("{}{path}", self.base_url));
        self.finish(request.send_form(form))
    }
}
