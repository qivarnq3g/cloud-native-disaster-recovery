use axum::Json;
use axum::http::{HeaderValue, StatusCode, header};
use axum::response::{IntoResponse, Response};
use serde::{Deserialize, Serialize};
use utoipa::ToSchema;

#[derive(Debug, Clone, PartialEq, Eq, thiserror::Error)]
pub enum ApiError {
    #[error("Mã bí mật không đúng.")]
    InvalidCode,
    #[error("Không tìm thấy.")]
    NotFound,
    #[error("{0}")]
    ImageTooLarge(&'static str),
    #[error("Tệp không phải ảnh JPG, PNG hoặc WebP đọc được.")]
    NotAnImage,
    #[error("{0}")]
    InvalidInput(String),
    #[error("Thử sai quá nhiều lần. Thử lại sau {0} giây.")]
    TooManyAttempts(u64),
    #[error("Hệ thống tạm ngừng, thử lại sau.")]
    Unavailable,
    #[error("Hệ thống đang ở chế độ chỉ đọc.")]
    ReadOnly,
}

#[derive(Debug, Serialize, Deserialize, ToSchema)]
pub struct ErrorBody {
    pub error: String,
    pub message: String,
}

impl ApiError {
    pub fn code(&self) -> &'static str {
        match self {
            ApiError::InvalidCode => "invalid_code",
            ApiError::NotFound => "not_found",
            ApiError::ImageTooLarge(_) => "image_too_large",
            ApiError::NotAnImage => "not_an_image",
            ApiError::InvalidInput(_) => "invalid_input",
            ApiError::TooManyAttempts(_) => "too_many_attempts",
            ApiError::Unavailable => "unavailable",
            ApiError::ReadOnly => "read_only",
        }
    }

    pub fn status(&self) -> StatusCode {
        match self {
            ApiError::InvalidCode => StatusCode::UNAUTHORIZED,
            ApiError::NotFound => StatusCode::NOT_FOUND,
            ApiError::ImageTooLarge(_) => StatusCode::PAYLOAD_TOO_LARGE,
            ApiError::NotAnImage => StatusCode::UNSUPPORTED_MEDIA_TYPE,
            ApiError::InvalidInput(_) => StatusCode::UNPROCESSABLE_ENTITY,
            ApiError::TooManyAttempts(_) => StatusCode::TOO_MANY_REQUESTS,
            ApiError::Unavailable | ApiError::ReadOnly => StatusCode::SERVICE_UNAVAILABLE,
        }
    }
}

impl IntoResponse for ApiError {
    fn into_response(self) -> Response {
        let body = ErrorBody {
            error: self.code().to_string(),
            message: self.to_string(),
        };
        let mut r = (self.status(), Json(body)).into_response();
        if let ApiError::TooManyAttempts(seconds) = self {
            r.headers_mut()
                .insert(header::RETRY_AFTER, HeaderValue::from(seconds));
        }
        r
    }
}

impl From<sqlx::Error> for ApiError {
    fn from(e: sqlx::Error) -> Self {
        tracing::error!(error = %e, "database error");
        ApiError::Unavailable
    }
}

impl From<object_store::Error> for ApiError {
    fn from(e: object_store::Error) -> Self {
        tracing::error!(error = %e, "image store error");
        ApiError::Unavailable
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn codes_and_statuses_match_design() {
        let cases = [
            (ApiError::InvalidCode, "invalid_code", 401),
            (ApiError::NotFound, "not_found", 404),
            (ApiError::ImageTooLarge("x"), "image_too_large", 413),
            (ApiError::NotAnImage, "not_an_image", 415),
            (ApiError::InvalidInput("x".into()), "invalid_input", 422),
            (ApiError::TooManyAttempts(5), "too_many_attempts", 429),
            (ApiError::Unavailable, "unavailable", 503),
            (ApiError::ReadOnly, "read_only", 503),
        ];
        for (err, code, status) in cases {
            assert_eq!(err.code(), code);
            assert_eq!(err.status().as_u16(), status);
        }
    }

    #[tokio::test]
    async fn error_body_is_json_and_429_has_retry_after() {
        let r = ApiError::TooManyAttempts(42).into_response();
        assert_eq!(r.status(), StatusCode::TOO_MANY_REQUESTS);
        assert_eq!(r.headers()[header::RETRY_AFTER], "42");
        let b = axum::body::to_bytes(r.into_body(), 4096).await.unwrap();
        let v: serde_json::Value = serde_json::from_slice(&b).unwrap();
        assert_eq!(v["error"], "too_many_attempts");
        assert!(v["message"].as_str().unwrap().contains("42"));
    }
}
