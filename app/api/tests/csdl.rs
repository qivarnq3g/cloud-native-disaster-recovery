use std::io::Cursor;

use api::anh::{AnhHopLe, kiem_tra};
use api::csdl::{BaiMoi, KetQuaThem, lay, them, tim_theo_ma_lan_dang, trang};
use bytes::Bytes;
use image::{DynamicImage, ImageFormat, RgbImage};
use sqlx::PgPool;
use uuid::Uuid;

async fn pool() -> PgPool {
    let url = std::env::var("DATABASE_URL")
        .unwrap_or_else(|_| "postgres://postgres:thu@127.0.0.1:5432/dr".into());
    let pool = PgPool::connect(&url).await.unwrap();
    sqlx::migrate!().run(&pool).await.unwrap();
    pool
}

fn anh() -> AnhHopLe {
    let mut ra = Cursor::new(Vec::new());
    DynamicImage::ImageRgb8(RgbImage::new(32, 24))
        .write_to(&mut ra, ImageFormat::Png)
        .unwrap();
    kiem_tra(Bytes::from(ra.into_inner())).unwrap()
}

#[tokio::test]
async fn them_roi_lay_lai_dung_truong() {
    let pool = pool().await;
    let a = anh();
    let (id, ma) = (Uuid::now_v7(), Uuid::now_v7());
    let KetQuaThem::Moi(b) = them(
        &pool,
        &BaiMoi {
            id,
            ma_lan_dang: ma,
            tieu_de: "Tiêu đề",
            mo_ta: "Mô tả",
            anh: &a,
        },
    )
    .await
    .unwrap() else {
        panic!("phải là bài mới");
    };
    assert_eq!(b.id, id);
    assert_eq!(b.anh_sha256, hex::encode(a.sha256));
    assert_eq!(
        (b.rong, b.cao, b.anh_byte),
        (32, 24, a.du_lieu.len() as i32)
    );
    assert_eq!(b.anh_kieu, "image/png");
    assert_eq!(lay(&pool, id).await.unwrap(), Some(b.clone()));
    assert_eq!(tim_theo_ma_lan_dang(&pool, ma).await.unwrap(), Some(b));
    assert_eq!(lay(&pool, Uuid::now_v7()).await.unwrap(), None);
}

#[tokio::test]
async fn trung_ma_lan_dang_thi_tra_bai_cu() {
    let pool = pool().await;
    let a = anh();
    let ma = Uuid::now_v7();
    let id_dau = Uuid::now_v7();
    them(
        &pool,
        &BaiMoi {
            id: id_dau,
            ma_lan_dang: ma,
            tieu_de: "Một",
            mo_ta: "",
            anh: &a,
        },
    )
    .await
    .unwrap();
    match them(
        &pool,
        &BaiMoi {
            id: Uuid::now_v7(),
            ma_lan_dang: ma,
            tieu_de: "Hai",
            mo_ta: "",
            anh: &a,
        },
    )
    .await
    .unwrap()
    {
        KetQuaThem::DaCo(b) => assert_eq!((b.id, b.tieu_de.as_str()), (id_dau, "Một")),
        KetQuaThem::Moi(_) => panic!("không được tạo bài thứ hai"),
    }
}

#[tokio::test]
async fn phan_trang_moi_nhat_truoc_theo_con_tro() {
    let pool = pool().await;
    let a = anh();
    let mut ids = Vec::new();
    for i in 0..5 {
        let id = Uuid::now_v7();
        them(
            &pool,
            &BaiMoi {
                id,
                ma_lan_dang: Uuid::now_v7(),
                tieu_de: &format!("Trang {i}"),
                mo_ta: "",
                anh: &a,
            },
        )
        .await
        .unwrap();
        ids.push(id);
    }
    let sau_cung = Uuid::now_v7();
    let mut thay = Vec::new();
    let mut con_tro = Some(sau_cung);
    while thay.len() < 5 {
        let ds = trang(&pool, con_tro, 2).await.unwrap();
        assert!(!ds.is_empty());
        assert!(ds.windows(2).all(|w| w[0].id > w[1].id));
        con_tro = ds.last().map(|b| b.id);
        thay.extend(ds.into_iter().map(|b| b.id).filter(|id| ids.contains(id)));
    }
    ids.reverse();
    assert_eq!(thay, ids);
}
