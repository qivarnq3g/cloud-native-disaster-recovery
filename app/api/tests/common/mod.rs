#![allow(dead_code)]

use std::sync::Arc;

use api::image_store::{ImageStore, network_options};
use object_store::aws::{AmazonS3, AmazonS3Builder};
use object_store::azure::{AzureConfigKey, MicrosoftAzureBuilder};

#[derive(Clone, Copy, Debug)]
pub enum TestStore {
    Azurite,
    Seaweed,
}

pub const ALL_STORES: [TestStore; 2] = [TestStore::Azurite, TestStore::Seaweed];

fn s3(endpoint: &str, id: &str, secret: &str) -> AmazonS3 {
    let (options, retry) = network_options();
    AmazonS3Builder::new()
        .with_client_options(options)
        .with_retry(retry)
        .with_endpoint(endpoint)
        .with_allow_http(true)
        .with_region("us-east-1")
        .with_bucket_name("images")
        .with_access_key_id(id)
        .with_secret_access_key(secret)
        .build()
        .unwrap()
}

pub fn writable_store(kind: TestStore) -> ImageStore {
    match kind {
        TestStore::Azurite => ImageStore::new(Arc::new(
            MicrosoftAzureBuilder::new()
                .with_use_emulator(true)
                .with_container_name("images")
                .build()
                .unwrap(),
        )),
        TestStore::Seaweed => ImageStore::new(Arc::new(s3(
            "http://127.0.0.1:8333",
            "writer",
            "writer-secret",
        ))),
    }
}

pub fn read_only_store(kind: TestStore) -> ImageStore {
    match kind {
        TestStore::Azurite => {
            let sas = std::env::var("AZURITE_READ_SAS")
                .expect("chạy app/dev/setup.sh rồi đặt AZURITE_READ_SAS");
            ImageStore::new(Arc::new(
                MicrosoftAzureBuilder::new()
                    .with_use_emulator(true)
                    .with_container_name("images")
                    .with_config(AzureConfigKey::SasKey, sas)
                    .build()
                    .unwrap(),
            ))
        }
        TestStore::Seaweed => ImageStore::new(Arc::new(s3(
            "http://127.0.0.1:8333",
            "reader",
            "reader-secret",
        ))),
    }
}

pub fn dead_store() -> ImageStore {
    ImageStore::new(Arc::new(s3("http://127.0.0.1:1", "x", "x")))
}

use std::io::Cursor;
use std::net::SocketAddr;

use api::AppState;
use api::config::{Config, StoreKind};
use image::{DynamicImage, ImageFormat, RgbImage};
use sqlx::PgPool;
use sqlx::postgres::PgPoolOptions;
use uuid::Uuid;

pub const TEST_CODE: &str = "test-code-0123456789";

pub struct TestApp {
    pub url: String,
    pub state: Arc<AppState>,
}

pub fn test_config(read_only: bool) -> Config {
    Config {
        database_url: String::new(),
        store_kind: StoreKind::S3,
        container: "images".into(),
        read_only,
        secret_code: TEST_CODE.into(),
        cluster: "primary".into(),
        region: "test".into(),
        cors_origins: vec!["http://localhost:4321".into()],
        trusted_proxies: vec![],
        port: 0,
    }
}

pub async fn test_pool() -> PgPool {
    let url = std::env::var("DATABASE_URL")
        .unwrap_or_else(|_| "postgres://postgres:test@127.0.0.1:5432/dr".into());
    PgPool::connect(&url).await.unwrap()
}

pub fn dead_pool() -> PgPool {
    PgPoolOptions::new()
        .acquire_timeout(std::time::Duration::from_secs(1))
        .connect_lazy("postgres://x:x@127.0.0.1:1/x")
        .unwrap()
}

pub async fn start_without_waiting(pool: PgPool, store: ImageStore, read_only: bool) -> TestApp {
    let state = Arc::new(AppState::new(pool, store, test_config(read_only)));
    api::state::spawn_migrations(state.clone());
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let url = format!("http://{}", listener.local_addr().unwrap());
    let app = api::app(state.clone());
    tokio::spawn(async move {
        axum::serve(
            listener,
            app.into_make_service_with_connect_info::<SocketAddr>(),
        )
        .await
        .unwrap();
    });
    TestApp { url, state }
}

pub async fn start(store: ImageStore, read_only: bool) -> TestApp {
    let app = start_without_waiting(test_pool().await, store, read_only).await;
    while !app
        .state
        .migrated
        .load(std::sync::atomic::Ordering::Acquire)
    {
        tokio::time::sleep(std::time::Duration::from_millis(50)).await;
    }
    app
}

pub fn png(width: u32, height: u32) -> Vec<u8> {
    let image = DynamicImage::ImageRgb8(RgbImage::from_fn(width, height, |x, y| {
        image::Rgb([(x % 256) as u8, (y % 256) as u8, 7])
    }));
    let mut out = Cursor::new(Vec::new());
    image.write_to(&mut out, ImageFormat::Png).unwrap();
    out.into_inner()
}

pub async fn submit_post(
    c: &reqwest::Client,
    url: &str,
    code: &str,
    idempotency_key: Uuid,
    title: &str,
    image: Vec<u8>,
) -> reqwest::Response {
    let form = reqwest::multipart::Form::new()
        .text("idempotency_key", idempotency_key.to_string())
        .text("title", title.to_string())
        .text("description", "mô tả thử")
        .part(
            "image",
            reqwest::multipart::Part::bytes(image).file_name("image.png"),
        );
    c.post(format!("{url}/v1/posts"))
        .bearer_auth(code)
        .multipart(form)
        .send()
        .await
        .unwrap()
}

pub async fn insert_directly(app: &TestApp, width: u32, height: u32) -> api::db::Post {
    let a = api::image_file::validate(bytes::Bytes::from(png(width, height))).unwrap();
    let id = Uuid::now_v7();
    app.state
        .store
        .put_original(id, a.data.clone())
        .await
        .unwrap();
    match api::db::insert(
        &app.state.pool,
        &api::db::NewPost {
            id,
            idempotency_key: Uuid::now_v7(),
            title: "Thử",
            description: "",
            image: &a,
        },
    )
    .await
    .unwrap()
    {
        api::db::InsertOutcome::Created(b) => b,
        api::db::InsertOutcome::Existing(b) => b,
    }
}
