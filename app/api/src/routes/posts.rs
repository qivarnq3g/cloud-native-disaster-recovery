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

use crate::AppState;
use crate::db::{self, InsertOutcome, NewPost, Post};
use crate::error::{ApiError, ErrorBody};
use crate::image_file::{self, ImageType};
use crate::{secret_code, text};

#[derive(Debug, Deserialize, IntoParams)]
#[into_params(parameter_in = Query)]
pub struct PageQuery {
    pub before: Option<Uuid>,
    pub limit: Option<i64>,
}

#[derive(Debug, Serialize, Deserialize, ToSchema)]
pub struct PostPage {
    pub posts: Vec<Post>,
    pub next: Option<Uuid>,
}

#[utoipa::path(
    get,
    path = "/v1/posts",
    params(PageQuery),
    responses(
        (status = 200, body = PostPage),
        (status = 422, body = ErrorBody),
        (status = 503, body = ErrorBody)
    )
)]
pub async fn list_posts(
    State(state): State<Arc<AppState>>,
    q: Result<Query<PageQuery>, QueryRejection>,
) -> Result<Json<PostPage>, ApiError> {
    let Query(q) = q.map_err(|_| ApiError::InvalidInput("Tham số không hợp lệ.".into()))?;
    let limit = q.limit.unwrap_or(24);
    if !(1..=60).contains(&limit) {
        return Err(ApiError::InvalidInput(
            "Số bài mỗi trang phải từ 1 đến 60.".into(),
        ));
    }
    let mut posts = db::page(&state.pool, q.before, limit + 1).await?;
    let next = if posts.len() as i64 > limit {
        posts.truncate(limit as usize);
        posts.last().map(|b| b.id)
    } else {
        None
    };
    Ok(Json(PostPage { posts, next }))
}

#[utoipa::path(
    get,
    path = "/v1/posts/{id}",
    params(("id" = Uuid, Path)),
    responses((status = 200, body = Post), (status = 404, body = ErrorBody), (status = 503, body = ErrorBody))
)]
pub async fn get_post(
    State(state): State<Arc<AppState>>,
    id: Result<Path<Uuid>, PathRejection>,
) -> Result<Json<Post>, ApiError> {
    Ok(Json(find_post(&state, id).await?))
}

#[utoipa::path(
    get,
    path = "/v1/posts/{id}/image",
    params(("id" = Uuid, Path)),
    responses((status = 200, description = "Ảnh gốc, kiểu theo image_type"), (status = 404, body = ErrorBody))
)]
pub async fn get_post_image(
    State(state): State<Arc<AppState>>,
    id: Result<Path<Uuid>, PathRejection>,
) -> Result<Response, ApiError> {
    let post = find_post(&state, id).await?;
    let data = state
        .store
        .get_original(post.id)
        .await?
        .ok_or(ApiError::NotFound)?;
    Ok(image_response(
        data,
        image_type_of(&post)?.mime(),
        post.image_sha256,
    ))
}

#[utoipa::path(
    get,
    path = "/v1/posts/{id}/thumbnail",
    params(("id" = Uuid, Path)),
    responses((status = 200, description = "Ảnh nhỏ WebP, hoặc ảnh gốc nếu ảnh đã nhỏ"), (status = 404, body = ErrorBody))
)]
pub async fn get_post_thumbnail(
    State(state): State<Arc<AppState>>,
    id: Result<Path<Uuid>, PathRejection>,
) -> Result<Response, ApiError> {
    let post = find_post(&state, id).await?;
    let kind = image_type_of(&post)?;
    let out = state
        .thumbnails
        .get(post.id, kind, post.width as u32, post.height as u32)
        .await?;
    Ok(image_response(
        out.data,
        out.content_type,
        format!("{}-thumbnail", post.image_sha256),
    ))
}

async fn find_post(
    state: &AppState,
    id: Result<Path<Uuid>, PathRejection>,
) -> Result<Post, ApiError> {
    let Path(id) = id.map_err(|_| ApiError::NotFound)?;
    db::get(&state.pool, id).await?.ok_or(ApiError::NotFound)
}

fn image_type_of(post: &Post) -> Result<ImageType, ApiError> {
    ImageType::from_mime(&post.image_type).ok_or(ApiError::Unavailable)
}

