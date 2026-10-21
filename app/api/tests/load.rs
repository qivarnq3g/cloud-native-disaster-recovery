mod common;

use std::io::Cursor;
use std::time::{Duration, Instant};

use common::{TEST_CODE, TestStore, start, submit_post, writable_store};
use image::{DynamicImage, ImageFormat, RgbImage};
use uuid::Uuid;

fn script_image(i: u32) -> Vec<u8> {
    let image = DynamicImage::ImageRgb8(RgbImage::from_fn(160, 120, |x, y| {
        let n = x
            .wrapping_mul(2_654_435_761)
            .wrapping_add(y.wrapping_mul(40_503))
            .wrapping_add(i.wrapping_mul(97));
        image::Rgb([n as u8, (n >> 8) as u8, (n >> 16) as u8])
    }));
    let mut out = Cursor::new(Vec::new());
    image.write_to(&mut out, ImageFormat::Png).unwrap();
    out.into_inner()
}

#[tokio::test(flavor = "multi_thread")]
#[ignore = "chạy riêng: cargo test --test load -- --ignored --nocapture"]
async fn one_post_per_second_for_five_minutes_uses_under_ten_percent_of_a_core() {
    let app = start(writable_store(TestStore::Seaweed), false).await;
    let c = reqwest::Client::new();
    let cpu = cpu_time::ProcessTime::now();
    let started = Instant::now();
    for i in 0..300 {
        let tick = Instant::now();
        let r = submit_post(
            &c,
            &app.url,
            TEST_CODE,
            Uuid::now_v7(),
            &format!("Tải {i}"),
            script_image(i),
        )
        .await;
        assert_eq!(r.status(), 201);
        tokio::time::sleep(Duration::from_secs(1).saturating_sub(tick.elapsed())).await;
    }
    let ratio = cpu.elapsed().as_secs_f64() / started.elapsed().as_secs_f64();
    println!("cpu_ratio={ratio:.3}");
    assert!(ratio <= 0.10, "CPU {ratio:.3} vượt 10% một nhân");
}
