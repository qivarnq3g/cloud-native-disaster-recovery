use std::collections::{HashMap, VecDeque};
use std::net::{IpAddr, SocketAddr};
use std::sync::Mutex;
use std::time::{Duration, Instant};

use axum::http::{HeaderMap, header};
use ipnet::IpNet;
use subtle::ConstantTimeEq;

use crate::error::ApiError;

pub struct SecretCodeChecker {
    code: Vec<u8>,
    failures: Mutex<HashMap<IpAddr, VecDeque<Instant>>>,
    max_failures: usize,
    window: Duration,
}

impl SecretCodeChecker {
    pub fn new(code: &str) -> Self {
        Self::with_limit(code, 10, Duration::from_secs(600))
    }

    pub fn with_limit(code: &str, max_failures: usize, window: Duration) -> Self {
        Self {
            code: code.as_bytes().to_vec(),
            failures: Mutex::new(HashMap::new()),
            max_failures,
            window,
        }
    }

    pub fn check(&self, ip: IpAddr, sent: Option<&str>, now: Instant) -> Result<(), ApiError> {
        let mut failures = self.failures.lock().expect("failure counter lock");
        if failures.len() > 10_000 {
            failures.retain(|_, attempts| {
                prune(attempts, now, self.window);
                !attempts.is_empty()
            });
        }
        let attempts = failures.entry(ip).or_default();
        prune(attempts, now, self.window);
        if attempts.len() >= self.max_failures {
            let remaining = self.window.saturating_sub(now.duration_since(attempts[0]));
            return Err(ApiError::TooManyAttempts(remaining.as_secs().max(1)));
        }
        let correct: bool = sent
            .map(|m| bool::from(m.as_bytes().ct_eq(&self.code)))
            .unwrap_or(false);
        if correct {
            let none_left = attempts.is_empty();
            if none_left {
                failures.remove(&ip);
            }
            Ok(())
        } else {
            attempts.push_back(now);
            Err(ApiError::InvalidCode)
        }
    }
}

fn prune(attempts: &mut VecDeque<Instant>, now: Instant, window: Duration) {
    while attempts
        .front()
        .is_some_and(|t| now.duration_since(*t) >= window)
    {
        attempts.pop_front();
    }
}

pub fn client_ip(peer: SocketAddr, headers: &HeaderMap, trusted: &[IpNet]) -> IpAddr {
    let ip = peer.ip();
    if trusted.iter().any(|n| n.contains(&ip)) {
        let forwarded = headers
            .get("x-forwarded-for")
            .and_then(|v| v.to_str().ok())
            .and_then(|s| s.split(',').next_back())
            .and_then(|s| s.trim().parse::<IpAddr>().ok());
        if let Some(x) = forwarded {
            return x;
        }
    }
    ip
}

pub fn code_from_headers(headers: &HeaderMap) -> Option<&str> {
    headers
        .get(header::AUTHORIZATION)?
        .to_str()
        .ok()?
        .strip_prefix("Bearer ")
}

#[cfg(test)]
mod tests {
    use super::*;
    use axum::http::HeaderValue;

    const CODE: &str = "0123456789abcdef";

    fn ip(s: &str) -> IpAddr {
        s.parse().unwrap()
    }

    #[test]
    fn correct_code_passes_wrong_or_missing_is_401() {
        let k = SecretCodeChecker::new(CODE);
        let t = Instant::now();
        assert_eq!(k.check(ip("1.2.3.4"), Some(CODE), t), Ok(()));
        assert_eq!(
            k.check(ip("1.2.3.4"), Some("wrong"), t),
            Err(ApiError::InvalidCode)
        );
        assert_eq!(
            k.check(ip("1.2.3.4"), Some("0123456789abcdeX"), t),
            Err(ApiError::InvalidCode)
        );
        assert_eq!(k.check(ip("1.2.3.4"), None, t), Err(ApiError::InvalidCode));
    }

    #[test]
    fn ten_failures_block_even_correct_code_until_window_ends() {
        let k = SecretCodeChecker::with_limit(CODE, 10, Duration::from_secs(600));
        let t0 = Instant::now();
        for i in 0..10 {
            assert_eq!(
                k.check(ip("1.2.3.4"), Some("wrong"), t0 + Duration::from_secs(i)),
                Err(ApiError::InvalidCode)
            );
        }
        assert_eq!(
            k.check(ip("1.2.3.4"), Some(CODE), t0 + Duration::from_secs(100)),
            Err(ApiError::TooManyAttempts(500))
        );
        assert_eq!(
            k.check(ip("5.6.7.8"), Some(CODE), t0 + Duration::from_secs(100)),
            Ok(())
        );
        assert_eq!(
            k.check(ip("1.2.3.4"), Some(CODE), t0 + Duration::from_secs(611)),
            Ok(())
        );
    }

    #[test]
    fn trusts_x_forwarded_for_only_from_proxy() {
        let trusted: Vec<IpNet> = vec!["10.42.0.0/16".parse().unwrap()];
        let mut h = HeaderMap::new();
        h.insert(
            "x-forwarded-for",
            HeaderValue::from_static("9.9.9.9, 203.0.113.7"),
        );
        assert_eq!(
            client_ip("10.42.0.5:1234".parse().unwrap(), &h, &trusted),
            ip("203.0.113.7")
        );
        assert_eq!(
            client_ip("198.51.100.1:1234".parse().unwrap(), &h, &trusted),
            ip("198.51.100.1")
        );
        assert_eq!(
            client_ip(
                "10.42.0.5:1234".parse().unwrap(),
                &HeaderMap::new(),
                &trusted
            ),
            ip("10.42.0.5")
        );
    }

    #[test]
    fn reads_code_from_bearer() {
        let mut h = HeaderMap::new();
        h.insert(
            header::AUTHORIZATION,
            HeaderValue::from_static("Bearer abc"),
        );
        assert_eq!(code_from_headers(&h), Some("abc"));
        h.insert(header::AUTHORIZATION, HeaderValue::from_static("Basic abc"));
        assert_eq!(code_from_headers(&h), None);
    }
}
