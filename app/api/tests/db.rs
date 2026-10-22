use std::io::Cursor;

use api::db::{InsertOutcome, NewPost, find_by_idempotency_key, get, insert, page};
use api::image_file::{ValidImage, validate};
use bytes::Bytes;
use image::{DynamicImage, ImageFormat, RgbImage};
use sqlx::PgPool;
use uuid::Uuid;

async fn pool() -> PgPool {
    let url = std::env::var("DATABASE_URL")
        .unwrap_or_else(|_| "postgres://postgres:test@127.0.0.1:5432/dr".into());
    let pool = PgPool::connect(&url).await.unwrap();
    sqlx::migrate!().run(&pool).await.unwrap();
    pool
}

fn image() -> ValidImage {
    let mut out = Cursor::new(Vec::new());
    DynamicImage::ImageRgb8(RgbImage::new(32, 24))
        .write_to(&mut out, ImageFormat::Png)
        .unwrap();
    validate(Bytes::from(out.into_inner())).unwrap()
}

#[tokio::test]
async fn insert_then_get_returns_same_fields() {
    let pool = pool().await;
    let a = image();
    let (id, key) = (Uuid::now_v7(), Uuid::now_v7());
    let InsertOutcome::Created(b) = insert(
        &pool,
        &NewPost {
            id,
            idempotency_key: key,
            title: "Tiêu đề",
            description: "Mô tả",
            image: &a,
        },
    )
    .await
    .unwrap() else {
        panic!("phải là bài mới");
    };
    assert_eq!(b.id, id);
    assert_eq!(b.image_sha256, hex::encode(a.sha256));
    assert_eq!(
        (b.width, b.height, b.image_bytes),
        (32, 24, a.data.len() as i32)
    );
    assert_eq!(b.image_type, "image/png");
    assert_eq!(get(&pool, id).await.unwrap(), Some(b.clone()));
    assert_eq!(find_by_idempotency_key(&pool, key).await.unwrap(), Some(b));
    assert_eq!(get(&pool, Uuid::now_v7()).await.unwrap(), None);
}

#[tokio::test]
async fn duplicate_idempotency_key_returns_existing_post() {
    let pool = pool().await;
    let a = image();
    let key = Uuid::now_v7();
    let first_id = Uuid::now_v7();
    insert(
        &pool,
        &NewPost {
            id: first_id,
            idempotency_key: key,
            title: "Một",
            description: "",
            image: &a,
        },
    )
    .await
    .unwrap();
    match insert(
        &pool,
        &NewPost {
            id: Uuid::now_v7(),
            idempotency_key: key,
            title: "Hai",
            description: "",
            image: &a,
        },
    )
    .await
    .unwrap()
    {
        InsertOutcome::Existing(b) => assert_eq!((b.id, b.title.as_str()), (first_id, "Một")),
        InsertOutcome::Created(_) => panic!("không được tạo bài thứ hai"),
    }
}

#[tokio::test]
async fn pages_newest_first_by_cursor() {
    let pool = pool().await;
    let a = image();
    let mut ids = Vec::new();
    for i in 0..5 {
        let id = Uuid::now_v7();
        insert(
            &pool,
            &NewPost {
                id,
                idempotency_key: Uuid::now_v7(),
                title: &format!("Trang {i}"),
                description: "",
                image: &a,
            },
        )
        .await
        .unwrap();
        ids.push(id);
    }
    let after_last = Uuid::now_v7();
    let mut seen = Vec::new();
    let mut cursor = Some(after_last);
    while seen.len() < 5 {
        let batch = page(&pool, cursor, 2).await.unwrap();
        assert!(!batch.is_empty());
        assert!(batch.windows(2).all(|w| w[0].id > w[1].id));
        cursor = batch.last().map(|b| b.id);
        seen.extend(
            batch
                .into_iter()
                .map(|b| b.id)
                .filter(|id| ids.contains(id)),
        );
    }
    ids.reverse();
    assert_eq!(seen, ids);
}
