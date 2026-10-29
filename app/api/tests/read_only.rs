mod common;

use common::{
    ALL_STORES, TEST_CODE, TestStore, dead_store, insert_directly, png, read_only_store, start,
    start_without_waiting, submit_post, writable_store,
};
use serde_json::Value;
use sqlx::Executor;
use sqlx::postgres::PgPoolOptions;
use uuid::Uuid;

#[tokio::test]
async fn read_only_serves_thumbnails_writes_nothing_and_rejects_posts() {
    for kind in ALL_STORES {
        let writer = start(writable_store(kind), false).await;
        let b = insert_directly(&writer, 1200, 900).await;
        let reader = start(read_only_store(kind), true).await;
        let c = reqwest::Client::new();
        let r = c
            .get(format!("{}/v1/posts/{}/thumbnail", reader.url, b.id))
            .send()
            .await
            .unwrap();
        assert_eq!(r.status(), 200, "{kind:?}");
        assert_eq!(r.headers()["content-type"], "image/webp");
        assert_eq!(
            writable_store(kind).get_thumbnail(b.id).await.unwrap(),
            None,
            "{kind:?}"
        );
        let r = submit_post(
            &c,
            &reader.url,
            TEST_CODE,
            Uuid::now_v7(),
            "Không được",
            png(8, 8),
        )
        .await;
        assert_eq!(r.status(), 503);
        assert_eq!(r.json::<Value>().await.unwrap()["error"], "read_only");
        let v: Value = c
            .get(format!("{}/healthz", reader.url))
            .send()
            .await
            .unwrap()
            .json()
            .await
            .unwrap();
        assert_eq!(v["status"], "ok", "{kind:?}");
        assert_eq!(v["read_only"], true);
    }
}

#[tokio::test]
async fn read_only_credentials_without_read_only_mode_still_serve() {
    for kind in ALL_STORES {
        let writer = start(writable_store(kind), false).await;
        let b = insert_directly(&writer, 1200, 900).await;
        let misconfigured = start(read_only_store(kind), false).await;
        let r = reqwest::get(format!("{}/v1/posts/{}/thumbnail", misconfigured.url, b.id))
            .await
            .unwrap();
        assert_eq!(r.status(), 200, "{kind:?}");
        assert_eq!(
            writable_store(kind).get_thumbnail(b.id).await.unwrap(),
            None,
            "{kind:?}"
        );
    }
}

#[tokio::test]
async fn dead_store_on_create_returns_unavailable_and_leaves_no_post() {
    let app = start(dead_store(), false).await;
    let c = reqwest::Client::new();
    let key = Uuid::now_v7();
    let started = std::time::Instant::now();
    let r = submit_post(&c, &app.url, TEST_CODE, key, "Kho chết", png(8, 8)).await;
    assert!(started.elapsed() < std::time::Duration::from_secs(30));
    assert_eq!(r.status(), 503);
    assert_eq!(r.json::<Value>().await.unwrap()["error"], "unavailable");
    let count: i64 = sqlx::query_scalar("SELECT count(*) FROM posts WHERE idempotency_key = $1")
        .bind(key)
        .fetch_one(&app.state.pool)
        .await
        .unwrap();
    assert_eq!(count, 0);
}

#[tokio::test]
async fn read_only_mode_becomes_ready_on_a_read_only_database() {
    start(writable_store(TestStore::Seaweed), false).await;
    let url = std::env::var("DATABASE_URL")
        .unwrap_or_else(|_| "postgres://postgres:test@127.0.0.1:5432/dr".into());
    let replica_like = PgPoolOptions::new()
        .after_connect(|conn, _| {
            Box::pin(async move {
                conn.execute("SET default_transaction_read_only = on")
                    .await
                    .map(|_| ())
            })
        })
        .connect_lazy(&url)
        .unwrap();
    let reader =
        start_without_waiting(replica_like, read_only_store(TestStore::Seaweed), true).await;
    let deadline = std::time::Instant::now() + std::time::Duration::from_secs(15);
    let status = loop {
        let status = reqwest::get(format!("{}/healthz", reader.url))
            .await
            .unwrap()
            .status();
        if status == 200 || std::time::Instant::now() > deadline {
            break status;
        }
        tokio::time::sleep(std::time::Duration::from_millis(200)).await;
    };
    assert_eq!(status, 200);
}
