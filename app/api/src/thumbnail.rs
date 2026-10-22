use std::collections::HashMap;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Mutex};

use bytes::Bytes;
use fast_image_resize::images::Image;
use fast_image_resize::{FilterType, PixelType, ResizeAlg, ResizeOptions, Resizer};
use lru::LruCache;
use tokio::sync::{OnceCell, Semaphore};
use uuid::Uuid;

use crate::error::ApiError;
use crate::image_file::{ImageType, decode};
use crate::image_store::ImageStore;

pub const MAX_EDGE: u32 = 800;
const CACHE_MAX_BYTES: usize = 64 * 1024 * 1024;

pub fn needs_thumbnail(width: u32, height: u32) -> bool {
    width > MAX_EDGE || height > MAX_EDGE
}

pub fn thumbnail_size(width: u32, height: u32) -> (u32, u32) {
    let scale = |edge: u32, long_edge: u32| -> u32 {
        ((u64::from(edge) * u64::from(MAX_EDGE) + u64::from(long_edge) / 2) / u64::from(long_edge))
            .max(1) as u32
    };
    if width >= height {
        (MAX_EDGE, scale(height, width))
    } else {
        (scale(width, height), MAX_EDGE)
    }
}

pub fn make_thumbnail(original: &[u8], kind: ImageType) -> anyhow::Result<Vec<u8>> {
    let image = decode(original, kind)?.to_rgba8();
    let (width, height) = image.dimensions();
    let (thumb_width, thumb_height) = thumbnail_size(width, height);
    let src = Image::from_vec_u8(width, height, image.into_raw(), PixelType::U8x4)?;
    let mut dst = Image::new(thumb_width, thumb_height, PixelType::U8x4);
    Resizer::new().resize(
        &src,
        &mut dst,
        &ResizeOptions::new().resize_alg(ResizeAlg::Convolution(FilterType::Lanczos3)),
    )?;
    let pixels: Vec<ravif::RGBA8> = dst
        .buffer()
        .chunks_exact(4)
        .map(|p| ravif::RGBA8::new(p[0], p[1], p[2], p[3]))
        .collect();
    let encoded = ravif::Encoder::new()
        .with_quality(60.0)
        .with_alpha_quality(60.0)
        .with_speed(6)
        .encode_rgba(ravif::Img::new(
            pixels.as_slice(),
            thumb_width as usize,
            thumb_height as usize,
        ))?;
    Ok(encoded.avif_file)
}

pub struct ThumbnailCache {
    entries: LruCache<Uuid, Bytes>,
    total: usize,
    limit: usize,
}

impl ThumbnailCache {
    pub fn new(limit: usize) -> Self {
        Self {
            entries: LruCache::unbounded(),
            total: 0,
            limit,
        }
    }

    pub fn get(&mut self, id: &Uuid) -> Option<Bytes> {
        self.entries.get(id).cloned()
    }

    pub fn put(&mut self, id: Uuid, data: Bytes) {
        if data.len() > self.limit {
            return;
        }
        if let Some(old) = self.entries.put(id, data.clone()) {
            self.total -= old.len();
        }
        self.total += data.len();
        while self.total > self.limit {
            match self.entries.pop_lru() {
                Some((_, evicted)) => self.total -= evicted.len(),
                None => break,
            }
        }
    }

    pub fn total(&self) -> usize {
        self.total
    }
}

#[derive(Debug)]
pub struct ServedImage {
    pub data: Bytes,
    pub content_type: &'static str,
}

pub struct ThumbnailService {
    store: ImageStore,
    read_only: bool,
    cache: Mutex<ThumbnailCache>,
    in_flight: Mutex<HashMap<Uuid, Arc<OnceCell<Bytes>>>>,
    one_at_a_time: Semaphore,
    generated: AtomicU64,
}

