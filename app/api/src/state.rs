use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::Duration;

use sqlx::PgPool;
use sqlx::postgres::PgPoolOptions;

use crate::config::Config;
use crate::image_store::ImageStore;
use crate::secret_code::SecretCodeChecker;
use crate::thumbnail::ThumbnailService;

pub struct AppState {
    pub pool: PgPool,
    pub store: ImageStore,
    pub thumbnails: ThumbnailService,
    pub secret_code: SecretCodeChecker,
    pub config: Config,
    pub migrated: AtomicBool,
}

impl AppState {
    pub fn new(pool: PgPool, store: ImageStore, config: Config) -> Self {
        Self {
            thumbnails: ThumbnailService::new(store.clone(), config.read_only),
            secret_code: SecretCodeChecker::new(&config.secret_code),
            pool,
            store,
            config,
            migrated: AtomicBool::new(false),
        }
    }

    pub fn from_config(config: Config) -> anyhow::Result<Self> {
        let pool = PgPoolOptions::new()
            .max_connections(5)
            .acquire_timeout(Duration::from_secs(2))
            .connect_lazy(&config.database_url)?;
        let store = ImageStore::from_config(&config)?;
        Ok(Self::new(pool, store, config))
    }
}

pub fn spawn_migrations(state: Arc<AppState>) -> tokio::task::JoinHandle<()> {
    tokio::spawn(async move {
        loop {
            match sqlx::migrate!().run(&state.pool).await {
                Ok(()) => {
                    state.migrated.store(true, Ordering::Release);
                    tracing::info!("database schema ready");
                    break;
                }
                Err(e) => {
                    tracing::warn!(error = %e, "database schema not ready, retrying in 2 seconds");
                    tokio::time::sleep(Duration::from_secs(2)).await;
                }
            }
        }
    })
}