fn image_response(data: Bytes, content_type: &'static str, etag: String) -> Response {
    (
        [
            (header::CONTENT_TYPE, content_type.to_string()),
            (header::ETAG, format!("\"{etag}\"")),
            (
                header::CACHE_CONTROL,
                "public, max-age=31536000, immutable".to_string(),
            ),
        ],
        data,
    )
        .into_response()
}

#[derive(ToSchema)]
#[allow(dead_code)]
pub struct CreatePostForm {
    idempotency_key: Uuid,
    title: String,
    description: String,
    #[schema(value_type = String, format = Binary)]
    image: Vec<u8>,
}

struct PostForm {
    idempotency_key: Uuid,
    title: String,
    description: String,
    image: Bytes,
}

#[utoipa::path(
    post,
    path = "/v1/posts",
    request_body(content = CreatePostForm, content_type = "multipart/form-data"),
    security(("secret_code" = [])),
    responses(
        (status = 201, body = Post),
        (status = 200, body = Post),
        (status = 401, body = ErrorBody),
        (status = 413, body = ErrorBody),
        (status = 415, body = ErrorBody),
        (status = 422, body = ErrorBody),
        (status = 429, body = ErrorBody),
        (status = 503, body = ErrorBody)
    )
)]
pub async fn create_post(
    State(state): State<Arc<AppState>>,
    ConnectInfo(peer): ConnectInfo<SocketAddr>,
    headers: HeaderMap,
    multipart: Result<Multipart, MultipartRejection>,
) -> Result<(StatusCode, Json<Post>), ApiError> {
    if state.config.read_only {
        return Err(ApiError::ReadOnly);
    }
    let ip = secret_code::client_ip(peer, &headers, &state.config.trusted_proxies);
    state
        .secret_code
        .check(ip, secret_code::code_from_headers(&headers), Instant::now())?;
    let multipart =
        multipart.map_err(|_| ApiError::InvalidInput("Cần gửi multipart/form-data.".into()))?;
    let form = read_form(multipart).await?;
    if let Some(existing) = db::find_by_idempotency_key(&state.pool, form.idempotency_key).await? {
        return Ok((StatusCode::OK, Json(existing)));
    }
    let title = text::title(&form.title)?;
    let description = text::description(&form.description)?;
    let valid = tokio::task::spawn_blocking(move || image_file::validate(form.image))
        .await
        .map_err(|_| ApiError::Unavailable)??;
    let id = Uuid::now_v7();
    state.store.put_original(id, valid.data.clone()).await?;
    let new_post = NewPost {
        id,
        idempotency_key: form.idempotency_key,
        title: &title,
        description: &description,
        image: &valid,
    };
    match db::insert(&state.pool, &new_post).await? {
        InsertOutcome::Created(b) => Ok((StatusCode::CREATED, Json(b))),
        InsertOutcome::Existing(b) => Ok((StatusCode::OK, Json(b))),
    }
}

async fn read_form(mut m: Multipart) -> Result<PostForm, ApiError> {
    let (mut key, mut title, mut description, mut image) = (None, None, None, None);
    while let Some(field) = m.next_field().await.map_err(multipart_error)? {
        match field.name() {
            Some("idempotency_key") => key = Some(field.text().await.map_err(multipart_error)?),
            Some("title") => title = Some(field.text().await.map_err(multipart_error)?),
            Some("description") => description = Some(field.text().await.map_err(multipart_error)?),
            Some("image") => image = Some(field.bytes().await.map_err(multipart_error)?),
            _ => {}
        }
    }
    let idempotency_key = key
        .as_deref()
        .and_then(|s| Uuid::parse_str(s.trim()).ok())
        .ok_or_else(|| ApiError::InvalidInput("Thiếu hoặc sai idempotency_key.".into()))?;
    Ok(PostForm {
        idempotency_key,
        title: title.ok_or_else(|| ApiError::InvalidInput("Thiếu tiêu đề.".into()))?,
        description: description.unwrap_or_default(),
        image: image.ok_or_else(|| ApiError::InvalidInput("Thiếu ảnh.".into()))?,
    })
}

fn multipart_error(e: MultipartError) -> ApiError {
    if e.status() == StatusCode::PAYLOAD_TOO_LARGE {
        ApiError::ImageTooLarge("Ảnh lớn hơn 1 MB.")
    } else {
        ApiError::InvalidInput("Dữ liệu gửi lên không đọc được.".into())
    }
}
