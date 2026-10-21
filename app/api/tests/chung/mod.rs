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
            MicrosoftAzureBuilder::new().with_use_emulator(true).with_container_name("anh").build().unwrap(),
        )),
        LoaiKhoThu::Seaweed => KhoAnh::moi(Arc::new(s3("http://127.0.0.1:8333", "ghi", "ghi-bi-mat"))),
    }
}

pub fn kho_doc(loai: LoaiKhoThu) -> KhoAnh {
    match loai {
        LoaiKhoThu::Azurite => {
            let sas = std::env::var("AZURITE_SAS_DOC").expect("chạy app/thu/chuan-bi.sh rồi đặt AZURITE_SAS_DOC");
            KhoAnh::moi(Arc::new(
                MicrosoftAzureBuilder::new()
                    .with_use_emulator(true)
                    .with_container_name("anh")
                    .with_config(AzureConfigKey::SasKey, sas)
                    .build()
                    .unwrap(),
            ))
        }
        LoaiKhoThu::Seaweed => KhoAnh::moi(Arc::new(s3("http://127.0.0.1:8333", "doc", "doc-bi-mat"))),
    }
}

pub fn kho_chet() -> KhoAnh {
    KhoAnh::moi(Arc::new(s3("http://127.0.0.1:1", "x", "x")))
}
