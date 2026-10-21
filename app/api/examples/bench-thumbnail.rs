use std::io::Cursor;
use std::time::Instant;

use api::image_file::ImageType;
use api::thumbnail::make_thumbnail;
use image::{DynamicImage, ImageFormat, RgbImage};

fn main() {
    let runs: usize = std::env::args()
        .nth(1)
        .and_then(|s| s.parse().ok())
        .unwrap_or(20);
    let image = DynamicImage::ImageRgb8(RgbImage::from_fn(2560, 1920, |x, y| {
        let n = (x.wrapping_mul(2_654_435_761) ^ y.wrapping_mul(40_503)) % 64;
        image::Rgb([
            ((x / 10) % 256) as u8 ^ n as u8,
            ((y / 8) % 256) as u8,
            ((x + y) % 256) as u8,
        ])
    }));
    let mut jpeg = Cursor::new(Vec::new());
    image.write_to(&mut jpeg, ImageFormat::Jpeg).unwrap();
    let jpeg = jpeg.into_inner();
    let mut ms: Vec<f64> = (0..runs)
        .map(|_| {
            let t = Instant::now();
            make_thumbnail(&jpeg, ImageType::Jpeg).unwrap();
            t.elapsed().as_secs_f64() * 1000.0
        })
        .collect();
    ms.sort_by(f64::total_cmp);
    let p95 = ms[((ms.len() as f64 * 0.95).ceil() as usize).saturating_sub(1)];
    println!(
        "n={} median_ms={:.0} p95_ms={:.0} jpeg_bytes={}",
        ms.len(),
        ms[ms.len() / 2],
        p95,
        jpeg.len()
    );
}
