use std::sync::Arc;
use std::sync::atomic::Ordering;
use std::time::Duration;

use axum::Json;
use axum::extract::State;
use axum::http::{StatusCode, header};
use axum::response::IntoResponse;
use serde::{Deserialize, Serialize};
use utoipa::ToSchema;

use crate::AppState;
use crate::config::APP_VERSION;

#[derive(Debug, Serialize, Deserialize, ToSchema)]
pub struct Health {
    pub status: String,
    pub cluster: String,
    pub region: String,
    pub version: String,
    pub read_only: bool,
    #[serde(skip_serializing_if = "Vec::is_empty", default)]
    pub failing: Vec<String>,
}

#[utoipa::path(get, path = "/healthz", responses((status = 200, body = Health), (status = 503, body = Health)))]
pub async fn healthz(State(state): State<Arc<AppState>>) -> impl IntoResponse {
    let timeout = Duration::from_secs(2);
    let (db, store) = tokio::join!(
        tokio::time::timeout(timeout, sqlx::query("SELECT 1").execute(&state.pool)),
        tokio::time::timeout(timeout, state.store.probe()),
    );
    let mut failing = Vec::new();
    if !state.migrated.load(Ordering::Acquire) || !matches!(db, Ok(Ok(_))) {
        failing.push("database".to_string());
    }
    if !matches!(store, Ok(Ok(()))) {
        failing.push("image_store".to_string());
    }
    let status_code = if failing.is_empty() {
        StatusCode::OK
    } else {
        StatusCode::SERVICE_UNAVAILABLE
    };
    let body = Health {
        status: if failing.is_empty() { "ok" } else { "error" }.to_string(),
        cluster: state.config.cluster.clone(),
        region: state.config.region.clone(),
        version: APP_VERSION.to_string(),
        read_only: state.config.read_only,
        failing,
    };
    (
        status_code,
        [(header::CACHE_CONTROL, "no-store")],
        Json(body),
    )
}

#[utoipa::path(get, path = "/livez", responses((status = 204)))]
pub async fn livez() -> StatusCode {
    StatusCode::NO_CONTENT
}
