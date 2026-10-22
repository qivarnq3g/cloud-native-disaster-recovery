use std::net::SocketAddr;
use std::sync::Arc;
use std::time::Instant;

use axum::extract::{ConnectInfo, State};
use axum::http::{HeaderMap, StatusCode};

use crate::AppState;
use crate::error::{ApiError, ErrorBody};
use crate::secret_code;

#[utoipa::path(
    post,
    path = "/v1/secret-code/verify",
    security(("secret_code" = [])),
    responses((status = 204), (status = 401, body = ErrorBody), (status = 429, body = ErrorBody))
)]
pub async fn verify_secret_code(
    State(state): State<Arc<AppState>>,
    ConnectInfo(peer): ConnectInfo<SocketAddr>,
    headers: HeaderMap,
) -> Result<StatusCode, ApiError> {
    let ip = secret_code::client_ip(peer, &headers, &state.config.trusted_proxies);
    state
        .secret_code
        .check(ip, secret_code::code_from_headers(&headers), Instant::now())?;
    Ok(StatusCode::NO_CONTENT)
}
