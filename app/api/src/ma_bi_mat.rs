use std::collections::{HashMap, VecDeque};
use std::net::{IpAddr, SocketAddr};
use std::sync::Mutex;
use std::time::{Duration, Instant};

use axum::http::{HeaderMap, header};
use ipnet::IpNet;
use subtle::ConstantTimeEq;

use crate::loi::ApiLoi;

pub struct KiemTraMa {
    ma: Vec<u8>,
    sai: Mutex<HashMap<IpAddr, VecDeque<Instant>>>,
    toi_da: usize,
    cua_so: Duration,
}

impl KiemTraMa {
    pub fn moi(ma: &str) -> Self {
        Self::voi_gioi_han(ma, 10, Duration::from_secs(600))
    }

    pub fn voi_gioi_han(ma: &str, toi_da: usize, cua_so: Duration) -> Self {
        Self { ma: ma.as_bytes().to_vec(), sai: Mutex::new(HashMap::new()), toi_da, cua_so }
    }

    pub fn kiem_tra(&self, ip: IpAddr, ma_gui: Option<&str>, bay_gio: Instant) -> Result<(), ApiLoi> {
        let mut sai = self.sai.lock().expect("khoa bo dem sai ma");
        if sai.len() > 10_000 {
            sai.retain(|_, hang| {
                bo_cu(hang, bay_gio, self.cua_so);
                !hang.is_empty()
            });
        }
        let hang = sai.entry(ip).or_default();
        bo_cu(hang, bay_gio, self.cua_so);
        if hang.len() >= self.toi_da {
            let con_lai = self.cua_so.saturating_sub(bay_gio.duration_since(hang[0]));
            return Err(ApiLoi::ThuQuaNhieu(con_lai.as_secs().max(1)));
        }
        let dung: bool = ma_gui.map(|m| bool::from(m.as_bytes().ct_eq(&self.ma))).unwrap_or(false);
        if dung {
            let khong_con = hang.is_empty();
            if khong_con {
                sai.remove(&ip);
            }
            Ok(())
        } else {
            hang.push_back(bay_gio);
            Err(ApiLoi::MaSai)
        }
    }
}

fn bo_cu(hang: &mut VecDeque<Instant>, bay_gio: Instant, cua_so: Duration) {
    while hang.front().is_some_and(|t| bay_gio.duration_since(*t) >= cua_so) {
        hang.pop_front();
    }
}

pub fn ip_khach(nguon: SocketAddr, headers: &HeaderMap, tin_cay: &[IpNet]) -> IpAddr {
    let ip = nguon.ip();
    if tin_cay.iter().any(|n| n.contains(&ip)) {
        let tu_proxy = headers
            .get("x-forwarded-for")
            .and_then(|v| v.to_str().ok())
            .and_then(|s| s.split(',').next_back())
            .and_then(|s| s.trim().parse::<IpAddr>().ok());
        if let Some(x) = tu_proxy {
            return x;
        }
    }
    ip
}

pub fn ma_tu_header(headers: &HeaderMap) -> Option<&str> {
    headers.get(header::AUTHORIZATION)?.to_str().ok()?.strip_prefix("Bearer ")
}

#[cfg(test)]
mod tests {
    use super::*;
    use axum::http::HeaderValue;

    const MA: &str = "0123456789abcdef";

    fn ip(s: &str) -> IpAddr {
        s.parse().unwrap()
    }

    #[test]
    fn ma_dung_thi_qua_ma_sai_hoac_thieu_thi_401() {
        let k = KiemTraMa::moi(MA);
        let t = Instant::now();
        assert_eq!(k.kiem_tra(ip("1.2.3.4"), Some(MA), t), Ok(()));
        assert_eq!(k.kiem_tra(ip("1.2.3.4"), Some("sai"), t), Err(ApiLoi::MaSai));
        assert_eq!(k.kiem_tra(ip("1.2.3.4"), Some("0123456789abcdeX"), t), Err(ApiLoi::MaSai));
        assert_eq!(k.kiem_tra(ip("1.2.3.4"), None, t), Err(ApiLoi::MaSai));
    }

    #[test]
    fn sai_10_lan_thi_chan_ca_ma_dung_toi_het_cua_so() {
        let k = KiemTraMa::voi_gioi_han(MA, 10, Duration::from_secs(600));
        let t0 = Instant::now();
        for i in 0..10 {
            assert_eq!(k.kiem_tra(ip("1.2.3.4"), Some("sai"), t0 + Duration::from_secs(i)), Err(ApiLoi::MaSai));
        }
        assert_eq!(k.kiem_tra(ip("1.2.3.4"), Some(MA), t0 + Duration::from_secs(100)), Err(ApiLoi::ThuQuaNhieu(500)));
        assert_eq!(k.kiem_tra(ip("5.6.7.8"), Some(MA), t0 + Duration::from_secs(100)), Ok(()));
        assert_eq!(k.kiem_tra(ip("1.2.3.4"), Some(MA), t0 + Duration::from_secs(611)), Ok(()));
    }

    #[test]
    fn chi_tin_x_forwarded_for_tu_proxy() {
        let tin: Vec<IpNet> = vec!["10.42.0.0/16".parse().unwrap()];
        let mut h = HeaderMap::new();
        h.insert("x-forwarded-for", HeaderValue::from_static("9.9.9.9, 203.0.113.7"));
        assert_eq!(ip_khach("10.42.0.5:1234".parse().unwrap(), &h, &tin), ip("203.0.113.7"));
        assert_eq!(ip_khach("198.51.100.1:1234".parse().unwrap(), &h, &tin), ip("198.51.100.1"));
        assert_eq!(ip_khach("10.42.0.5:1234".parse().unwrap(), &HeaderMap::new(), &tin), ip("10.42.0.5"));
    }

    #[test]
    fn doc_ma_tu_bearer() {
        let mut h = HeaderMap::new();
        h.insert(header::AUTHORIZATION, HeaderValue::from_static("Bearer abc"));
        assert_eq!(ma_tu_header(&h), Some("abc"));
        h.insert(header::AUTHORIZATION, HeaderValue::from_static("Basic abc"));
        assert_eq!(ma_tu_header(&h), None);
    }
}
