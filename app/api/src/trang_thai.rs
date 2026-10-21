use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::Duration;

use sqlx::PgPool;
use sqlx::postgres::PgPoolOptions;

use crate::anh_nho::DichVuAnhNho;
use crate::cau_hinh::CauHinh;
use crate::kho_anh::KhoAnh;
use crate::ma_bi_mat::KiemTraMa;

pub struct TrangThai {
    pub pool: PgPool,
    pub kho: KhoAnh,
    pub anh_nho: DichVuAnhNho,
    pub ma: KiemTraMa,
    pub cau_hinh: CauHinh,
    pub da_migrate: AtomicBool,
}

impl TrangThai {
    pub fn moi(pool: PgPool, kho: KhoAnh, cau_hinh: CauHinh) -> Self {
        Self {
            anh_nho: DichVuAnhNho::moi(kho.clone(), cau_hinh.chi_doc),
            ma: KiemTraMa::moi(&cau_hinh.ma_bi_mat),
            pool,
            kho,
            cau_hinh,
            da_migrate: AtomicBool::new(false),
        }
    }

    pub fn tu_cau_hinh(cau_hinh: CauHinh) -> anyhow::Result<Self> {
        let pool = PgPoolOptions::new()
            .max_connections(5)
            .acquire_timeout(Duration::from_secs(2))
            .connect_lazy(&cau_hinh.database_url)?;
        let kho = KhoAnh::tu_cau_hinh(&cau_hinh)?;
        Ok(Self::moi(pool, kho, cau_hinh))
    }
}

pub fn chay_migrate_nen(tt: Arc<TrangThai>) -> tokio::task::JoinHandle<()> {
    tokio::spawn(async move {
        loop {
            match sqlx::migrate!().run(&tt.pool).await {
                Ok(()) => {
                    tt.da_migrate.store(true, Ordering::Release);
                    tracing::info!("cau truc bang da san sang");
                    break;
                }
                Err(e) => {
                    tracing::warn!(loi = %e, "chua tao duoc cau truc bang, thu lai sau 2 giay");
                    tokio::time::sleep(Duration::from_secs(2)).await;
                }
            }
        }
    })
}
