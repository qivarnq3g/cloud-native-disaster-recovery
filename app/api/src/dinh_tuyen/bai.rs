use std::net::SocketAddr;
use std::sync::Arc;
use std::time::Instant;

use axum::Json;
use axum::extract::multipart::{Multipart, MultipartError, MultipartRejection};
use axum::extract::rejection::{PathRejection, QueryRejection};
use axum::extract::{ConnectInfo, Path, Query, State};
use axum::http::{HeaderMap, StatusCode, header};
use axum::response::{IntoResponse, Response};
use bytes::Bytes;
use serde::{Deserialize, Serialize};
use utoipa::{IntoParams, ToSchema};
use uuid::Uuid;

use crate::TrangThai;
use crate::anh::{self, KieuAnh};
use crate::csdl::{self, Bai, BaiMoi, KetQuaThem};
use crate::loi::{ApiLoi, ThanLoi};
use crate::{ma_bi_mat, van_ban};

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
        return Err(ApiLoi::DuLieuSai(
            "Số bài mỗi trang phải từ 1 đến 60.".into(),
        ));
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
    let ra = tt
        .anh_nho
        .lay(bai.id, kieu, bai.rong as u32, bai.cao as u32)
        .await?;
    Ok(tra_anh(
        ra.du_lieu,
        ra.kieu,
        format!("{}-nho", bai.anh_sha256),
    ))
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
            (
                header::CACHE_CONTROL,
                "public, max-age=31536000, immutable".to_string(),
            ),
        ],
        du_lieu,
    )
        .into_response()
}

#[derive(ToSchema)]
#[allow(dead_code)]
pub struct FormDangBai {
    ma_lan_dang: Uuid,
    tieu_de: String,
    mo_ta: String,
    #[schema(value_type = String, format = Binary)]
    anh: Vec<u8>,
}

struct Form {
    ma_lan_dang: Uuid,
    tieu_de: String,
    mo_ta: String,
    anh: Bytes,
}

#[utoipa::path(
    post,
    path = "/v1/bai",
    request_body(content = FormDangBai, content_type = "multipart/form-data"),
    security(("ma_bi_mat" = [])),
    responses(
        (status = 201, body = Bai),
        (status = 200, body = Bai),
        (status = 401, body = ThanLoi),
        (status = 413, body = ThanLoi),
        (status = 415, body = ThanLoi),
        (status = 422, body = ThanLoi),
        (status = 429, body = ThanLoi),
        (status = 503, body = ThanLoi)
    )
)]
pub async fn dang_bai(
    State(tt): State<Arc<TrangThai>>,
    ConnectInfo(nguon): ConnectInfo<SocketAddr>,
    headers: HeaderMap,
    multipart: Result<Multipart, MultipartRejection>,
) -> Result<(StatusCode, Json<Bai>), ApiLoi> {
    if tt.cau_hinh.chi_doc {
        return Err(ApiLoi::ChiDoc);
    }
    let ip = ma_bi_mat::ip_khach(nguon, &headers, &tt.cau_hinh.proxy_tin_cay);
    tt.ma
        .kiem_tra(ip, ma_bi_mat::ma_tu_header(&headers), Instant::now())?;
    let multipart =
        multipart.map_err(|_| ApiLoi::DuLieuSai("Cần gửi multipart/form-data.".into()))?;
    let form = doc_form(multipart).await?;
    if let Some(cu) = csdl::tim_theo_ma_lan_dang(&tt.pool, form.ma_lan_dang).await? {
        return Ok((StatusCode::OK, Json(cu)));
    }
    let tieu_de = van_ban::tieu_de(&form.tieu_de)?;
    let mo_ta = van_ban::mo_ta(&form.mo_ta)?;
    let anh_hop_le = tokio::task::spawn_blocking(move || anh::kiem_tra(form.anh))
        .await
        .map_err(|_| ApiLoi::TamNgung)??;
    let id = Uuid::now_v7();
    tt.kho.cat_goc(id, anh_hop_le.du_lieu.clone()).await?;
    let moi = BaiMoi {
        id,
        ma_lan_dang: form.ma_lan_dang,
        tieu_de: &tieu_de,
        mo_ta: &mo_ta,
        anh: &anh_hop_le,
    };
    match csdl::them(&tt.pool, &moi).await? {
        KetQuaThem::Moi(b) => Ok((StatusCode::CREATED, Json(b))),
        KetQuaThem::DaCo(b) => Ok((StatusCode::OK, Json(b))),
    }
}

async fn doc_form(mut m: Multipart) -> Result<Form, ApiLoi> {
    let (mut ma, mut tieu_de, mut mo_ta, mut anh) = (None, None, None, None);
    while let Some(truong) = m.next_field().await.map_err(loi_multipart)? {
        match truong.name() {
            Some("ma_lan_dang") => ma = Some(truong.text().await.map_err(loi_multipart)?),
            Some("tieu_de") => tieu_de = Some(truong.text().await.map_err(loi_multipart)?),
            Some("mo_ta") => mo_ta = Some(truong.text().await.map_err(loi_multipart)?),
            Some("anh") => anh = Some(truong.bytes().await.map_err(loi_multipart)?),
            _ => {}
        }
    }
    let ma_lan_dang = ma
        .as_deref()
        .and_then(|s| Uuid::parse_str(s.trim()).ok())
        .ok_or_else(|| ApiLoi::DuLieuSai("Thiếu hoặc sai ma_lan_dang.".into()))?;
    Ok(Form {
        ma_lan_dang,
        tieu_de: tieu_de.ok_or_else(|| ApiLoi::DuLieuSai("Thiếu tiêu đề.".into()))?,
        mo_ta: mo_ta.unwrap_or_default(),
        anh: anh.ok_or_else(|| ApiLoi::DuLieuSai("Thiếu ảnh.".into()))?,
    })
}

fn loi_multipart(e: MultipartError) -> ApiLoi {
    if e.status() == StatusCode::PAYLOAD_TOO_LARGE {
        ApiLoi::AnhQuaLon("Ảnh lớn hơn 1 MB.")
    } else {
        ApiLoi::DuLieuSai("Dữ liệu gửi lên không đọc được.".into())
    }
}
