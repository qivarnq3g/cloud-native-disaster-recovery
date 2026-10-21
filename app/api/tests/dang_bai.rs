mod chung;

use api::csdl::Bai;
use chung::{CAC_KHO, LoaiKhoThu, MA, chay, dang, kho_ghi, png};
use serde_json::Value;
use sha2::{Digest, Sha256};
use uuid::Uuid;

#[tokio::test]
async fn dang_roi_xem_roi_lay_anh_khop_sha256() {
    for loai in CAC_KHO {
        let app = chay(kho_ghi(loai), false).await;
        let c = reqwest::Client::new();
        let anh = png(64, 48);
        let r = dang(
            &c,
            &app.url,
            MA,
            Uuid::now_v7(),
            "  Bài   thử ",
            anh.clone(),
        )
        .await;
        assert_eq!(r.status(), 201, "{loai:?}");
        let b: Bai = r.json().await.unwrap();
        assert_eq!(b.tieu_de, "Bài   thử");
        assert_eq!(b.anh_sha256, hex::encode(Sha256::digest(&anh)));
        let byte = c
            .get(format!("{}/v1/bai/{}/anh", app.url, b.id))
            .send()
            .await
            .unwrap()
            .bytes()
            .await
            .unwrap();
        assert_eq!(byte.as_ref(), anh.as_slice());
    }
}

#[tokio::test]
async fn gui_lai_cung_ma_lan_dang_ke_ca_song_song_chi_ra_mot_bai() {
    let app = chay(kho_ghi(LoaiKhoThu::Seaweed), false).await;
    let c = reqwest::Client::new();
    let ma = Uuid::now_v7();
    let (a, b) = tokio::join!(
        dang(&c, &app.url, MA, ma, "Song song", png(64, 48)),
        dang(&c, &app.url, MA, ma, "Song song", png(64, 48))
    );
    let mut trang_thai = vec![a.status().as_u16(), b.status().as_u16()];
    trang_thai.sort();
    assert_eq!(trang_thai, vec![200, 201]);
    let lan_ba = dang(&c, &app.url, MA, ma, "Khác", png(64, 48)).await;
    assert_eq!(lan_ba.status(), 200);
    let so: i64 = sqlx::query_scalar("SELECT count(*) FROM bai WHERE ma_lan_dang = $1")
        .bind(ma)
        .fetch_one(&app.tt.pool)
        .await
        .unwrap();
    assert_eq!(so, 1);
}

#[tokio::test]
async fn loi_dau_vao_tra_dung_ma_loi() {
    let app = chay(kho_ghi(LoaiKhoThu::Seaweed), false).await;
    let c = reqwest::Client::new();
    let mut qua_lon = b"\x89PNG\r\n\x1a\n".to_vec();
    qua_lon.resize(1_048_577, 0);
    for (ma, tieu_de, anh, so, loi) in [
        ("sai-ma-0123456789", "Ok", png(8, 8), 401, "ma_sai"),
        (
            MA,
            "Ok",
            "không phải ảnh".as_bytes().to_vec(),
            415,
            "khong_phai_anh",
        ),
        (MA, "Ok", qua_lon, 413, "anh_qua_lon"),
        (MA, &"a".repeat(101), png(8, 8), 422, "du_lieu_sai"),
    ] {
        let r = dang(&c, &app.url, ma, Uuid::now_v7(), tieu_de, anh).await;
        assert_eq!(r.status(), so, "{loi}");
        let v: Value = r.json().await.unwrap();
        assert_eq!(v["loi"], loi);
    }
}

#[tokio::test]
async fn kiem_tra_ma_va_chan_sau_10_lan_sai() {
    let app = chay(kho_ghi(LoaiKhoThu::Seaweed), false).await;
    let c = reqwest::Client::new();
    let url = format!("{}/v1/ma/kiem-tra", app.url);
    assert_eq!(
        c.post(&url).bearer_auth(MA).send().await.unwrap().status(),
        204
    );
    for _ in 0..10 {
        assert_eq!(
            c.post(&url)
                .bearer_auth("sai")
                .send()
                .await
                .unwrap()
                .status(),
            401
        );
    }
    let r = c.post(&url).bearer_auth(MA).send().await.unwrap();
    assert_eq!(r.status(), 429);
    assert!(r.headers().contains_key("retry-after"));
}
