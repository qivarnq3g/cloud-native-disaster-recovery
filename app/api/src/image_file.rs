use std::io::Cursor;

use bytes::Bytes;
use image::{ImageFormat, ImageReader, Limits};
use sha2::{Digest, Sha256};

use crate::error::ApiError;

pub const MAX_BYTES: usize = 1_048_576;
pub const MAX_PIXELS: u64 = 50_000_000;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ImageType {
    Jpeg,
    Png,
    Webp,
}

impl ImageType {
    pub fn mime(self) -> &'static str {
        match self {
            ImageType::Jpeg => "image/jpeg",
            ImageType::Png => "image/png",
            ImageType::Webp => "image/webp",
        }
    }

    pub fn from_mime(s: &str) -> Option<Self> {
        match s {
            "image/jpeg" => Some(ImageType::Jpeg),
            "image/png" => Some(ImageType::Png),
            "image/webp" => Some(ImageType::Webp),
            _ => None,
        }
    }

    pub fn detect(d: &[u8]) -> Option<Self> {
        if d.starts_with(&[0xFF, 0xD8, 0xFF]) {
            Some(ImageType::Jpeg)
        } else if d.starts_with(b"\x89PNG\r\n\x1a\n") {
            Some(ImageType::Png)
        } else if d.len() >= 12 && &d[0..4] == b"RIFF" && &d[8..12] == b"WEBP" {
            Some(ImageType::Webp)
        } else {
            None
        }
    }

    fn image_format(self) -> ImageFormat {
        match self {
            ImageType::Jpeg => ImageFormat::Jpeg,
            ImageType::Png => ImageFormat::Png,
            ImageType::Webp => ImageFormat::WebP,
        }
    }
}

#[derive(Debug, Clone)]
pub struct ValidImage {
    pub kind: ImageType,
    pub width: u32,
    pub height: u32,
    pub sha256: [u8; 32],
    pub data: Bytes,
}

pub fn validate(data: Bytes) -> Result<ValidImage, ApiError> {
    if data.len() > MAX_BYTES {
        return Err(ApiError::ImageTooLarge("Ảnh lớn hơn 1 MB."));
    }
    let kind = ImageType::detect(&data).ok_or(ApiError::NotAnImage)?;
    let (width, height) = ImageReader::with_format(Cursor::new(&data[..]), kind.image_format())
        .into_dimensions()
        .map_err(|_| ApiError::NotAnImage)?;
    if width == 0 || height == 0 {
        return Err(ApiError::NotAnImage);
    }
    if u64::from(width) * u64::from(height) > MAX_PIXELS {
        return Err(ApiError::ImageTooLarge("Ảnh có quá nhiều điểm ảnh."));
    }
    decode(&data, kind).map_err(|_| ApiError::NotAnImage)?;
    let sha256: [u8; 32] = Sha256::digest(&data).into();
    Ok(ValidImage {
        kind,
        width,
        height,
        sha256,
        data,
    })
}

pub fn decode(data: &[u8], kind: ImageType) -> image::ImageResult<image::DynamicImage> {
    let mut reader = ImageReader::with_format(Cursor::new(data), kind.image_format());
    let mut limits = Limits::default();
    limits.max_alloc = Some(256 * 1024 * 1024);
    reader.limits(limits);
    reader.decode()
}

#[cfg(test)]
mod tests {
    use super::*;
    use image::{DynamicImage, GrayImage, RgbImage};

    fn encode(image: DynamicImage, format: ImageFormat) -> Bytes {
        let mut out = Cursor::new(Vec::new());
        image.write_to(&mut out, format).unwrap();
        Bytes::from(out.into_inner())
    }

    fn sample(width: u32, height: u32) -> DynamicImage {
        DynamicImage::ImageRgb8(RgbImage::from_fn(width, height, |x, y| {
            image::Rgb([(x % 256) as u8, (y % 256) as u8, 90])
        }))
    }

    #[test]
    fn accepts_png_jpeg_webp_and_reads_dimensions() {
        for (format, kind) in [
            (ImageFormat::Png, ImageType::Png),
            (ImageFormat::Jpeg, ImageType::Jpeg),
            (ImageFormat::WebP, ImageType::Webp),
        ] {
            let b = encode(sample(64, 48), format);
            let a = validate(b.clone()).unwrap();
            assert_eq!(a.kind, kind);
            assert_eq!((a.width, a.height), (64, 48));
            let expected: [u8; 32] = Sha256::digest(&b).into();
            assert_eq!(a.sha256, expected);
            assert_eq!(a.data, b);
        }
    }

    #[test]
    fn renamed_file_is_not_an_image() {
        assert_eq!(
            validate(Bytes::from_static("xin chào".as_bytes())).unwrap_err(),
            ApiError::NotAnImage
        );
    }

    #[test]
    fn corrupt_image_is_not_an_image() {
        let b = encode(sample(64, 48), ImageFormat::Png);
        assert_eq!(validate(b.slice(0..60)).unwrap_err(), ApiError::NotAnImage);
    }

    #[test]
    fn over_1_mib_is_too_large() {
        let mut v = b"\x89PNG\r\n\x1a\n".to_vec();
        v.resize(MAX_BYTES + 1, 0);
        assert!(matches!(
            validate(Bytes::from(v)).unwrap_err(),
            ApiError::ImageTooLarge(_)
        ));
    }

    #[test]
    fn over_50_megapixels_is_too_large() {
        let b = encode(
            DynamicImage::ImageLuma8(GrayImage::new(8000, 7000)),
            ImageFormat::Png,
        );
        assert!(b.len() <= MAX_BYTES);
        assert!(matches!(
            validate(b).unwrap_err(),
            ApiError::ImageTooLarge(_)
        ));
    }

    #[test]
    fn mime_round_trip() {
        for k in [ImageType::Jpeg, ImageType::Png, ImageType::Webp] {
            assert_eq!(ImageType::from_mime(k.mime()), Some(k));
        }
        assert_eq!(ImageType::from_mime("image/gif"), None);
    }
}
