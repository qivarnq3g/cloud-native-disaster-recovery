use std::sync::Arc;
use std::time::Duration;

use bytes::Bytes;
use object_store::aws::AmazonS3Builder;
use object_store::azure::MicrosoftAzureBuilder;
use object_store::path::Path;
use object_store::{BackoffConfig, ClientOptions, ObjectStore, PutPayload, RetryConfig};
use uuid::Uuid;

use crate::cau_hinh::{CauHinh, LoaiKho};

#[derive(Clone)]
pub struct KhoAnh {
    kho: Arc<dyn ObjectStore>,
}

pub fn tuy_chon_mang() -> (ClientOptions, RetryConfig) {
    let tuy_chon = ClientOptions::new()
        .with_connect_timeout(Duration::from_secs(3))
        .with_timeout(Duration::from_secs(10));
    let thu_lai = RetryConfig {
        backoff: BackoffConfig::default(),
        max_retries: 2,
        retry_timeout: Duration::from_secs(15),
    };
    (tuy_chon, thu_lai)
}

fn bien_moi_truong(tien_to: &'static str) -> impl Iterator<Item = (String, String)> {
    std::env::vars().filter(move |(k, _)| k.starts_with(tien_to)).map(|(k, v)| (k.to_ascii_lowercase(), v))
}

impl KhoAnh {
    pub fn moi(kho: Arc<dyn ObjectStore>) -> Self {
        Self { kho }
    }

    pub fn tu_cau_hinh(c: &CauHinh) -> anyhow::Result<Self> {
        let (tuy_chon, thu_lai) = tuy_chon_mang();
        let kho: Arc<dyn ObjectStore> = match c.loai_kho {
            LoaiKho::Azure => {
                let mut b = MicrosoftAzureBuilder::new().with_client_options(tuy_chon).with_retry(thu_lai);
                for (k, v) in bien_moi_truong("AZURE_") {
                    if let Ok(khoa) = k.parse() {
                        b = b.with_config(khoa, v);
                    }
                }
                Arc::new(b.with_container_name(&c.ten_container).build()?)
            }
            LoaiKho::S3 => {
                let mut b = AmazonS3Builder::new().with_client_options(tuy_chon).with_retry(thu_lai);
                for (k, v) in bien_moi_truong("AWS_") {
                    if let Ok(khoa) = k.parse() {
                        b = b.with_config(khoa, v);
                    }
                }
                Arc::new(b.with_bucket_name(&c.ten_container).build()?)
            }
        };
        Ok(Self::moi(kho))
    }

    fn duong_goc(id: Uuid) -> Path {
        Path::from(format!("goc/{id}"))
    }

    fn duong_nho(id: Uuid) -> Path {
        Path::from(format!("nho/{id}.avif"))
    }

    pub async fn cat_goc(&self, id: Uuid, du_lieu: Bytes) -> object_store::Result<()> {
        self.kho.put(&Self::duong_goc(id), PutPayload::from(du_lieu)).await.map(|_| ())
    }

    pub async fn lay_goc(&self, id: Uuid) -> object_store::Result<Option<Bytes>> {
        self.lay(&Self::duong_goc(id)).await
    }

    pub async fn cat_nho(&self, id: Uuid, du_lieu: Bytes) -> object_store::Result<()> {
        self.kho.put(&Self::duong_nho(id), PutPayload::from(du_lieu)).await.map(|_| ())
    }

    pub async fn lay_nho(&self, id: Uuid) -> object_store::Result<Option<Bytes>> {
        self.lay(&Self::duong_nho(id)).await
    }

    pub async fn xoa_nho(&self, id: Uuid) -> object_store::Result<()> {
        match self.kho.delete(&Self::duong_nho(id)).await {
            Ok(()) | Err(object_store::Error::NotFound { .. }) => Ok(()),
            Err(e) => Err(e),
        }
    }

    pub async fn tham_do(&self) -> object_store::Result<()> {
        match self.kho.head(&Path::from("suc-khoe/khong-ton-tai")).await {
            Ok(_) | Err(object_store::Error::NotFound { .. }) => Ok(()),
            Err(e) => Err(e),
        }
    }

    async fn lay(&self, duong: &Path) -> object_store::Result<Option<Bytes>> {
        match self.kho.get(duong).await {
            Ok(r) => Ok(Some(r.bytes().await?)),
            Err(object_store::Error::NotFound { .. }) => Ok(None),
            Err(e) => Err(e),
        }
    }
}
