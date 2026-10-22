mod common;

use common::{TestStore, start, writable_store};
use serde_json::Value;

#[tokio::test]
async fn served_openapi_matches_committed_file() {
    let app = start(writable_store(TestStore::Seaweed), false).await;
    let served: Value = reqwest::get(format!("{}/openapi.json", app.url))
        .await
        .unwrap()
        .json()
        .await
        .unwrap();
    let file: Value = serde_json::from_str(
        &std::fs::read_to_string(concat!(env!("CARGO_MANIFEST_DIR"), "/openapi.json")).unwrap(),
    )
    .unwrap();
    let generated = serde_json::to_value(api::openapi::spec()).unwrap();
    assert_eq!(served, generated);
    assert_eq!(
        served, file,
        "chạy lại: cargo run -- --print-openapi > openapi.json"
    );
}
