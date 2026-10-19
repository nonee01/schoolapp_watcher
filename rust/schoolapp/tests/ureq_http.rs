mod common;

use std::io::{BufRead, BufReader, Read, Write};
use std::net::TcpListener;
use std::time::Duration;

use common::NOW;
use schoolapp::client::Client;
use schoolapp::http::Http;
use schoolapp::ureq_http::UreqHttp;

const LOGIN_FORM: &str =
    r#"<html><form action="/login"><input name="_csrf" value="tok"/><input name="password"/></form></html>"#;

fn now() -> String {
    NOW.to_string()
}

/// A one-thread HTTP/1.1 server answering each request with `respond(request line)`.
fn serve(respond: fn(&str) -> String) -> String {
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let base = format!("http://{}", listener.local_addr().unwrap());
    std::thread::spawn(move || {
        for stream in listener.incoming() {
            let mut stream = stream.unwrap();
            let mut reader = BufReader::new(stream.try_clone().unwrap());
            let mut request_line = String::new();
            reader.read_line(&mut request_line).unwrap();
            let mut content_length = 0;
            loop {
                let mut line = String::new();
                reader.read_line(&mut line).unwrap();
                if line == "\r\n" || line.is_empty() {
                    break;
                }
                if let Some(v) = line.to_ascii_lowercase().strip_prefix("content-length:") {
                    content_length = v.trim().parse().unwrap();
                }
            }
            let mut body = vec![0; content_length];
            reader.read_exact(&mut body).unwrap();
            stream.write_all(respond(request_line.trim_end()).as_bytes()).unwrap();
        }
    });
    base
}

fn html(status: &str, body: &str) -> String {
    format!("HTTP/1.1 {status}\r\nContent-Type: text/html\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}", body.len())
}

#[test]
fn bad_password_redirect_is_reported_as_failed_login() {
    let base = serve(|request| match request {
        "POST /login HTTP/1.1" => "HTTP/1.1 302 Found\r\nLocation: /login?error\r\nContent-Length: 0\r\nConnection: close\r\n\r\n".into(),
        _ => html("200 OK", LOGIN_FORM),
    });
    let mut c = Client::new(UreqHttp::new(&base, Duration::from_secs(5)), now);
    assert_eq!(c.login("e", "bad").unwrap_err().to_string(), "Login failed: verify email/password");
}

#[test]
fn http_errors_become_status_errors() {
    let base = serve(|_| "HTTP/1.1 503 Service Unavailable\r\nContent-Length: 0\r\nConnection: close\r\n\r\n".into());
    let mut h = UreqHttp::new(&base, Duration::from_secs(5));
    assert_eq!(h.get("/student/notessem", &[]).unwrap_err().to_string(), "status 503");
}

/// Like `requests`, the timeout bounds each wait, not the whole request: a page
/// whose headers and body each take longer than half the timeout still loads.
#[test]
fn timeout_applies_per_read_not_to_the_whole_request() {
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let base = format!("http://{}", listener.local_addr().unwrap());
    std::thread::spawn(move || {
        let (mut stream, _) = listener.accept().unwrap();
        let mut reader = BufReader::new(stream.try_clone().unwrap());
        let mut line = String::new();
        while reader.read_line(&mut line).unwrap() > 2 {
            line.clear();
        }
        let body = "<html>slow but fine</html>";
        let (first, rest) = body.split_at(10);
        std::thread::sleep(Duration::from_millis(1200));
        write!(stream, "HTTP/1.1 200 OK\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{first}", body.len()).unwrap();
        stream.flush().unwrap();
        std::thread::sleep(Duration::from_millis(1200));
        stream.write_all(rest.as_bytes()).unwrap();
    });
    let mut h = UreqHttp::new(&base, Duration::from_secs(2));
    assert_eq!(h.get("/slow", &[]).unwrap(), "<html>slow but fine</html>");
}

#[test]
fn query_values_are_url_encoded() {
    let base = serve(|request| html("200 OK", request));
    let mut h = UreqHttp::new(&base, Duration::from_secs(5));
    let echoed = h.get("/notes-stat/elemevalsat", &[("au", "2025/2026"), ("note", "12,5 é")]).unwrap();
    assert_eq!(echoed, "GET /notes-stat/elemevalsat?au=2025%2F2026&note=12%2C5+%C3%A9 HTTP/1.1");
}
