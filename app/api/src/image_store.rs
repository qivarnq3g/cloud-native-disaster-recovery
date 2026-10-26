use std::sync::Arc;
use std::time::Duration;

use bytes::Bytes;
use object_store::aws::AmazonS3Builder;
use object_store::azure::MicrosoftAzureBuilder;
use object_store::path::Path;
use object_store::{BackoffConfig, ClientOptions, ObjectStore, PutPayload, RetryConfig};
use uuid::Uuid;

use crate::config::{Config, StoreKind};

#[derive(Clone)]
pub struct ImageStore {
    inner: Arc<dyn ObjectStore>,
}

pub fn network_options() -> (ClientOptions, RetryConfig) {
    let options = ClientOptions::new()
        .with_connect_timeout(Duration::from_secs(3))
        .with_timeout(Duration::from_secs(10));
    let retry = RetryConfig {
        backoff: BackoffConfig::default(),
        max_retries: 2,
        retry_timeout: Duration::from_secs(15),
    };
    (options, retry)
}

fn env_with_prefix(prefix: &'static str) -> impl Iterator<Item = (String, String)> {
    std::env::vars()
        .filter(move |(k, _)| k.starts_with(prefix))
        .map(|(k, v)| (k.to_ascii_lowercase(), v))
}

impl ImageStore {
    pub fn new(inner: Arc<dyn ObjectStore>) -> Self {
        Self { inner }
    }

    pub fn from_config(c: &Config) -> anyhow::Result<Self> {
        let (options, retry) = network_options();
        let inner: Arc<dyn ObjectStore> = match c.store_kind {
            StoreKind::Azure => {
                let mut b = MicrosoftAzureBuilder::new()
                    .with_client_options(options)
                    .with_retry(retry);
                for (k, v) in env_with_prefix("AZURE_") {
                    if let Ok(key) = k.parse() {
                        b = b.with_config(key, v);
                    }
                }
                Arc::new(b.with_container_name(&c.container).build()?)
            }
            StoreKind::S3 => {
                let mut b = AmazonS3Builder::new()
                    .with_client_options(options)
                    .with_retry(retry);
                for (k, v) in env_with_prefix("AWS_") {
                    if let Ok(key) = k.parse() {
                        b = b.with_config(key, v);
                    }
                }
                Arc::new(b.with_bucket_name(&c.container).build()?)
            }
        };
        Ok(Self::new(inner))
    }

    fn original_path(id: Uuid) -> Path {
        Path::from(format!("original/{id}"))
    }

    fn thumbnail_path(id: Uuid) -> Path {
        Path::from(format!("thumbnail/{id}.webp"))
    }

    pub async fn put_original(&self, id: Uuid, data: Bytes) -> object_store::Result<()> {
        self.inner
            .put(&Self::original_path(id), PutPayload::from(data))
            .await
            .map(|_| ())
    }

    pub async fn get_original(&self, id: Uuid) -> object_store::Result<Option<Bytes>> {
        self.get(&Self::original_path(id)).await
    }

    pub async fn put_thumbnail(&self, id: Uuid, data: Bytes) -> object_store::Result<()> {
        self.inner
            .put(&Self::thumbnail_path(id), PutPayload::from(data))
            .await
            .map(|_| ())
    }

    pub async fn get_thumbnail(&self, id: Uuid) -> object_store::Result<Option<Bytes>> {
        self.get(&Self::thumbnail_path(id)).await
    }

    pub async fn delete_thumbnail(&self, id: Uuid) -> object_store::Result<()> {
        match self.inner.delete(&Self::thumbnail_path(id)).await {
            Ok(()) | Err(object_store::Error::NotFound { .. }) => Ok(()),
            Err(e) => Err(e),
        }
    }

    pub async fn probe(&self) -> object_store::Result<()> {
        match self.inner.head(&Path::from("health/missing")).await {
            Ok(_) | Err(object_store::Error::NotFound { .. }) => Ok(()),
            Err(e) => Err(e),
        }
    }

    async fn get(&self, path: &Path) -> object_store::Result<Option<Bytes>> {
        match self.inner.get(path).await {
            Ok(r) => Ok(Some(r.bytes().await?)),
            Err(object_store::Error::NotFound { .. }) => Ok(None),
            Err(e) => Err(e),
        }
    }
}
