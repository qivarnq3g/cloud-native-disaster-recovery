use anyhow::{Context, bail};
use ipnet::IpNet;

pub const PHIEN_BAN: &str = match option_env!("PHIEN_BAN") {
    Some(v) => v,
    None => "dev",
};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum LoaiKho {
    Azure,
    S3,
}

#[derive(Clone, Debug)]
pub struct CauHinh {
    pub database_url: String,
    pub loai_kho: LoaiKho,
    pub ten_container: String,
    pub chi_doc: bool,
    pub ma_bi_mat: String,
    pub cum: String,
    pub vung: String,
    pub cors_nguon: Vec<String>,
    pub proxy_tin_cay: Vec<IpNet>,
    pub cong: u16,
}

impl CauHinh {
    pub fn tu_moi_truong() -> anyhow::Result<Self> {
        Self::tu_ham(|k| std::env::var(k).ok())
    }

    pub fn tu_ham(doc: impl Fn(&str) -> Option<String>) -> anyhow::Result<Self> {
        let bat_buoc = |k: &str| {
            doc(k)
                .filter(|v| !v.trim().is_empty())
                .with_context(|| format!("thiếu biến môi trường {k}"))
        };
        let danh_sach = |k: &str, mac_dinh: &str| -> Vec<String> {
            doc(k)
                .unwrap_or_else(|| mac_dinh.to_string())
                .split(',')
                .map(str::trim)
                .filter(|s| !s.is_empty())
                .map(String::from)
                .collect()
        };
        let loai_kho = match bat_buoc("KHO_ANH")?.as_str() {
            "azure" => LoaiKho::Azure,
            "s3" => LoaiKho::S3,
            khac => bail!("KHO_ANH phải là azure hoặc s3, nhận được {khac}"),
        };
        let cum = bat_buoc("CUM")?;
        if cum != "chinh" && cum != "du-phong" {
            bail!("CUM phải là chinh hoặc du-phong, nhận được {cum}");
        }
        let ma_bi_mat = bat_buoc("MA_BI_MAT")?;
        if ma_bi_mat.chars().count() < 16 {
            bail!("MA_BI_MAT phải dài ít nhất 16 ký tự");
        }
        let chi_doc = match doc("KHO_ANH_CHI_DOC").as_deref() {
            None | Some("") | Some("false") => false,
            Some("true") => true,
            Some(khac) => bail!("KHO_ANH_CHI_DOC phải là true hoặc false, nhận được {khac}"),
        };
        let proxy_tin_cay = danh_sach("PROXY_TIN_CAY", "")
            .iter()
            .map(|s| {
                s.parse::<IpNet>()
                    .with_context(|| format!("PROXY_TIN_CAY sai: {s}"))
            })
            .collect::<anyhow::Result<Vec<_>>>()?;
        let cong = doc("CONG")
            .map(|s| s.parse::<u16>())
            .transpose()
            .context("CONG phải là số cổng")?
            .unwrap_or(8080);
        Ok(Self {
            database_url: bat_buoc("DATABASE_URL")?,
            loai_kho,
            ten_container: doc("KHO_ANH_CONTAINER").unwrap_or_else(|| "anh".into()),
            chi_doc,
            ma_bi_mat,
            cum,
            vung: doc("VUNG").unwrap_or_default(),
            cors_nguon: danh_sach("CORS_NGUON", "https://dr.qivarn.id.vn"),
            proxy_tin_cay,
            cong,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;

    const DU: &[(&str, &str)] = &[
        ("DATABASE_URL", "postgres://x"),
        ("KHO_ANH", "s3"),
        ("CUM", "chinh"),
        ("MA_BI_MAT", "0123456789abcdef"),
    ];

    fn tu(cap: &[(&str, &str)]) -> anyhow::Result<CauHinh> {
        let m: HashMap<String, String> = cap
            .iter()
            .map(|(k, v)| (k.to_string(), v.to_string()))
            .collect();
        CauHinh::tu_ham(|k| m.get(k).cloned())
    }

    #[test]
    fn doc_bien_bat_buoc_va_gia_tri_mac_dinh() {
        let c = tu(DU).unwrap();
        assert_eq!(c.loai_kho, LoaiKho::S3);
        assert_eq!(c.ten_container, "anh");
        assert!(!c.chi_doc);
        assert_eq!(c.cors_nguon, vec!["https://dr.qivarn.id.vn".to_string()]);
        assert_eq!(c.cong, 8080);
        assert!(c.proxy_tin_cay.is_empty());
        assert_eq!(c.vung, "");
    }

    #[test]
    fn thieu_bien_bat_buoc_thi_loi() {
        for bo in ["DATABASE_URL", "KHO_ANH", "CUM", "MA_BI_MAT"] {
            let thieu: Vec<_> = DU.iter().copied().filter(|(k, _)| *k != bo).collect();
            assert!(tu(&thieu).is_err(), "thiếu {bo} phải lỗi");
        }
    }

    #[test]
    fn gia_tri_sai_thi_loi() {
        for (k, v) in [
            ("MA_BI_MAT", "ngan"),
            ("KHO_ANH", "gcs"),
            ("CUM", "phu"),
            ("KHO_ANH_CHI_DOC", "co"),
            ("CONG", "abc"),
            ("PROXY_TIN_CAY", "10.0.0.0/99"),
        ] {
            let mut sai: Vec<_> = DU.iter().copied().filter(|(x, _)| *x != k).collect();
            sai.push((k, v));
            assert!(tu(&sai).is_err(), "{k}={v} phải lỗi");
        }
    }

    #[test]
    fn doc_danh_sach_proxy_va_che_do_chi_doc() {
        let mut v = DU.to_vec();
        v.extend([
            ("CORS_NGUON", "https://a.vn, http://localhost:4321"),
            ("PROXY_TIN_CAY", "10.42.0.0/16"),
            ("KHO_ANH_CHI_DOC", "true"),
            ("KHO_ANH", "azure"),
            ("CUM", "du-phong"),
        ]);
        let c = tu(&v).unwrap();
        assert_eq!(
            c.cors_nguon,
            vec![
                "https://a.vn".to_string(),
                "http://localhost:4321".to_string()
            ]
        );
        assert!(c.proxy_tin_cay[0].contains(&"10.42.3.4".parse::<std::net::IpAddr>().unwrap()));
        assert!(c.chi_doc);
        assert_eq!(c.loai_kho, LoaiKho::Azure);
        assert_eq!(c.cum, "du-phong");
    }
}
