use std::net::SocketAddr;
use std::sync::Arc;
use std::time::Instant;

use axum::extract::{ConnectInfo, State};
use axum::http::{HeaderMap, StatusCode};

use crate::TrangThai;
use crate::loi::{ApiLoi, ThanLoi};
use crate::ma_bi_mat;

#[utoipa::path(
    post,
    path = "/v1/ma/kiem-tra",
    security(("ma_bi_mat" = [])),
    responses((status = 204), (status = 401, body = ThanLoi), (status = 429, body = ThanLoi))
)]
pub async fn kiem_tra_ma(
    State(tt): State<Arc<TrangThai>>,
    ConnectInfo(nguon): ConnectInfo<SocketAddr>,
    headers: HeaderMap,
) -> Result<StatusCode, ApiLoi> {
    let ip = ma_bi_mat::ip_khach(nguon, &headers, &tt.cau_hinh.proxy_tin_cay);
    tt.ma
        .kiem_tra(ip, ma_bi_mat::ma_tu_header(&headers), Instant::now())?;
    Ok(StatusCode::NO_CONTENT)
}
