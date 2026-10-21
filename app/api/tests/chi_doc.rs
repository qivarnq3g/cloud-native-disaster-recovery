mod chung;

use chung::{CAC_KHO, MA, chay, dang, kho_chet, kho_doc, kho_ghi, png, them_truc_tiep};
use serde_json::Value;
use uuid::Uuid;

#[tokio::test]
async fn chi_doc_van_xem_duoc_anh_nho_khong_ghi_vao_kho_va_tu_choi_dang() {
    for loai in CAC_KHO {
        let ghi = chay(kho_ghi(loai), false).await;
        let b = them_truc_tiep(&ghi, 1200, 900).await;
        let doc = chay(kho_doc(loai), true).await;
        let c = reqwest::Client::new();
        let r = c
            .get(format!("{}/v1/bai/{}/anh-nho", doc.url, b.id))
            .send()
            .await
            .unwrap();
        assert_eq!(r.status(), 200, "{loai:?}");
        assert_eq!(r.headers()["content-type"], "image/avif");
        assert_eq!(kho_ghi(loai).lay_nho(b.id).await.unwrap(), None, "{loai:?}");
        let r = dang(&c, &doc.url, MA, Uuid::now_v7(), "Không được", png(8, 8)).await;
        assert_eq!(r.status(), 503);
        assert_eq!(r.json::<Value>().await.unwrap()["loi"], "chi_doc");
        let v: Value = c
            .get(format!("{}/healthz", doc.url))
            .send()
            .await
            .unwrap()
            .json()
            .await
            .unwrap();
        assert_eq!(v["trang_thai"], "on", "{loai:?}");
        assert_eq!(v["chi_doc"], true);
    }
}

#[tokio::test]
async fn quen_bat_chi_doc_voi_ma_chi_doc_thi_van_xem_duoc() {
    for loai in CAC_KHO {
        let ghi = chay(kho_ghi(loai), false).await;
        let b = them_truc_tiep(&ghi, 1200, 900).await;
        let nham = chay(kho_doc(loai), false).await;
        let r = reqwest::get(format!("{}/v1/bai/{}/anh-nho", nham.url, b.id))
            .await
            .unwrap();
        assert_eq!(r.status(), 200, "{loai:?}");
        assert_eq!(kho_ghi(loai).lay_nho(b.id).await.unwrap(), None, "{loai:?}");
    }
}

#[tokio::test]
async fn kho_chet_khi_dang_tra_tam_ngung_va_khong_de_lai_bai() {
    let app = chay(kho_chet(), false).await;
    let c = reqwest::Client::new();
    let ma = Uuid::now_v7();
    let bat_dau = std::time::Instant::now();
    let r = dang(&c, &app.url, MA, ma, "Kho chết", png(8, 8)).await;
    assert!(bat_dau.elapsed() < std::time::Duration::from_secs(30));
    assert_eq!(r.status(), 503);
    assert_eq!(r.json::<Value>().await.unwrap()["loi"], "tam_ngung");
    let so: i64 = sqlx::query_scalar("SELECT count(*) FROM bai WHERE ma_lan_dang = $1")
        .bind(ma)
        .fetch_one(&app.tt.pool)
        .await
        .unwrap();
    assert_eq!(so, 0);
}
