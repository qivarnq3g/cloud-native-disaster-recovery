use anyhow::{Context, bail};
use ipnet::IpNet;

pub const APP_VERSION: &str = match option_env!("APP_VERSION") {
    Some(v) => v,
    None => "dev",
};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum StoreKind {
    Azure,
    S3,
}

#[derive(Clone, Debug)]
pub struct Config {
    pub database_url: String,
    pub store_kind: StoreKind,
    pub container: String,
    pub read_only: bool,
    pub secret_code: String,
    pub cluster: String,
    pub region: String,
    pub cors_origins: Vec<String>,
    pub trusted_proxies: Vec<IpNet>,
    pub port: u16,
}

impl Config {
    pub fn from_env() -> anyhow::Result<Self> {
        Self::from_lookup(|k| std::env::var(k).ok())
    }

    pub fn from_lookup(lookup: impl Fn(&str) -> Option<String>) -> anyhow::Result<Self> {
        let required = |k: &str| {
            lookup(k)
                .filter(|v| !v.trim().is_empty())
                .with_context(|| format!("thiếu biến môi trường {k}"))
        };
        let list = |k: &str, default: &str| -> Vec<String> {
            lookup(k)
                .unwrap_or_else(|| default.to_string())
                .split(',')
                .map(str::trim)
                .filter(|s| !s.is_empty())
                .map(String::from)
                .collect()
        };
        let store_kind = match required("IMAGE_STORE")?.as_str() {
            "azure" => StoreKind::Azure,
            "s3" => StoreKind::S3,
            other => bail!("IMAGE_STORE phải là azure hoặc s3, nhận được {other}"),
        };
        let cluster = required("CLUSTER")?;
        if cluster != "primary" && cluster != "standby" {
            bail!("CLUSTER phải là primary hoặc standby, nhận được {cluster}");
        }
        let secret_code = required("SECRET_CODE")?;
        if secret_code.chars().count() < 16 {
            bail!("SECRET_CODE phải dài ít nhất 16 ký tự");
        }
        let read_only = match lookup("IMAGE_STORE_READ_ONLY").as_deref() {
            None | Some("") | Some("false") => false,
            Some("true") => true,
            Some(other) => {
                bail!("IMAGE_STORE_READ_ONLY phải là true hoặc false, nhận được {other}")
            }
        };
        let trusted_proxies = list("TRUSTED_PROXIES", "")
            .iter()
            .map(|s| {
                s.parse::<IpNet>()
                    .with_context(|| format!("TRUSTED_PROXIES sai: {s}"))
            })
            .collect::<anyhow::Result<Vec<_>>>()?;
        let port = lookup("PORT")
            .map(|s| s.parse::<u16>())
            .transpose()
            .context("PORT phải là số cổng")?
            .unwrap_or(8080);
        Ok(Self {
            database_url: required("DATABASE_URL")?,
            store_kind,
            container: lookup("IMAGE_STORE_CONTAINER").unwrap_or_else(|| "images".into()),
            read_only,
            secret_code,
            cluster,
            region: lookup("REGION").unwrap_or_default(),
            cors_origins: list("CORS_ORIGINS", "https://dr.qivarn.id.vn"),
            trusted_proxies,
            port,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;

    const REQUIRED: &[(&str, &str)] = &[
        ("DATABASE_URL", "postgres://x"),
        ("IMAGE_STORE", "s3"),
        ("CLUSTER", "primary"),
        ("SECRET_CODE", "0123456789abcdef"),
    ];

    fn parse(pairs: &[(&str, &str)]) -> anyhow::Result<Config> {
        let m: HashMap<String, String> = pairs
            .iter()
            .map(|(k, v)| (k.to_string(), v.to_string()))
            .collect();
        Config::from_lookup(|k| m.get(k).cloned())
    }

    #[test]
    fn reads_required_vars_and_defaults() {
        let c = parse(REQUIRED).unwrap();
        assert_eq!(c.store_kind, StoreKind::S3);
        assert_eq!(c.container, "images");
        assert!(!c.read_only);
        assert_eq!(c.cors_origins, vec!["https://dr.qivarn.id.vn".to_string()]);
        assert_eq!(c.port, 8080);
        assert!(c.trusted_proxies.is_empty());
        assert_eq!(c.region, "");
    }

    #[test]
    fn missing_required_var_fails() {
        for missing in ["DATABASE_URL", "IMAGE_STORE", "CLUSTER", "SECRET_CODE"] {
            let partial: Vec<_> = REQUIRED
                .iter()
                .copied()
                .filter(|(k, _)| *k != missing)
                .collect();
            assert!(parse(&partial).is_err(), "thiếu {missing} phải lỗi");
        }
    }

    #[test]
    fn invalid_values_fail() {
        for (k, v) in [
            ("SECRET_CODE", "short"),
            ("IMAGE_STORE", "gcs"),
            ("CLUSTER", "secondary"),
            ("IMAGE_STORE_READ_ONLY", "yes"),
            ("PORT", "abc"),
            ("TRUSTED_PROXIES", "10.0.0.0/99"),
        ] {
            let mut bad: Vec<_> = REQUIRED.iter().copied().filter(|(x, _)| *x != k).collect();
            bad.push((k, v));
            assert!(parse(&bad).is_err(), "{k}={v} phải lỗi");
        }
    }

    #[test]
    fn reads_lists_proxies_and_read_only_mode() {
        let mut v = REQUIRED.to_vec();
        v.extend([
            ("CORS_ORIGINS", "https://a.vn, http://localhost:4321"),
            ("TRUSTED_PROXIES", "10.42.0.0/16"),
            ("IMAGE_STORE_READ_ONLY", "true"),
            ("IMAGE_STORE", "azure"),
            ("CLUSTER", "standby"),
        ]);
        let c = parse(&v).unwrap();
        assert_eq!(
            c.cors_origins,
            vec![
                "https://a.vn".to_string(),
                "http://localhost:4321".to_string()
            ]
        );
        assert!(c.trusted_proxies[0].contains(&"10.42.3.4".parse::<std::net::IpAddr>().unwrap()));
        assert!(c.read_only);
        assert_eq!(c.store_kind, StoreKind::Azure);
        assert_eq!(c.cluster, "standby");
    }
}
