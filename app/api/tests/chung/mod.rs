#![allow(dead_code)]

use std::sync::Arc;

use api::kho_anh::{KhoAnh, tuy_chon_mang};
use object_store::aws::{AmazonS3, AmazonS3Builder};
use object_store::azure::{AzureConfigKey, MicrosoftAzureBuilder};

#[derive(Clone, Copy, Debug)]
pub enum LoaiKhoThu {
    Azurite,
    Seaweed,
}

pub const CAC_KHO: [LoaiKhoThu; 2] = [LoaiKhoThu::Azurite, LoaiKhoThu::Seaweed];

fn s3(diem: &str, id: &str, bi_mat: &str) -> AmazonS3 {
    let (tuy_chon, thu_lai) = tuy_chon_mang();
    AmazonS3Builder::new()
        .with_client_options(tuy_chon)
        .with_retry(thu_lai)
        .with_endpoint(diem)
        .with_allow_http(true)
        .with_region("us-east-1")
        .with_bucket_name("anh")
        .with_access_key_id(id)
        .with_secret_access_key(bi_mat)
        .build()
        .unwrap()
}

pub fn kho_ghi(loai: LoaiKhoThu) -> KhoAnh {
    match loai {
        LoaiKhoThu::Azurite => KhoAnh::moi(Arc::new(
            MicrosoftAzureBuilder::new()
                .with_use_emulator(true)
                .with_container_name("anh")
                .build()
                .unwrap(),
        )),
        LoaiKhoThu::Seaweed => {
            KhoAnh::moi(Arc::new(s3("http://127.0.0.1:8333", "ghi", "ghi-bi-mat")))
        }
    }
}

pub fn kho_doc(loai: LoaiKhoThu) -> KhoAnh {
    match loai {
        LoaiKhoThu::Azurite => {
            let sas = std::env::var("AZURITE_SAS_DOC")
                .expect("chạy app/thu/chuan-bi.sh rồi đặt AZURITE_SAS_DOC");
            KhoAnh::moi(Arc::new(
                MicrosoftAzureBuilder::new()
                    .with_use_emulator(true)
                    .with_container_name("anh")
                    .with_config(AzureConfigKey::SasKey, sas)
                    .build()
                    .unwrap(),
            ))
        }
        LoaiKhoThu::Seaweed => {
            KhoAnh::moi(Arc::new(s3("http://127.0.0.1:8333", "doc", "doc-bi-mat")))
        }
    }
}

pub fn kho_chet() -> KhoAnh {
    KhoAnh::moi(Arc::new(s3("http://127.0.0.1:1", "x", "x")))
}

use std::io::Cursor;
use std::net::SocketAddr;

use api::TrangThai;
use api::cau_hinh::{CauHinh, LoaiKho};
use image::{DynamicImage, ImageFormat, RgbImage};
use sqlx::PgPool;
use sqlx::postgres::PgPoolOptions;
use uuid::Uuid;

pub const MA: &str = "ma-thu-0123456789";

pub struct UngDungThu {
    pub url: String,
    pub tt: Arc<TrangThai>,
}

pub fn cau_hinh_thu(chi_doc: bool) -> CauHinh {
    CauHinh {
        database_url: String::new(),
        loai_kho: LoaiKho::S3,
        ten_container: "anh".into(),
        chi_doc,
        ma_bi_mat: MA.into(),
        cum: "chinh".into(),
        vung: "thu".into(),
        cors_nguon: vec!["http://localhost:4321".into()],
        proxy_tin_cay: vec![],
        cong: 0,
    }
}

pub async fn pool_thu() -> PgPool {
    let url = std::env::var("DATABASE_URL")
        .unwrap_or_else(|_| "postgres://postgres:thu@127.0.0.1:5432/dr".into());
    PgPool::connect(&url).await.unwrap()
}

pub fn pool_chet() -> PgPool {
    PgPoolOptions::new()
        .acquire_timeout(std::time::Duration::from_secs(1))
        .connect_lazy("postgres://x:x@127.0.0.1:1/x")
        .unwrap()
}

pub async fn chay_khong_cho(pool: PgPool, kho: KhoAnh, chi_doc: bool) -> UngDungThu {
    let tt = Arc::new(TrangThai::moi(pool, kho, cau_hinh_thu(chi_doc)));
    api::trang_thai::chay_migrate_nen(tt.clone());
    let nghe = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let url = format!("http://{}", nghe.local_addr().unwrap());
    let ung_dung = api::ung_dung(tt.clone());
    tokio::spawn(async move {
        axum::serve(
            nghe,
            ung_dung.into_make_service_with_connect_info::<SocketAddr>(),
        )
        .await
        .unwrap();
    });
    UngDungThu { url, tt }
}

pub async fn chay(kho: KhoAnh, chi_doc: bool) -> UngDungThu {
    let app = chay_khong_cho(pool_thu().await, kho, chi_doc).await;
    while !app.tt.da_migrate.load(std::sync::atomic::Ordering::Acquire) {
        tokio::time::sleep(std::time::Duration::from_millis(50)).await;
    }
    app
}

pub fn png(rong: u32, cao: u32) -> Vec<u8> {
    let anh = DynamicImage::ImageRgb8(RgbImage::from_fn(rong, cao, |x, y| {
        image::Rgb([(x % 256) as u8, (y % 256) as u8, 7])
    }));
    let mut ra = Cursor::new(Vec::new());
    anh.write_to(&mut ra, ImageFormat::Png).unwrap();
    ra.into_inner()
}

pub async fn dang(
    c: &reqwest::Client,
    url: &str,
    ma: &str,
    ma_lan_dang: Uuid,
    tieu_de: &str,
    anh: Vec<u8>,
) -> reqwest::Response {
    let form = reqwest::multipart::Form::new()
        .text("ma_lan_dang", ma_lan_dang.to_string())
        .text("tieu_de", tieu_de.to_string())
        .text("mo_ta", "mô tả thử")
        .part(
            "anh",
            reqwest::multipart::Part::bytes(anh).file_name("anh.png"),
        );
    c.post(format!("{url}/v1/bai"))
        .bearer_auth(ma)
        .multipart(form)
        .send()
        .await
        .unwrap()
}

pub async fn them_truc_tiep(app: &UngDungThu, rong: u32, cao: u32) -> api::csdl::Bai {
    let a = api::anh::kiem_tra(bytes::Bytes::from(png(rong, cao))).unwrap();
    let id = Uuid::now_v7();
    app.tt.kho.cat_goc(id, a.du_lieu.clone()).await.unwrap();
    match api::csdl::them(
        &app.tt.pool,
        &api::csdl::BaiMoi {
            id,
            ma_lan_dang: Uuid::now_v7(),
            tieu_de: "Thử",
            mo_ta: "",
            anh: &a,
        },
    )
    .await
    .unwrap()
    {
        api::csdl::KetQuaThem::Moi(b) => b,
        api::csdl::KetQuaThem::DaCo(b) => b,
    }
}
