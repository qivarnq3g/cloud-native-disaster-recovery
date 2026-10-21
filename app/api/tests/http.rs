mod common;

use api::db::Post;
use common::{
    ALL_STORES, TestStore, dead_pool, dead_store, insert_directly, start, start_without_waiting,
    writable_store,
};
use serde_json::Value;
use sha2::{Digest, Sha256};

#[tokio::test]
async fn lists_gets_post_and_original_image() {
    for kind in ALL_STORES {
        let app = start(writable_store(kind), false).await;
        let b = insert_directly(&app, 64, 48).await;
        let c = reqwest::Client::new();
        let list: Value = c
            .get(format!("{}/v1/posts?limit=60", app.url))
            .send()
            .await
            .unwrap()
            .json()
            .await
            .unwrap();
        assert!(
            list["posts"]
                .as_array()
                .unwrap()
                .iter()
                .any(|x| x["id"] == b.id.to_string()),
            "{kind:?}"
        );
        let fetched: Post = c
            .get(format!("{}/v1/posts/{}", app.url, b.id))
            .send()
            .await
            .unwrap()
            .json()
            .await
            .unwrap();
        assert_eq!(fetched, b);
        let r = c
            .get(format!("{}/v1/posts/{}/image", app.url, b.id))
            .send()
            .await
            .unwrap();
        assert_eq!(r.status(), 200);
        assert_eq!(r.headers()["content-type"], "image/png");
        assert_eq!(
            r.headers()["cache-control"],
            "public, max-age=31536000, immutable"
        );
        assert_eq!(r.headers()["etag"], format!("\"{}\"", b.image_sha256));
        assert_eq!(r.headers()["x-content-type-options"], "nosniff");
        let body = r.bytes().await.unwrap();
        assert_eq!(hex::encode(Sha256::digest(&body)), b.image_sha256);
    }
}

#[tokio::test]
async fn thumbnail_is_avif_for_large_and_original_for_small() {
    let app = start(writable_store(TestStore::Seaweed), false).await;
    let large = insert_directly(&app, 1200, 900).await;
    let small = insert_directly(&app, 64, 48).await;
    let c = reqwest::Client::new();
    let r = c
        .get(format!("{}/v1/posts/{}/thumbnail", app.url, large.id))
        .send()
        .await
        .unwrap();
    assert_eq!(r.headers()["content-type"], "image/avif");
    assert_eq!(
        r.headers()["etag"],
        format!("\"{}-thumbnail\"", large.image_sha256)
    );
    let r = c
        .get(format!("{}/v1/posts/{}/thumbnail", app.url, small.id))
        .send()
        .await
        .unwrap();
    assert_eq!(r.headers()["content-type"], "image/png");
    assert_eq!(
        hex::encode(Sha256::digest(r.bytes().await.unwrap())),
        small.image_sha256
    );
}

#[tokio::test]
async fn bad_params_return_json_error() {
    let app = start(writable_store(TestStore::Seaweed), false).await;
    let c = reqwest::Client::new();
    for (path, status, code) in [
        ("/v1/posts?limit=0", 422, "invalid_input"),
        ("/v1/posts?limit=61", 422, "invalid_input"),
        ("/v1/posts?before=not-a-uuid", 422, "invalid_input"),
        ("/v1/posts/not-a-uuid", 404, "not_found"),
        (
            "/v1/posts/0192f0c0-0000-7000-8000-000000000000",
            404,
            "not_found",
        ),
        (
            "/v1/posts/0192f0c0-0000-7000-8000-000000000000/image",
            404,
            "not_found",
        ),
    ] {
        let r = c.get(format!("{}{path}", app.url)).send().await.unwrap();
        assert_eq!(r.status(), status, "{path}");
        let v: Value = r.json().await.unwrap();
        assert_eq!(v["error"], code, "{path}");
    }
}

#[tokio::test]
async fn healthz_ok_when_database_and_store_respond() {
    for kind in ALL_STORES {
        let app = start(writable_store(kind), false).await;
        let r = reqwest::get(format!("{}/healthz", app.url)).await.unwrap();
        assert_eq!(r.status(), 200, "{kind:?}");
        assert_eq!(r.headers()["cache-control"], "no-store");
        let v: Value = r.json().await.unwrap();
        assert_eq!(v["status"], "ok");
        assert_eq!(v["cluster"], "primary");
        assert_eq!(v["region"], "test");
        assert_eq!(v["read_only"], false);
        assert!(v.get("failing").is_none());
    }
}

#[tokio::test]
async fn healthz_reports_failing_parts_and_livez_stays_up() {
    let app = start_without_waiting(dead_pool(), dead_store(), false).await;
    let started = std::time::Instant::now();
    let r = reqwest::get(format!("{}/healthz", app.url)).await.unwrap();
    assert!(started.elapsed() < std::time::Duration::from_secs(5));
    assert_eq!(r.status(), 503);
    let v: Value = r.json().await.unwrap();
    assert_eq!(v["status"], "error");
    assert_eq!(v["failing"], serde_json::json!(["database", "image_store"]));
    assert_eq!(
        reqwest::get(format!("{}/livez", app.url))
            .await
            .unwrap()
            .status(),
        204
    );
}

#[tokio::test]
async fn cors_allows_only_configured_origins() {
    let app = start(writable_store(TestStore::Seaweed), false).await;
    let c = reqwest::Client::new();
    let allowed = c
        .get(format!("{}/healthz", app.url))
        .header("origin", "http://localhost:4321")
        .send()
        .await
        .unwrap();
    assert_eq!(
        allowed.headers()["access-control-allow-origin"],
        "http://localhost:4321"
    );
    let denied = c
        .get(format!("{}/healthz", app.url))
        .header("origin", "https://la.vn")
        .send()
        .await
        .unwrap();
    assert!(
        denied
            .headers()
            .get("access-control-allow-origin")
            .is_none()
    );
}

#[tokio::test]
async fn starting_before_database_does_not_exit_and_migrates_later() {
    let app = start_without_waiting(dead_pool(), writable_store(TestStore::Seaweed), false).await;
    tokio::time::sleep(std::time::Duration::from_secs(3)).await;
    let v: Value = reqwest::get(format!("{}/healthz", app.url))
        .await
        .unwrap()
        .json()
        .await
        .unwrap();
    assert_eq!(v["failing"], serde_json::json!(["database"]));
    assert!(
        !app.state
            .migrated
            .load(std::sync::atomic::Ordering::Acquire)
    );
    assert_eq!(
        reqwest::get(format!("{}/livez", app.url))
            .await
            .unwrap()
            .status(),
        204
    );
}
