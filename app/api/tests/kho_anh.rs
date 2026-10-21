mod chung;

use bytes::Bytes;
use chung::{CAC_KHO, kho_chet, kho_doc, kho_ghi};
use uuid::Uuid;

#[tokio::test]
async fn cat_va_lay_anh_goc_va_anh_nho() {
    for loai in CAC_KHO {
        let kho = kho_ghi(loai);
        let id = Uuid::now_v7();
        assert_eq!(kho.lay_goc(id).await.unwrap(), None, "{loai:?}");
        kho.cat_goc(id, Bytes::from_static(b"goc")).await.unwrap();
        kho.cat_nho(id, Bytes::from_static(b"nho")).await.unwrap();
        assert_eq!(
            kho.lay_goc(id).await.unwrap(),
            Some(Bytes::from_static(b"goc")),
            "{loai:?}"
        );
        assert_eq!(
            kho.lay_nho(id).await.unwrap(),
            Some(Bytes::from_static(b"nho")),
            "{loai:?}"
        );
        kho.xoa_nho(id).await.unwrap();
        assert_eq!(kho.lay_nho(id).await.unwrap(), None, "{loai:?}");
    }
}

#[tokio::test]
async fn tham_do_chi_can_quyen_doc() {
    for loai in CAC_KHO {
        kho_ghi(loai).tham_do().await.unwrap();
        kho_doc(loai).tham_do().await.unwrap();
    }
}

#[tokio::test]
async fn ma_chi_doc_khong_ghi_duoc() {
    for loai in CAC_KHO {
        let id = Uuid::now_v7();
        assert!(
            kho_doc(loai)
                .cat_nho(id, Bytes::from_static(b"x"))
                .await
                .is_err(),
            "{loai:?}"
        );
        assert_eq!(kho_ghi(loai).lay_nho(id).await.unwrap(), None, "{loai:?}");
    }
}

#[tokio::test]
async fn kho_chet_bao_loi_nhanh() {
    let bat_dau = std::time::Instant::now();
    assert!(kho_chet().tham_do().await.is_err());
    assert!(bat_dau.elapsed() < std::time::Duration::from_secs(20));
}
