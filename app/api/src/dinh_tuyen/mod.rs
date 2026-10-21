pub mod bai;
pub mod suc_khoe;

use std::sync::Arc;
use std::time::Duration;

use axum::extract::DefaultBodyLimit;
use axum::http::{HeaderName, HeaderValue, Method, header};
use axum::routing::get;
use axum::{Json, Router};
use tower_http::cors::{AllowOrigin, CorsLayer};
use tower_http::set_header::SetResponseHeaderLayer;
use tower_http::trace::{DefaultMakeSpan, DefaultOnResponse, TraceLayer};
use tracing::Level;
use utoipa::OpenApi;
use utoipa_axum::router::OpenApiRouter;
use utoipa_axum::routes;

use crate::TrangThai;
use crate::openapi::TaiLieu;

pub const GIOI_HAN_THAN: usize = 1_258_291;

pub fn cac_tuyen() -> OpenApiRouter<Arc<TrangThai>> {
    OpenApiRouter::with_openapi(TaiLieu::openapi())
        .routes(routes!(bai::danh_sach))
        .routes(routes!(bai::mot_bai))
        .routes(routes!(bai::anh_goc))
        .routes(routes!(bai::anh_nho))
        .routes(routes!(suc_khoe::healthz))
        .routes(routes!(suc_khoe::livez))
}

pub fn ung_dung(tt: Arc<TrangThai>) -> Router {
    let (router, api) = cac_tuyen().split_for_parts();
    let nguon: Vec<HeaderValue> = tt.cau_hinh.cors_nguon.iter().filter_map(|s| HeaderValue::from_str(s).ok()).collect();
    let cors = CorsLayer::new()
        .allow_origin(AllowOrigin::list(nguon))
        .allow_methods([Method::GET, Method::POST])
        .allow_headers([header::AUTHORIZATION, header::CONTENT_TYPE])
        .max_age(Duration::from_secs(600));
    router
        .route("/openapi.json", get(move || {
            let api = api.clone();
            async move { Json(api) }
        }))
        .with_state(tt)
        .layer(DefaultBodyLimit::max(GIOI_HAN_THAN))
        .layer(SetResponseHeaderLayer::overriding(
            HeaderName::from_static("x-content-type-options"),
            HeaderValue::from_static("nosniff"),
        ))
        .layer(cors)
        .layer(
            TraceLayer::new_for_http()
                .make_span_with(DefaultMakeSpan::new().level(Level::INFO))
                .on_response(DefaultOnResponse::new().level(Level::INFO)),
        )
}