impl ThumbnailService {
    pub fn new(store: ImageStore, read_only: bool) -> Self {
        Self {
            store,
            read_only,
            cache: Mutex::new(ThumbnailCache::new(CACHE_MAX_BYTES)),
            in_flight: Mutex::new(HashMap::new()),
            one_at_a_time: Semaphore::new(1),
            generated: AtomicU64::new(0),
        }
    }

    pub fn generated_count(&self) -> u64 {
        self.generated.load(Ordering::Relaxed)
    }

    pub async fn get(
        &self,
        id: Uuid,
        original_kind: ImageType,
        width: u32,
        height: u32,
    ) -> Result<ServedImage, ApiError> {
        if !needs_thumbnail(width, height) {
            let original = self
                .store
                .get_original(id)
                .await?
                .ok_or(ApiError::NotFound)?;
            return Ok(ServedImage {
                data: original,
                content_type: original_kind.mime(),
            });
        }
        let cached = self.cache.lock().expect("thumbnail cache lock").get(&id);
        if let Some(b) = cached {
            return Ok(avif(b));
        }
        if let Some(b) = self.store.get_thumbnail(id).await? {
            self.cache
                .lock()
                .expect("thumbnail cache lock")
                .put(id, b.clone());
            return Ok(avif(b));
        }
        let cell = self
            .in_flight
            .lock()
            .expect("in-flight map lock")
            .entry(id)
            .or_insert_with(|| Arc::new(OnceCell::new()))
            .clone();
        let result = cell
            .get_or_try_init(|| self.generate(id, original_kind))
            .await
            .cloned();
        {
            let mut in_flight = self.in_flight.lock().expect("in-flight map lock");
            if in_flight.get(&id).is_some_and(|x| Arc::ptr_eq(x, &cell)) {
                in_flight.remove(&id);
            }
        }
        Ok(avif(result?))
    }

    async fn generate(&self, id: Uuid, original_kind: ImageType) -> Result<Bytes, ApiError> {
        let _permit = self
            .one_at_a_time
            .acquire()
            .await
            .map_err(|_| ApiError::Unavailable)?;
        let cached = self.cache.lock().expect("thumbnail cache lock").get(&id);
        if let Some(b) = cached {
            return Ok(b);
        }
        let original = self
            .store
            .get_original(id)
            .await?
            .ok_or(ApiError::NotFound)?;
        let data = tokio::task::spawn_blocking(move || make_thumbnail(&original, original_kind))
            .await
            .map_err(|_| ApiError::Unavailable)?
            .map_err(|e| {
                tracing::error!(%id, error = %e, "failed to generate thumbnail");
                ApiError::Unavailable
            })?;
        let data = Bytes::from(data);
        self.generated.fetch_add(1, Ordering::Relaxed);
        self.cache
            .lock()
            .expect("thumbnail cache lock")
            .put(id, data.clone());
        if !self.read_only
            && let Err(e) = self.store.put_thumbnail(id, data.clone()).await
        {
            tracing::warn!(%id, error = %e, "failed to store thumbnail");
        }
        Ok(data)
    }
}

