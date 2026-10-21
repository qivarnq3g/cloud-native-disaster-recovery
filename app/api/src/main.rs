use std::net::SocketAddr;
use std::sync::Arc;

use api::TrangThai;
use api::cau_hinh::CauHinh;
use tracing_subscriber::EnvFilter;

#[cfg(feature = "phat_hanh")]
#[global_allocator]
static CAP_PHAT: mimalloc::MiMalloc = mimalloc::MiMalloc;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    if std::env::args().nth(1).as_deref() == Some("--in-openapi") {
        println!("{}", api::openapi::tai_lieu().to_pretty_json()?);
        return Ok(());
    }
    tracing_subscriber::fmt()
        .json()
        .with_env_filter(EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new("info")))
        .init();
    let cau_hinh = CauHinh::tu_moi_truong()?;
    let cong = cau_hinh.cong;
    let tt = Arc::new(TrangThai::tu_cau_hinh(cau_hinh)?);
    api::trang_thai::chay_migrate_nen(tt.clone());
    let nghe = tokio::net::TcpListener::bind(("0.0.0.0", cong)).await?;
    tracing::info!(cong, "api dang nghe");
    axum::serve(nghe, api::ung_dung(tt).into_make_service_with_connect_info::<SocketAddr>())
        .with_graceful_shutdown(cho_tat())
        .await?;
    Ok(())
}

async fn cho_tat() {
    let ctrl_c = async {
        let _ = tokio::signal::ctrl_c().await;
    };
    #[cfg(unix)]
    let term = async {
        if let Ok(mut s) = tokio::signal::unix::signal(tokio::signal::unix::SignalKind::terminate()) {
            s.recv().await;
        }
    };
    #[cfg(not(unix))]
    let term = std::future::pending::<()>();
    tokio::select! {
        _ = ctrl_c => {},
        _ = term => {},
    }
}
