use std::collections::HashMap;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Mutex};

use bytes::Bytes;
use fast_image_resize::images::Image;
use fast_image_resize::{FilterType, PixelType, ResizeAlg, ResizeOptions, Resizer};
use lru::LruCache;
use tokio::sync::{OnceCell, Semaphore};
use uuid::Uuid;

use crate::anh::{KieuAnh, giai_ma};
use crate::kho_anh::KhoAnh;
use crate::loi::ApiLoi;

pub const CANH_TOI_DA: u32 = 800;
const BO_NHO_DEM_TOI_DA: usize = 64 * 1024 * 1024;

pub fn can_anh_nho(rong: u32, cao: u32) -> bool {
    rong > CANH_TOI_DA || cao > CANH_TOI_DA
}

pub fn kich_thuoc_nho(rong: u32, cao: u32) -> (u32, u32) {
    let thu_nho = |canh: u32, canh_dai: u32| -> u32 {
        ((u64::from(canh) * u64::from(CANH_TOI_DA) + u64::from(canh_dai) / 2) / u64::from(canh_dai))
            .max(1) as u32
    };
    if rong >= cao {
        (CANH_TOI_DA, thu_nho(cao, rong))
    } else {
        (thu_nho(rong, cao), CANH_TOI_DA)
    }
}

pub fn tao_anh_nho(goc: &[u8], kieu: KieuAnh) -> anyhow::Result<Vec<u8>> {
    let anh = giai_ma(goc, kieu)?.to_rgba8();
    let (rong, cao) = anh.dimensions();
    let (rong_nho, cao_nho) = kich_thuoc_nho(rong, cao);
    let nguon = Image::from_vec_u8(rong, cao, anh.into_raw(), PixelType::U8x4)?;
    let mut dich = Image::new(rong_nho, cao_nho, PixelType::U8x4);
    Resizer::new().resize(
        &nguon,
        &mut dich,
        &ResizeOptions::new().resize_alg(ResizeAlg::Convolution(FilterType::Lanczos3)),
    )?;
    let diem: Vec<ravif::RGBA8> = dich
        .buffer()
        .chunks_exact(4)
        .map(|p| ravif::RGBA8::new(p[0], p[1], p[2], p[3]))
        .collect();
    let ket_qua = ravif::Encoder::new()
        .with_quality(60.0)
        .with_alpha_quality(60.0)
        .with_speed(6)
        .encode_rgba(ravif::Img::new(
            diem.as_slice(),
            rong_nho as usize,
            cao_nho as usize,
        ))?;
    Ok(ket_qua.avif_file)
}

pub struct BoNhoDem {
    ds: LruCache<Uuid, Bytes>,
    tong: usize,
    gioi_han: usize,
}

impl BoNhoDem {
    pub fn moi(gioi_han: usize) -> Self {
        Self {
            ds: LruCache::unbounded(),
            tong: 0,
            gioi_han,
        }
    }

    pub fn lay(&mut self, id: &Uuid) -> Option<Bytes> {
        self.ds.get(id).cloned()
    }

    pub fn dat(&mut self, id: Uuid, du_lieu: Bytes) {
        if du_lieu.len() > self.gioi_han {
            return;
        }
        if let Some(cu) = self.ds.put(id, du_lieu.clone()) {
            self.tong -= cu.len();
        }
        self.tong += du_lieu.len();
        while self.tong > self.gioi_han {
            match self.ds.pop_lru() {
                Some((_, bo)) => self.tong -= bo.len(),
                None => break,
            }
        }
    }

    pub fn tong(&self) -> usize {
        self.tong
    }
}

#[derive(Debug)]
pub struct AnhTraVe {
    pub du_lieu: Bytes,
    pub kieu: &'static str,
}

pub struct DichVuAnhNho {
    kho: KhoAnh,
    chi_doc: bool,
    dem: Mutex<BoNhoDem>,
    dang_tao: Mutex<HashMap<Uuid, Arc<OnceCell<Bytes>>>>,
    mot_luc: Semaphore,
    so_lan_tao: AtomicU64,
}

impl DichVuAnhNho {
    pub fn moi(kho: KhoAnh, chi_doc: bool) -> Self {
        Self {
            kho,
            chi_doc,
            dem: Mutex::new(BoNhoDem::moi(BO_NHO_DEM_TOI_DA)),
            dang_tao: Mutex::new(HashMap::new()),
            mot_luc: Semaphore::new(1),
            so_lan_tao: AtomicU64::new(0),
        }
    }

