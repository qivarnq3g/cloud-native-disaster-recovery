mod chung;

use api::csdl::Bai;
use chung::{CAC_KHO, LoaiKhoThu, chay, chay_khong_cho, kho_chet, kho_ghi, pool_chet, them_truc_tiep};
use serde_json::Value;
use sha2::{Digest, Sha256};

#[tokio::test]
async fn danh_sach_xem_bai_va_lay_anh_goc() {
    for loai in CAC_KHO {
        let app = chay(kho_ghi(loai), false).await;
        let b = them_truc_tiep(&app, 64, 48).await;
        let c = reqwest::Client::new();
        let ds: Value = c.get(format!("{}/v1/bai?so=60", app.url)).send().await.unwrap().json().await.unwrap();
        assert!(ds["bai"].as_array().unwrap().iter().any(|x| x["id"] == b.id.to_string()), "{loai:?}");
        let mot: Bai = c.get(format!("{}/v1/bai/{}", app.url, b.id)).send().await.unwrap().json().await.unwrap();
        assert_eq!(mot, b);
        let r = c.get(format!("{}/v1/bai/{}/anh", app.url, b.id)).send().await.unwrap();
        assert_eq!(r.status(), 200);
        assert_eq!(r.headers()["content-type"], "image/png");
        assert_eq!(r.headers()["cache-control"], "public, max-age=31536000, immutable");
        assert_eq!(r.headers()["etag"], format!("\"{}\"", b.anh_sha256));
        assert_eq!(r.headers()["x-content-type-options"], "nosniff");
        let byte = r.bytes().await.unwrap();
        assert_eq!(hex::encode(Sha256::digest(&byte)), b.anh_sha256);
    }
}

#[tokio::test]
async fn anh_nho_cua_anh_lon_la_avif_cua_anh_nho_la_anh_goc() {
    let app = chay(kho_ghi(LoaiKhoThu::Seaweed), false).await;
    let lon = them_truc_tiep(&app, 1200, 900).await;
    let nho = them_truc_tiep(&app, 64, 48).await;
    let c = reqwest::Client::new();
    let r = c.get(format!("{}/v1/bai/{}/anh-nho", app.url, lon.id)).send().await.unwrap();
    assert_eq!(r.headers()["content-type"], "image/avif");
    assert_eq!(r.headers()["etag"], format!("\"{}-nho\"", lon.anh_sha256));
    let r = c.get(format!("{}/v1/bai/{}/anh-nho", app.url, nho.id)).send().await.unwrap();
    assert_eq!(r.headers()["content-type"], "image/png");
    assert_eq!(hex::encode(Sha256::digest(r.bytes().await.unwrap())), nho.anh_sha256);
}

#[tokio::test]
async fn tham_so_sai_tra_json_loi() {
    let app = chay(kho_ghi(LoaiKhoThu::Seaweed), false).await;
    let c = reqwest::Client::new();
    for (duong, so, ma) in [
        ("/v1/bai?so=0", 422, "du_lieu_sai"),
        ("/v1/bai?so=61", 422, "du_lieu_sai"),
        ("/v1/bai?truoc=khong-phai-uuid", 422, "du_lieu_sai"),
        ("/v1/bai/khong-phai-uuid", 404, "khong_tim_thay"),
        ("/v1/bai/0192f0c0-0000-7000-8000-000000000000", 404, "khong_tim_thay"),
        ("/v1/bai/0192f0c0-0000-7000-8000-000000000000/anh", 404, "khong_tim_thay"),
    ] {
        let r = c.get(format!("{}{duong}", app.url)).send().await.unwrap();
        assert_eq!(r.status(), so, "{duong}");
        let v: Value = r.json().await.unwrap();
        assert_eq!(v["loi"], ma, "{duong}");
    }
}

#[tokio::test]
async fn healthz_on_khi_csdl_va_kho_deu_tra_loi() {
    for loai in CAC_KHO {
        let app = chay(kho_ghi(loai), false).await;
        let r = reqwest::get(format!("{}/healthz", app.url)).await.unwrap();
        assert_eq!(r.status(), 200, "{loai:?}");
        assert_eq!(r.headers()["cache-control"], "no-store");
        let v: Value = r.json().await.unwrap();
        assert_eq!(v["trang_thai"], "on");
        assert_eq!(v["cum"], "chinh");
        assert_eq!(v["vung"], "thu");
        assert_eq!(v["chi_doc"], false);
        assert!(v.get("hong").is_none());
    }
}

#[tokio::test]
async fn healthz_bao_dung_phan_hong_va_livez_van_song() {
    let app = chay_khong_cho(pool_chet(), kho_chet(), false).await;
    let bat_dau = std::time::Instant::now();
    let r = reqwest::get(format!("{}/healthz", app.url)).await.unwrap();
    assert!(bat_dau.elapsed() < std::time::Duration::from_secs(5));
    assert_eq!(r.status(), 503);
    let v: Value = r.json().await.unwrap();
    assert_eq!(v["trang_thai"], "loi");
    assert_eq!(v["hong"], serde_json::json!(["csdl", "kho_anh"]));
    assert_eq!(reqwest::get(format!("{}/livez", app.url)).await.unwrap().status(), 204);
}

#[tokio::test]
async fn cors_chi_cho_nguon_trong_cau_hinh() {
    let app = chay(kho_ghi(LoaiKhoThu::Seaweed), false).await;
    let c = reqwest::Client::new();
    let duoc = c.get(format!("{}/healthz", app.url)).header("origin", "http://localhost:4321").send().await.unwrap();
    assert_eq!(duoc.headers()["access-control-allow-origin"], "http://localhost:4321");
    let khong = c.get(format!("{}/healthz", app.url)).header("origin", "https://la.vn").send().await.unwrap();
    assert!(khong.headers().get("access-control-allow-origin").is_none());
}

#[tokio::test]
async fn khoi_dong_truoc_csdl_khong_thoat_va_tu_tao_bang_khi_csdl_co_lai() {
    let app = chay_khong_cho(pool_chet(), kho_ghi(LoaiKhoThu::Seaweed), false).await;
    tokio::time::sleep(std::time::Duration::from_secs(3)).await;
    let v: Value = reqwest::get(format!("{}/healthz", app.url)).await.unwrap().json().await.unwrap();
    assert_eq!(v["hong"], serde_json::json!(["csdl"]));
    assert!(!app.tt.da_migrate.load(std::sync::atomic::Ordering::Acquire));
    assert_eq!(reqwest::get(format!("{}/livez", app.url)).await.unwrap().status(), 204);
}
