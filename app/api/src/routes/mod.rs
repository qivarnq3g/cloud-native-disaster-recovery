pub mod health;
pub mod posts;
pub mod secret_code;

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

use crate::AppState;
use crate::openapi::ApiDoc;

pub const BODY_LIMIT: usize = 1_258_291;

pub fn api_router() -> OpenApiRouter<Arc<AppState>> {
    OpenApiRouter::with_openapi(ApiDoc::openapi())
        .routes(routes!(posts::list_posts, posts::create_post))
        .routes(routes!(posts::get_post))
        .routes(routes!(posts::get_post_image))
        .routes(routes!(posts::get_post_thumbnail))
        .routes(routes!(secret_code::verify_secret_code))
        .routes(routes!(health::healthz))
        .routes(routes!(health::livez))
}

pub fn app(state: Arc<AppState>) -> Router {
    let (router, api) = api_router().split_for_parts();
    let origins: Vec<HeaderValue> = state
        .config
        .cors_origins
        .iter()
        .filter_map(|s| HeaderValue::from_str(s).ok())
        .collect();
    let cors = CorsLayer::new()
        .allow_origin(AllowOrigin::list(origins))
        .allow_methods([Method::GET, Method::POST])
        .allow_headers([header::AUTHORIZATION, header::CONTENT_TYPE])
        .max_age(Duration::from_secs(600));
    router
        .route(
            "/openapi.json",
            get(move || {
                let api = api.clone();
                async move { Json(api) }
            }),
        )
        .with_state(state)
        .layer(DefaultBodyLimit::max(BODY_LIMIT))
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