    pub fn so_lan_tao(&self) -> u64 {
        self.so_lan_tao.load(Ordering::Relaxed)
    }

    pub async fn lay(
        &self,
        id: Uuid,
        kieu_goc: KieuAnh,
        rong: u32,
        cao: u32,
    ) -> Result<AnhTraVe, ApiLoi> {
        if !can_anh_nho(rong, cao) {
            let goc = self.kho.lay_goc(id).await?.ok_or(ApiLoi::KhongTimThay)?;
            return Ok(AnhTraVe {
                du_lieu: goc,
                kieu: kieu_goc.mime(),
            });
        }
        let tu_dem = self.dem.lock().expect("khoa bo nho dem").lay(&id);
        if let Some(b) = tu_dem {
            return Ok(avif(b));
        }
        if let Some(b) = self.kho.lay_nho(id).await? {
            self.dem.lock().expect("khoa bo nho dem").dat(id, b.clone());
            return Ok(avif(b));
        }
        let o = self
            .dang_tao
            .lock()
            .expect("khoa dang tao")
            .entry(id)
            .or_insert_with(|| Arc::new(OnceCell::new()))
            .clone();
        let ket_qua = o.get_or_try_init(|| self.tao(id, kieu_goc)).await.cloned();
        {
            let mut dang_tao = self.dang_tao.lock().expect("khoa dang tao");
            if dang_tao.get(&id).is_some_and(|x| Arc::ptr_eq(x, &o)) {
                dang_tao.remove(&id);
            }
        }
        Ok(avif(ket_qua?))
    }

    async fn tao(&self, id: Uuid, kieu_goc: KieuAnh) -> Result<Bytes, ApiLoi> {
        let _luot = self.mot_luc.acquire().await.map_err(|_| ApiLoi::TamNgung)?;
        let tu_dem = self.dem.lock().expect("khoa bo nho dem").lay(&id);
        if let Some(b) = tu_dem {
            return Ok(b);
        }
        let goc = self.kho.lay_goc(id).await?.ok_or(ApiLoi::KhongTimThay)?;
        let du_lieu = tokio::task::spawn_blocking(move || tao_anh_nho(&goc, kieu_goc))
            .await
            .map_err(|_| ApiLoi::TamNgung)?
            .map_err(|e| {
                tracing::error!(%id, loi = %e, "khong tao duoc anh nho");
                ApiLoi::TamNgung
            })?;
        let du_lieu = Bytes::from(du_lieu);
        self.so_lan_tao.fetch_add(1, Ordering::Relaxed);
        self.dem
            .lock()
            .expect("khoa bo nho dem")
            .dat(id, du_lieu.clone());
        if !self.chi_doc {
            if let Err(e) = self.kho.cat_nho(id, du_lieu.clone()).await {
                tracing::warn!(%id, loi = %e, "khong cat duoc anh nho vao kho");
            }
        }
        Ok(du_lieu)
    }
}

