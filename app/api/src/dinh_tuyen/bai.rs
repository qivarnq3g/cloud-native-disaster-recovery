use std::sync::Arc;

use axum::Json;
use axum::extract::rejection::{PathRejection, QueryRejection};
use axum::extract::{Path, Query, State};
use axum::http::header;
use axum::response::{IntoResponse, Response};
use bytes::Bytes;
use serde::{Deserialize, Serialize};
use utoipa::{IntoParams, ToSchema};
use uuid::Uuid;

use crate::TrangThai;
use crate::anh::KieuAnh;
use crate::csdl::{self, Bai};
use crate::loi::{ApiLoi, ThanLoi};

#[derive(Debug, Deserialize, IntoParams)]
#[into_params(parameter_in = Query)]
pub struct ThamSoTrang {
    pub truoc: Option<Uuid>,
    pub so: Option<i64>,
}

#[derive(Debug, Serialize, Deserialize, ToSchema)]
pub struct TrangBai {
    pub bai: Vec<Bai>,
    pub tiep: Option<Uuid>,
}

#[utoipa::path(
    get,
    path = "/v1/bai",
    params(ThamSoTrang),
    responses(
        (status = 200, body = TrangBai),
        (status = 422, body = ThanLoi),
        (status = 503, body = ThanLoi)
    )
)]
pub async fn danh_sach(
    State(tt): State<Arc<TrangThai>>,
    q: Result<Query<ThamSoTrang>, QueryRejection>,
) -> Result<Json<TrangBai>, ApiLoi> {
    let Query(q) = q.map_err(|_| ApiLoi::DuLieuSai("Tham số không hợp lệ.".into()))?;
    let so = q.so.unwrap_or(24);
    if !(1..=60).contains(&so) {
        return Err(ApiLoi::DuLieuSai("Số bài mỗi trang phải từ 1 đến 60.".into()));
    }
    let mut ds = csdl::trang(&tt.pool, q.truoc, so + 1).await?;
    let tiep = if ds.len() as i64 > so {
        ds.truncate(so as usize);
        ds.last().map(|b| b.id)
    } else {
        None
    };
    Ok(Json(TrangBai { bai: ds, tiep }))
}

#[utoipa::path(
    get,
    path = "/v1/bai/{id}",
    params(("id" = Uuid, Path)),
    responses((status = 200, body = Bai), (status = 404, body = ThanLoi), (status = 503, body = ThanLoi))
)]
pub async fn mot_bai(
    State(tt): State<Arc<TrangThai>>,
    id: Result<Path<Uuid>, PathRejection>,
) -> Result<Json<Bai>, ApiLoi> {
    Ok(Json(tim(&tt, id).await?))
}

#[utoipa::path(
    get,
    path = "/v1/bai/{id}/anh",
    params(("id" = Uuid, Path)),
    responses((status = 200, description = "Ảnh gốc, kiểu theo anh_kieu"), (status = 404, body = ThanLoi))
)]
pub async fn anh_goc(
    State(tt): State<Arc<TrangThai>>,
    id: Result<Path<Uuid>, PathRejection>,
) -> Result<Response, ApiLoi> {
    let bai = tim(&tt, id).await?;
    let du_lieu = tt.kho.lay_goc(bai.id).await?.ok_or(ApiLoi::KhongTimThay)?;
    Ok(tra_anh(du_lieu, kieu_cua(&bai)?.mime(), bai.anh_sha256))
}

#[utoipa::path(
    get,
    path = "/v1/bai/{id}/anh-nho",
    params(("id" = Uuid, Path)),
    responses((status = 200, description = "Ảnh nhỏ AVIF, hoặc ảnh gốc nếu ảnh đã nhỏ"), (status = 404, body = ThanLoi))
)]
pub async fn anh_nho(
    State(tt): State<Arc<TrangThai>>,
    id: Result<Path<Uuid>, PathRejection>,
) -> Result<Response, ApiLoi> {
    let bai = tim(&tt, id).await?;
    let kieu = kieu_cua(&bai)?;
    let ra = tt.anh_nho.lay(bai.id, kieu, bai.rong as u32, bai.cao as u32).await?;
    Ok(tra_anh(ra.du_lieu, ra.kieu, format!("{}-nho", bai.anh_sha256)))
}

async fn tim(tt: &TrangThai, id: Result<Path<Uuid>, PathRejection>) -> Result<Bai, ApiLoi> {
    let Path(id) = id.map_err(|_| ApiLoi::KhongTimThay)?;
    csdl::lay(&tt.pool, id).await?.ok_or(ApiLoi::KhongTimThay)
}

fn kieu_cua(bai: &Bai) -> Result<KieuAnh, ApiLoi> {
    KieuAnh::tu_mime(&bai.anh_kieu).ok_or(ApiLoi::TamNgung)
}

fn tra_anh(du_lieu: Bytes, kieu: &'static str, etag: String) -> Response {
    (
        [
            (header::CONTENT_TYPE, kieu.to_string()),
            (header::ETAG, format!("\"{etag}\"")),
            (header::CACHE_CONTROL, "public, max-age=31536000, immutable".to_string()),
        ],
        du_lieu,
    )
        .into_response()
}