fn avif(data: Bytes) -> ServedImage {
    ServedImage {
        data,
        content_type: "image/avif",
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Cursor;

    use image::{DynamicImage, ImageFormat, RgbImage};
    use object_store::memory::InMemory;

    fn png(width: u32, height: u32) -> Bytes {
        let image = DynamicImage::ImageRgb8(RgbImage::from_fn(width, height, |x, y| {
            image::Rgb([(x % 256) as u8, (y % 256) as u8, 40])
        }));
        let mut out = Cursor::new(Vec::new());
        image.write_to(&mut out, ImageFormat::Png).unwrap();
        Bytes::from(out.into_inner())
    }

    fn empty_store() -> ImageStore {
        ImageStore::new(Arc::new(InMemory::new()))
    }

    #[test]
    fn size_keeps_aspect_ratio() {
        assert_eq!(thumbnail_size(1600, 1200), (800, 600));
        assert_eq!(thumbnail_size(1200, 1600), (600, 800));
        assert_eq!(thumbnail_size(801, 10), (800, 10));
        assert_eq!(thumbnail_size(5000, 1), (800, 1));
        assert!(!needs_thumbnail(800, 800));
        assert!(needs_thumbnail(801, 10));
    }

    #[test]
    fn produces_avif() {
        let out = make_thumbnail(&png(1200, 900), ImageType::Png).unwrap();
        assert_eq!(&out[4..12], b"ftypavif");
    }

    #[test]
    fn cache_evicts_oldest_when_over_limit() {
        let mut d = ThumbnailCache::new(10);
        let (a, b) = (Uuid::now_v7(), Uuid::now_v7());
        d.put(a, Bytes::from_static(b"123456"));
        d.put(b, Bytes::from_static(b"7890ab"));
        assert_eq!(d.get(&a), None);
        assert_eq!(d.get(&b), Some(Bytes::from_static(b"7890ab")));
        assert_eq!(d.total(), 6);
        d.put(a, Bytes::from_static(b"exceeds the limit"));
        assert_eq!(d.get(&a), None);
    }

    #[tokio::test]
    async fn small_original_is_served_without_generating() {
        let store = empty_store();
        let id = Uuid::now_v7();
        let original = png(64, 48);
        store.put_original(id, original.clone()).await.unwrap();
        let service = ThumbnailService::new(store.clone(), false);
        let out = service.get(id, ImageType::Png, 64, 48).await.unwrap();
        assert_eq!(out.data, original);
        assert_eq!(out.content_type, "image/png");
        assert_eq!(service.generated_count(), 0);
        assert_eq!(store.get_thumbnail(id).await.unwrap(), None);
    }

    #[tokio::test(flavor = "multi_thread", worker_threads = 4)]
    async fn twenty_concurrent_requests_generate_once() {
        let store = empty_store();
        let id = Uuid::now_v7();
        store.put_original(id, png(1200, 900)).await.unwrap();
        let service = Arc::new(ThumbnailService::new(store.clone(), false));
        let mut tasks = Vec::new();
        for _ in 0..20 {
            let service = service.clone();
            tasks.push(tokio::spawn(async move {
                service.get(id, ImageType::Png, 1200, 900).await
            }));
        }
        for n in tasks {
            let out = n.await.unwrap().unwrap();
            assert_eq!(out.content_type, "image/avif");
        }
        assert_eq!(service.generated_count(), 1);
        assert!(store.get_thumbnail(id).await.unwrap().is_some());
    }

    #[tokio::test]
    async fn read_only_caches_but_does_not_store() {
        let store = empty_store();
        let id = Uuid::now_v7();
        store.put_original(id, png(1200, 900)).await.unwrap();
        let service = ThumbnailService::new(store.clone(), true);
        service.get(id, ImageType::Png, 1200, 900).await.unwrap();
        service.get(id, ImageType::Png, 1200, 900).await.unwrap();
        assert_eq!(service.generated_count(), 1);
        assert_eq!(store.get_thumbnail(id).await.unwrap(), None);
    }

    #[tokio::test]
    async fn lost_thumbnail_is_regenerated_on_next_view() {
        let store = empty_store();
        let id = Uuid::now_v7();
        store.put_original(id, png(1200, 900)).await.unwrap();
        ThumbnailService::new(store.clone(), false)
            .get(id, ImageType::Png, 1200, 900)
            .await
            .unwrap();
        store.delete_thumbnail(id).await.unwrap();
        let fresh_service = ThumbnailService::new(store.clone(), false);
        fresh_service
            .get(id, ImageType::Png, 1200, 900)
            .await
            .unwrap();
        assert_eq!(fresh_service.generated_count(), 1);
        assert!(store.get_thumbnail(id).await.unwrap().is_some());
    }

    #[tokio::test]
    async fn missing_original_is_not_found() {
        let service = ThumbnailService::new(empty_store(), false);
        assert_eq!(
            service
                .get(Uuid::now_v7(), ImageType::Png, 1200, 900)
                .await
                .unwrap_err(),
            ApiError::NotFound
        );
    }
}
