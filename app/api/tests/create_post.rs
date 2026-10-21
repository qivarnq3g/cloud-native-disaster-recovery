mod common;

use api::db::Post;
use common::{ALL_STORES, TEST_CODE, TestStore, png, start, submit_post, writable_store};
use serde_json::Value;
use sha2::{Digest, Sha256};
use uuid::Uuid;

#[tokio::test]
async fn create_then_get_image_matches_sha256() {
    for kind in ALL_STORES {
        let app = start(writable_store(kind), false).await;
        let c = reqwest::Client::new();
        let image = png(64, 48);
        let r = submit_post(
            &c,
            &app.url,
            TEST_CODE,
            Uuid::now_v7(),
            "  Bài   thử ",
            image.clone(),
        )
        .await;
        assert_eq!(r.status(), 201, "{kind:?}");
        let b: Post = r.json().await.unwrap();
        assert_eq!(b.title, "Bài   thử");
        assert_eq!(b.image_sha256, hex::encode(Sha256::digest(&image)));
        let body = c
            .get(format!("{}/v1/posts/{}/image", app.url, b.id))
            .send()
            .await
            .unwrap()
            .bytes()
            .await
            .unwrap();
        assert_eq!(body.as_ref(), image.as_slice());
    }
}

#[tokio::test]
async fn resubmitting_same_key_even_concurrently_creates_one_post() {
    let app = start(writable_store(TestStore::Seaweed), false).await;
    let c = reqwest::Client::new();
    let key = Uuid::now_v7();
    let (a, b) = tokio::join!(
        submit_post(&c, &app.url, TEST_CODE, key, "Song song", png(64, 48)),
        submit_post(&c, &app.url, TEST_CODE, key, "Song song", png(64, 48))
    );
    let mut statuses = vec![a.status().as_u16(), b.status().as_u16()];
    statuses.sort();
    assert_eq!(statuses, vec![200, 201]);
    let third = submit_post(&c, &app.url, TEST_CODE, key, "Khác", png(64, 48)).await;
    assert_eq!(third.status(), 200);
    let count: i64 = sqlx::query_scalar("SELECT count(*) FROM posts WHERE idempotency_key = $1")
        .bind(key)
        .fetch_one(&app.state.pool)
        .await
        .unwrap();
    assert_eq!(count, 1);
}

#[tokio::test]
async fn bad_input_returns_right_error_code() {
    let app = start(writable_store(TestStore::Seaweed), false).await;
    let c = reqwest::Client::new();
    let mut too_large = b"\x89PNG\r\n\x1a\n".to_vec();
    too_large.resize(1_048_577, 0);
    for (code, title, image, status, error) in [
        (
            "wrong-code-0123456789",
            "Ok",
            png(8, 8),
            401,
            "invalid_code",
        ),
        (
            TEST_CODE,
            "Ok",
            "không phải ảnh".as_bytes().to_vec(),
            415,
            "not_an_image",
        ),
        (TEST_CODE, "Ok", too_large, 413, "image_too_large"),
        (TEST_CODE, &"a".repeat(101), png(8, 8), 422, "invalid_input"),
    ] {
        let r = submit_post(&c, &app.url, code, Uuid::now_v7(), title, image).await;
        assert_eq!(r.status(), status, "{error}");
        let v: Value = r.json().await.unwrap();
        assert_eq!(v["error"], error);
    }
}

#[tokio::test]
async fn checks_code_and_blocks_after_ten_failures() {
    let app = start(writable_store(TestStore::Seaweed), false).await;
    let c = reqwest::Client::new();
    let url = format!("{}/v1/secret-code/verify", app.url);
    assert_eq!(
        c.post(&url)
            .bearer_auth(TEST_CODE)
            .send()
            .await
            .unwrap()
            .status(),
        204
    );
    for _ in 0..10 {
        assert_eq!(
            c.post(&url)
                .bearer_auth("wrong")
                .send()
                .await
                .unwrap()
                .status(),
            401
        );
    }
    let r = c.post(&url).bearer_auth(TEST_CODE).send().await.unwrap();
    assert_eq!(r.status(), 429);
    assert!(r.headers().contains_key("retry-after"));
}
