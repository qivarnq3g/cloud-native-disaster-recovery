use std::io::Cursor;

use bytes::Bytes;
use image::{ImageFormat, ImageReader, Limits};
use sha2::{Digest, Sha256};

use crate::loi::ApiLoi;

pub const BYTE_TOI_DA: usize = 1_048_576;
pub const DIEM_ANH_TOI_DA: u64 = 50_000_000;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum KieuAnh {
    Jpeg,
    Png,
    Webp,
}

impl KieuAnh {
    pub fn mime(self) -> &'static str {
        match self {
            KieuAnh::Jpeg => "image/jpeg",
            KieuAnh::Png => "image/png",
            KieuAnh::Webp => "image/webp",
        }
    }

    pub fn tu_mime(s: &str) -> Option<Self> {
        match s {
            "image/jpeg" => Some(KieuAnh::Jpeg),
            "image/png" => Some(KieuAnh::Png),
            "image/webp" => Some(KieuAnh::Webp),
            _ => None,
        }
    }

    pub fn nhan_dang(d: &[u8]) -> Option<Self> {
        if d.starts_with(&[0xFF, 0xD8, 0xFF]) {
            Some(KieuAnh::Jpeg)
        } else if d.starts_with(b"\x89PNG\r\n\x1a\n") {
            Some(KieuAnh::Png)
        } else if d.len() >= 12 && &d[0..4] == b"RIFF" && &d[8..12] == b"WEBP" {
            Some(KieuAnh::Webp)
        } else {
            None
        }
    }

    fn dinh_dang(self) -> ImageFormat {
        match self {
            KieuAnh::Jpeg => ImageFormat::Jpeg,
            KieuAnh::Png => ImageFormat::Png,
            KieuAnh::Webp => ImageFormat::WebP,
        }
    }
}

#[derive(Debug, Clone)]
pub struct AnhHopLe {
    pub kieu: KieuAnh,
    pub rong: u32,
    pub cao: u32,
    pub sha256: [u8; 32],
    pub du_lieu: Bytes,
}

pub fn kiem_tra(du_lieu: Bytes) -> Result<AnhHopLe, ApiLoi> {
    if du_lieu.len() > BYTE_TOI_DA {
        return Err(ApiLoi::AnhQuaLon("Ảnh lớn hơn 1 MB."));
    }
    let kieu = KieuAnh::nhan_dang(&du_lieu).ok_or(ApiLoi::KhongPhaiAnh)?;
    let (rong, cao) = ImageReader::with_format(Cursor::new(&du_lieu[..]), kieu.dinh_dang())
        .into_dimensions()
        .map_err(|_| ApiLoi::KhongPhaiAnh)?;
    if rong == 0 || cao == 0 {
        return Err(ApiLoi::KhongPhaiAnh);
    }
    if u64::from(rong) * u64::from(cao) > DIEM_ANH_TOI_DA {
        return Err(ApiLoi::AnhQuaLon("Ảnh có quá nhiều điểm ảnh."));
    }
    giai_ma(&du_lieu, kieu).map_err(|_| ApiLoi::KhongPhaiAnh)?;
    let sha256: [u8; 32] = Sha256::digest(&du_lieu).into();
    Ok(AnhHopLe {
        kieu,
        rong,
        cao,
        sha256,
        du_lieu,
    })
}

pub fn giai_ma(du_lieu: &[u8], kieu: KieuAnh) -> image::ImageResult<image::DynamicImage> {
    let mut doc = ImageReader::with_format(Cursor::new(du_lieu), kieu.dinh_dang());
    let mut gioi_han = Limits::default();
    gioi_han.max_alloc = Some(256 * 1024 * 1024);
    doc.limits(gioi_han);
    doc.decode()
}

#[cfg(test)]
mod tests {
    use super::*;
    use image::{DynamicImage, GrayImage, RgbImage};

    fn ma_hoa(anh: DynamicImage, dd: ImageFormat) -> Bytes {
        let mut ra = Cursor::new(Vec::new());
        anh.write_to(&mut ra, dd).unwrap();
        Bytes::from(ra.into_inner())
    }

    fn mau(rong: u32, cao: u32) -> DynamicImage {
        DynamicImage::ImageRgb8(RgbImage::from_fn(rong, cao, |x, y| {
            image::Rgb([(x % 256) as u8, (y % 256) as u8, 90])
        }))
    }

    #[test]
    fn nhan_png_jpeg_webp_va_doc_kich_thuoc() {
        for (dd, kieu) in [
            (ImageFormat::Png, KieuAnh::Png),
            (ImageFormat::Jpeg, KieuAnh::Jpeg),
            (ImageFormat::WebP, KieuAnh::Webp),
        ] {
            let b = ma_hoa(mau(64, 48), dd);
            let a = kiem_tra(b.clone()).unwrap();
            assert_eq!(a.kieu, kieu);
            assert_eq!((a.rong, a.cao), (64, 48));
            let ky_vong: [u8; 32] = Sha256::digest(&b).into();
            assert_eq!(a.sha256, ky_vong);
            assert_eq!(a.du_lieu, b);
        }
    }

    #[test]
    fn tep_doi_duoi_khong_phai_anh() {
        assert_eq!(
            kiem_tra(Bytes::from_static("xin chào".as_bytes())).unwrap_err(),
            ApiLoi::KhongPhaiAnh
        );
    }

    #[test]
    fn anh_hong_khong_phai_anh() {
        let b = ma_hoa(mau(64, 48), ImageFormat::Png);
        assert_eq!(kiem_tra(b.slice(0..60)).unwrap_err(), ApiLoi::KhongPhaiAnh);
    }

    #[test]
    fn qua_1_mib_thi_qua_lon() {
        let mut v = b"\x89PNG\r\n\x1a\n".to_vec();
        v.resize(BYTE_TOI_DA + 1, 0);
        assert!(matches!(
            kiem_tra(Bytes::from(v)).unwrap_err(),
            ApiLoi::AnhQuaLon(_)
        ));
    }

    #[test]
    fn qua_50_trieu_diem_anh_thi_qua_lon() {
        let b = ma_hoa(
            DynamicImage::ImageLuma8(GrayImage::new(8000, 7000)),
            ImageFormat::Png,
        );
        assert!(b.len() <= BYTE_TOI_DA);
        assert!(matches!(kiem_tra(b).unwrap_err(), ApiLoi::AnhQuaLon(_)));
    }

    #[test]
    fn mime_qua_lai() {
        for k in [KieuAnh::Jpeg, KieuAnh::Png, KieuAnh::Webp] {
            assert_eq!(KieuAnh::tu_mime(k.mime()), Some(k));
        }
        assert_eq!(KieuAnh::tu_mime("image/gif"), None);
    }
}
