mod chung;

use chung::{LoaiKhoThu, chay, kho_ghi};
use serde_json::Value;

#[tokio::test]
async fn openapi_phuc_vu_khop_tep_da_commit() {
    let app = chay(kho_ghi(LoaiKhoThu::Seaweed), false).await;
    let phuc_vu: Value = reqwest::get(format!("{}/openapi.json", app.url))
        .await
        .unwrap()
        .json()
        .await
        .unwrap();
    let tep: Value = serde_json::from_str(
        &std::fs::read_to_string(concat!(env!("CARGO_MANIFEST_DIR"), "/openapi.json")).unwrap(),
    )
    .unwrap();
    let sinh = serde_json::to_value(api::openapi::tai_lieu()).unwrap();
    assert_eq!(phuc_vu, sinh);
    assert_eq!(
        phuc_vu, tep,
        "chạy lại: cargo run -- --in-openapi > openapi.json"
    );
}
