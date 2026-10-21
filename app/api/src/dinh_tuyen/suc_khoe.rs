use std::sync::Arc;
use std::sync::atomic::Ordering;
use std::time::Duration;

use axum::Json;
use axum::extract::State;
use axum::http::{StatusCode, header};
use axum::response::IntoResponse;
use serde::{Deserialize, Serialize};
use utoipa::ToSchema;

use crate::TrangThai;
use crate::cau_hinh::PHIEN_BAN;

#[derive(Debug, Serialize, Deserialize, ToSchema)]
pub struct SucKhoe {
    pub trang_thai: String,
    pub cum: String,
    pub vung: String,
    pub phien_ban: String,
    pub chi_doc: bool,
    #[serde(skip_serializing_if = "Vec::is_empty", default)]
    pub hong: Vec<String>,
}

#[utoipa::path(get, path = "/healthz", responses((status = 200, body = SucKhoe), (status = 503, body = SucKhoe)))]
pub async fn healthz(State(tt): State<Arc<TrangThai>>) -> impl IntoResponse {
    let han = Duration::from_secs(2);
    let (csdl, kho) = tokio::join!(
        tokio::time::timeout(han, sqlx::query("SELECT 1").execute(&tt.pool)),
        tokio::time::timeout(han, tt.kho.tham_do()),
    );
    let mut hong = Vec::new();
    if !tt.da_migrate.load(Ordering::Acquire) || !matches!(csdl, Ok(Ok(_))) {
        hong.push("csdl".to_string());
    }
    if !matches!(kho, Ok(Ok(()))) {
        hong.push("kho_anh".to_string());
    }
    let trang_thai = if hong.is_empty() { StatusCode::OK } else { StatusCode::SERVICE_UNAVAILABLE };
    let than = SucKhoe {
        trang_thai: if hong.is_empty() { "on" } else { "loi" }.to_string(),
        cum: tt.cau_hinh.cum.clone(),
        vung: tt.cau_hinh.vung.clone(),
        phien_ban: PHIEN_BAN.to_string(),
        chi_doc: tt.cau_hinh.chi_doc,
        hong,
    };
    (trang_thai, [(header::CACHE_CONTROL, "no-store")], Json(than))
}

#[utoipa::path(get, path = "/livez", responses((status = 204)))]
pub async fn livez() -> StatusCode {
    StatusCode::NO_CONTENT
}
