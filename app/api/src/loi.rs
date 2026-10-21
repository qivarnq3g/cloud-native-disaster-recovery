use axum::Json;
use axum::http::{HeaderValue, StatusCode, header};
use axum::response::{IntoResponse, Response};
use serde::{Deserialize, Serialize};
use utoipa::ToSchema;

#[derive(Debug, Clone, PartialEq, Eq, thiserror::Error)]
pub enum ApiLoi {
    #[error("Mã bí mật không đúng.")]
    MaSai,
    #[error("Không tìm thấy.")]
    KhongTimThay,
    #[error("{0}")]
    AnhQuaLon(&'static str),
    #[error("Tệp không phải ảnh JPG, PNG hoặc WebP đọc được.")]
    KhongPhaiAnh,
    #[error("{0}")]
    DuLieuSai(String),
    #[error("Thử sai quá nhiều lần. Thử lại sau {0} giây.")]
    ThuQuaNhieu(u64),
    #[error("Hệ thống tạm ngừng, thử lại sau.")]
    TamNgung,
    #[error("Hệ thống đang ở chế độ chỉ đọc.")]
    ChiDoc,
}

#[derive(Debug, Serialize, Deserialize, ToSchema)]
pub struct ThanLoi {
    pub loi: String,
    pub thong_bao: String,
}

impl ApiLoi {
    pub fn ma(&self) -> &'static str {
        match self {
            ApiLoi::MaSai => "ma_sai",
            ApiLoi::KhongTimThay => "khong_tim_thay",
            ApiLoi::AnhQuaLon(_) => "anh_qua_lon",
            ApiLoi::KhongPhaiAnh => "khong_phai_anh",
            ApiLoi::DuLieuSai(_) => "du_lieu_sai",
            ApiLoi::ThuQuaNhieu(_) => "thu_qua_nhieu",
            ApiLoi::TamNgung => "tam_ngung",
            ApiLoi::ChiDoc => "chi_doc",
        }
    }

    pub fn trang_thai(&self) -> StatusCode {
        match self {
            ApiLoi::MaSai => StatusCode::UNAUTHORIZED,
            ApiLoi::KhongTimThay => StatusCode::NOT_FOUND,
            ApiLoi::AnhQuaLon(_) => StatusCode::PAYLOAD_TOO_LARGE,
            ApiLoi::KhongPhaiAnh => StatusCode::UNSUPPORTED_MEDIA_TYPE,
            ApiLoi::DuLieuSai(_) => StatusCode::UNPROCESSABLE_ENTITY,
            ApiLoi::ThuQuaNhieu(_) => StatusCode::TOO_MANY_REQUESTS,
            ApiLoi::TamNgung | ApiLoi::ChiDoc => StatusCode::SERVICE_UNAVAILABLE,
        }
    }
}

impl IntoResponse for ApiLoi {
    fn into_response(self) -> Response {
        let than = ThanLoi { loi: self.ma().to_string(), thong_bao: self.to_string() };
        let mut r = (self.trang_thai(), Json(than)).into_response();
        if let ApiLoi::ThuQuaNhieu(giay) = self {
            r.headers_mut().insert(header::RETRY_AFTER, HeaderValue::from(giay));
        }
        r
    }
}

impl From<sqlx::Error> for ApiLoi {
    fn from(e: sqlx::Error) -> Self {
        tracing::error!(loi = %e, "loi co so du lieu");
        ApiLoi::TamNgung
    }
}

impl From<object_store::Error> for ApiLoi {
    fn from(e: object_store::Error) -> Self {
        tracing::error!(loi = %e, "loi kho anh");
        ApiLoi::TamNgung
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ma_va_trang_thai_dung_nhu_thiet_ke() {
        let ca = [
            (ApiLoi::MaSai, "ma_sai", 401),
            (ApiLoi::KhongTimThay, "khong_tim_thay", 404),
            (ApiLoi::AnhQuaLon("x"), "anh_qua_lon", 413),
            (ApiLoi::KhongPhaiAnh, "khong_phai_anh", 415),
            (ApiLoi::DuLieuSai("x".into()), "du_lieu_sai", 422),
            (ApiLoi::ThuQuaNhieu(5), "thu_qua_nhieu", 429),
            (ApiLoi::TamNgung, "tam_ngung", 503),
            (ApiLoi::ChiDoc, "chi_doc", 503),
        ];
        for (l, ma, so) in ca {
            assert_eq!(l.ma(), ma);
            assert_eq!(l.trang_thai().as_u16(), so);
        }
    }

    #[tokio::test]
    async fn than_loi_la_json_va_429_co_retry_after() {
        let r = ApiLoi::ThuQuaNhieu(42).into_response();
        assert_eq!(r.status(), StatusCode::TOO_MANY_REQUESTS);
        assert_eq!(r.headers()[header::RETRY_AFTER], "42");
        let b = axum::body::to_bytes(r.into_body(), 4096).await.unwrap();
        let v: serde_json::Value = serde_json::from_slice(&b).unwrap();
        assert_eq!(v["loi"], "thu_qua_nhieu");
        assert!(v["thong_bao"].as_str().unwrap().contains("42"));
    }
}