fn avif(du_lieu: Bytes) -> AnhTraVe {
    AnhTraVe {
        du_lieu,
        kieu: "image/avif",
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Cursor;

    use image::{DynamicImage, ImageFormat, RgbImage};
    use object_store::memory::InMemory;

    fn png(rong: u32, cao: u32) -> Bytes {
        let anh = DynamicImage::ImageRgb8(RgbImage::from_fn(rong, cao, |x, y| {
            image::Rgb([(x % 256) as u8, (y % 256) as u8, 40])
        }));
        let mut ra = Cursor::new(Vec::new());
        anh.write_to(&mut ra, ImageFormat::Png).unwrap();
        Bytes::from(ra.into_inner())
    }

    fn kho_trong() -> KhoAnh {
        KhoAnh::moi(Arc::new(InMemory::new()))
    }

    #[test]
    fn tinh_kich_thuoc_giu_ti_le() {
        assert_eq!(kich_thuoc_nho(1600, 1200), (800, 600));
        assert_eq!(kich_thuoc_nho(1200, 1600), (600, 800));
        assert_eq!(kich_thuoc_nho(801, 10), (800, 10));
        assert_eq!(kich_thuoc_nho(5000, 1), (800, 1));
        assert!(!can_anh_nho(800, 800));
        assert!(can_anh_nho(801, 10));
    }

    #[test]
    fn tao_ra_avif() {
        let ra = tao_anh_nho(&png(1200, 900), KieuAnh::Png).unwrap();
        assert_eq!(&ra[4..12], b"ftypavif");
    }

    #[test]
    fn bo_nho_dem_bo_anh_cu_khi_vuot_gioi_han() {
        let mut d = BoNhoDem::moi(10);
        let (a, b) = (Uuid::now_v7(), Uuid::now_v7());
        d.dat(a, Bytes::from_static(b"123456"));
        d.dat(b, Bytes::from_static(b"7890ab"));
        assert_eq!(d.lay(&a), None);
        assert_eq!(d.lay(&b), Some(Bytes::from_static(b"7890ab")));
        assert_eq!(d.tong(), 6);
        d.dat(a, Bytes::from_static(b"qua dai hon gioi han"));
        assert_eq!(d.lay(&a), None);
    }

    #[tokio::test]
    async fn anh_goc_nho_thi_tra_anh_goc_khong_tao() {
        let kho = kho_trong();
        let id = Uuid::now_v7();
        let goc = png(64, 48);
        kho.cat_goc(id, goc.clone()).await.unwrap();
        let dv = DichVuAnhNho::moi(kho.clone(), false);
        let ra = dv.lay(id, KieuAnh::Png, 64, 48).await.unwrap();
        assert_eq!(ra.du_lieu, goc);
        assert_eq!(ra.kieu, "image/png");
        assert_eq!(dv.so_lan_tao(), 0);
        assert_eq!(kho.lay_nho(id).await.unwrap(), None);
    }

    #[tokio::test(flavor = "multi_thread", worker_threads = 4)]
    async fn hai_muoi_yeu_cau_cung_luc_chi_tao_mot_lan() {
        let kho = kho_trong();
        let id = Uuid::now_v7();
        kho.cat_goc(id, png(1200, 900)).await.unwrap();
        let dv = Arc::new(DichVuAnhNho::moi(kho.clone(), false));
        let mut nv = Vec::new();
        for _ in 0..20 {
            let dv = dv.clone();
            nv.push(tokio::spawn(async move {
                dv.lay(id, KieuAnh::Png, 1200, 900).await
            }));
        }
        for n in nv {
            let ra = n.await.unwrap().unwrap();
            assert_eq!(ra.kieu, "image/avif");
        }
        assert_eq!(dv.so_lan_tao(), 1);
        assert!(kho.lay_nho(id).await.unwrap().is_some());
    }

    #[tokio::test]
    async fn chi_doc_thi_khong_cat_vao_kho_nhung_van_dem() {
        let kho = kho_trong();
        let id = Uuid::now_v7();
        kho.cat_goc(id, png(1200, 900)).await.unwrap();
        let dv = DichVuAnhNho::moi(kho.clone(), true);
        dv.lay(id, KieuAnh::Png, 1200, 900).await.unwrap();
        dv.lay(id, KieuAnh::Png, 1200, 900).await.unwrap();
        assert_eq!(dv.so_lan_tao(), 1);
        assert_eq!(kho.lay_nho(id).await.unwrap(), None);
    }

    #[tokio::test]
    async fn mat_anh_nho_thi_lan_xem_sau_tao_lai() {
        let kho = kho_trong();
        let id = Uuid::now_v7();
        kho.cat_goc(id, png(1200, 900)).await.unwrap();
        DichVuAnhNho::moi(kho.clone(), false)
            .lay(id, KieuAnh::Png, 1200, 900)
            .await
            .unwrap();
        kho.xoa_nho(id).await.unwrap();
        let dv_moi = DichVuAnhNho::moi(kho.clone(), false);
        dv_moi.lay(id, KieuAnh::Png, 1200, 900).await.unwrap();
        assert_eq!(dv_moi.so_lan_tao(), 1);
        assert!(kho.lay_nho(id).await.unwrap().is_some());
    }

    #[tokio::test]
    async fn thieu_anh_goc_thi_khong_tim_thay() {
        let dv = DichVuAnhNho::moi(kho_trong(), false);
        assert_eq!(
            dv.lay(Uuid::now_v7(), KieuAnh::Png, 1200, 900)
                .await
                .unwrap_err(),
            ApiLoi::KhongTimThay
        );
    }
}
