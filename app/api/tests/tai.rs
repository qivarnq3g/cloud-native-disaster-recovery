mod chung;

use std::io::Cursor;
use std::time::{Duration, Instant};

use chung::{LoaiKhoThu, MA, chay, dang, kho_ghi};
use image::{DynamicImage, ImageFormat, RgbImage};
use uuid::Uuid;

fn anh_cua_script(i: u32) -> Vec<u8> {
    let anh = DynamicImage::ImageRgb8(RgbImage::from_fn(160, 120, |x, y| {
        let n = x
            .wrapping_mul(2_654_435_761)
            .wrapping_add(y.wrapping_mul(40_503))
            .wrapping_add(i.wrapping_mul(97));
        image::Rgb([n as u8, (n >> 8) as u8, (n >> 16) as u8])
    }));
    let mut ra = Cursor::new(Vec::new());
    anh.write_to(&mut ra, ImageFormat::Png).unwrap();
    ra.into_inner()
}

#[tokio::test(flavor = "multi_thread")]
#[ignore = "chạy riêng: cargo test --test tai -- --ignored --nocapture"]
async fn dang_mot_bai_moi_giay_trong_nam_phut_ton_duoi_10_phan_tram_mot_nhan() {
    let app = chay(kho_ghi(LoaiKhoThu::Seaweed), false).await;
    let c = reqwest::Client::new();
    let cpu = cpu_time::ProcessTime::now();
    let bat_dau = Instant::now();
    for i in 0..300 {
        let moc = Instant::now();
        let r = dang(
            &c,
            &app.url,
            MA,
            Uuid::now_v7(),
            &format!("Tải {i}"),
            anh_cua_script(i),
        )
        .await;
        assert_eq!(r.status(), 201);
        tokio::time::sleep(Duration::from_secs(1).saturating_sub(moc.elapsed())).await;
    }
    let ty_le = cpu.elapsed().as_secs_f64() / bat_dau.elapsed().as_secs_f64();
    println!("cpu_tren_thoi_gian={ty_le:.3}");
    assert!(ty_le <= 0.10, "CPU {ty_le:.3} vượt 10% một nhân");
}
