use serde::{Deserialize, Serialize};
use sqlx::PgPool;
use time::OffsetDateTime;
use utoipa::ToSchema;
use uuid::Uuid;

use crate::image_file::ValidImage;

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, ToSchema)]
pub struct Post {
    pub id: Uuid,
    pub title: String,
    pub description: String,
    pub image_sha256: String,
    pub image_type: String,
    pub image_bytes: i32,
    pub width: i32,
    pub height: i32,
    #[serde(with = "time::serde::rfc3339")]
    #[schema(value_type = String, format = DateTime)]
    pub created_at: OffsetDateTime,
}

struct PostRow {
    id: Uuid,
    title: String,
    description: String,
    image_sha256: Vec<u8>,
    image_type: String,
    image_bytes: i32,
    width: i32,
    height: i32,
    created_at: OffsetDateTime,
}

impl From<PostRow> for Post {
    fn from(d: PostRow) -> Self {
        Self {
            id: d.id,
            title: d.title,
            description: d.description,
            image_sha256: hex::encode(d.image_sha256),
            image_type: d.image_type,
            image_bytes: d.image_bytes,
            width: d.width,
            height: d.height,
            created_at: d.created_at,
        }
    }
}

pub struct NewPost<'a> {
    pub id: Uuid,
    pub idempotency_key: Uuid,
    pub title: &'a str,
    pub description: &'a str,
    pub image: &'a ValidImage,
}

pub enum InsertOutcome {
    Created(Post),
    Existing(Post),
}

pub async fn insert(pool: &PgPool, post: &NewPost<'_>) -> sqlx::Result<InsertOutcome> {
    let row = sqlx::query_as!(
        PostRow,
        r#"INSERT INTO posts (id, idempotency_key, title, description, image_sha256, image_type, image_bytes, width, height)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
           ON CONFLICT (idempotency_key) DO NOTHING
           RETURNING id AS "id!", title AS "title!", description AS "description!", image_sha256 AS "image_sha256!",
                     image_type AS "image_type!", image_bytes AS "image_bytes!", width AS "width!", height AS "height!", created_at AS "created_at!""#,
        post.id,
        post.idempotency_key,
        post.title,
        post.description,
        &post.image.sha256[..],
        post.image.kind.mime(),
        post.image.data.len() as i32,
        post.image.width as i32,
        post.image.height as i32,
    )
    .fetch_optional(pool)
    .await?;
    match row {
        Some(d) => Ok(InsertOutcome::Created(d.into())),
        None => {
            let existing = find_by_idempotency_key(pool, post.idempotency_key)
                .await?
                .ok_or(sqlx::Error::RowNotFound)?;
            Ok(InsertOutcome::Existing(existing))
        }
    }
}

pub async fn get(pool: &PgPool, id: Uuid) -> sqlx::Result<Option<Post>> {
    let d = sqlx::query_as!(
        PostRow,
        "SELECT id, title, description, image_sha256, image_type, image_bytes, width, height, created_at FROM posts WHERE id = $1",
        id
    )
    .fetch_optional(pool)
    .await?;
    Ok(d.map(Post::from))
}

pub async fn find_by_idempotency_key(pool: &PgPool, key: Uuid) -> sqlx::Result<Option<Post>> {
    let d = sqlx::query_as!(
        PostRow,
        "SELECT id, title, description, image_sha256, image_type, image_bytes, width, height, created_at FROM posts WHERE idempotency_key = $1",
        key
    )
    .fetch_optional(pool)
    .await?;
    Ok(d.map(Post::from))
}

pub async fn page(pool: &PgPool, before: Option<Uuid>, limit: i64) -> sqlx::Result<Vec<Post>> {
    let posts = sqlx::query_as!(
        PostRow,
        "SELECT id, title, description, image_sha256, image_type, image_bytes, width, height, created_at FROM posts
         WHERE ($1::uuid IS NULL OR id < $1) ORDER BY id DESC LIMIT $2",
        before,
        limit
    )
    .fetch_all(pool)
    .await?;
    Ok(posts.into_iter().map(Post::from).collect())
}
