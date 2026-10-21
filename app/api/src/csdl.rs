use serde::{Deserialize, Serialize};
use sqlx::PgPool;
use time::OffsetDateTime;
use utoipa::ToSchema;
use uuid::Uuid;

use crate::anh::AnhHopLe;

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, ToSchema)]
pub struct Bai {
    pub id: Uuid,
    pub tieu_de: String,
    pub mo_ta: String,
    pub anh_sha256: String,
    pub anh_kieu: String,
    pub anh_byte: i32,
    pub rong: i32,
    pub cao: i32,
    #[serde(with = "time::serde::rfc3339")]
    #[schema(value_type = String, format = DateTime)]
    pub tao_luc: OffsetDateTime,
}

struct DongBai {
    id: Uuid,
    tieu_de: String,
    mo_ta: String,
    anh_sha256: Vec<u8>,
    anh_kieu: String,
    anh_byte: i32,
    rong: i32,
    cao: i32,
    tao_luc: OffsetDateTime,
}

impl From<DongBai> for Bai {
    fn from(d: DongBai) -> Self {
        Self {
            id: d.id,
            tieu_de: d.tieu_de,
            mo_ta: d.mo_ta,
            anh_sha256: hex::encode(d.anh_sha256),
            anh_kieu: d.anh_kieu,
            anh_byte: d.anh_byte,
            rong: d.rong,
            cao: d.cao,
            tao_luc: d.tao_luc,
        }
    }
}

pub struct BaiMoi<'a> {
    pub id: Uuid,
    pub ma_lan_dang: Uuid,
    pub tieu_de: &'a str,
    pub mo_ta: &'a str,
    pub anh: &'a AnhHopLe,
}

pub enum KetQuaThem {
    Moi(Bai),
    DaCo(Bai),
}

pub async fn them(pool: &PgPool, b: &BaiMoi<'_>) -> sqlx::Result<KetQuaThem> {
    let dong = sqlx::query_as!(
        DongBai,
        r#"INSERT INTO bai (id, ma_lan_dang, tieu_de, mo_ta, anh_sha256, anh_kieu, anh_byte, rong, cao)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
           ON CONFLICT (ma_lan_dang) DO NOTHING
           RETURNING id AS "id!", tieu_de AS "tieu_de!", mo_ta AS "mo_ta!", anh_sha256 AS "anh_sha256!",
                     anh_kieu AS "anh_kieu!", anh_byte AS "anh_byte!", rong AS "rong!", cao AS "cao!", tao_luc AS "tao_luc!""#,
        b.id,
        b.ma_lan_dang,
        b.tieu_de,
        b.mo_ta,
        &b.anh.sha256[..],
        b.anh.kieu.mime(),
        b.anh.du_lieu.len() as i32,
        b.anh.rong as i32,
        b.anh.cao as i32,
    )
    .fetch_optional(pool)
    .await?;
    match dong {
        Some(d) => Ok(KetQuaThem::Moi(d.into())),
        None => {
            let cu = tim_theo_ma_lan_dang(pool, b.ma_lan_dang).await?.ok_or(sqlx::Error::RowNotFound)?;
            Ok(KetQuaThem::DaCo(cu))
        }
    }
}

pub async fn lay(pool: &PgPool, id: Uuid) -> sqlx::Result<Option<Bai>> {
    let d = sqlx::query_as!(
        DongBai,
        "SELECT id, tieu_de, mo_ta, anh_sha256, anh_kieu, anh_byte, rong, cao, tao_luc FROM bai WHERE id = $1",
        id
    )
    .fetch_optional(pool)
    .await?;
    Ok(d.map(Bai::from))
}

pub async fn tim_theo_ma_lan_dang(pool: &PgPool, ma: Uuid) -> sqlx::Result<Option<Bai>> {
    let d = sqlx::query_as!(
        DongBai,
        "SELECT id, tieu_de, mo_ta, anh_sha256, anh_kieu, anh_byte, rong, cao, tao_luc FROM bai WHERE ma_lan_dang = $1",
        ma
    )
    .fetch_optional(pool)
    .await?;
    Ok(d.map(Bai::from))
}

pub async fn trang(pool: &PgPool, truoc: Option<Uuid>, so: i64) -> sqlx::Result<Vec<Bai>> {
    let ds = sqlx::query_as!(
        DongBai,
        "SELECT id, tieu_de, mo_ta, anh_sha256, anh_kieu, anh_byte, rong, cao, tao_luc FROM bai
         WHERE ($1::uuid IS NULL OR id < $1) ORDER BY id DESC LIMIT $2",
        truoc,
        so
    )
    .fetch_all(pool)
    .await?;
    Ok(ds.into_iter().map(Bai::from).collect())
}
