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
            let ready = if state.config.read_only {
                schema_is_current(&state.pool).await
            } else {
                sqlx::migrate!().run(&state.pool).await.map_err(Into::into)
            };
            match ready {
                Ok(()) => {
                    state.migrated.store(true, Ordering::Release);
                    tracing::info!(read_only = state.config.read_only, "database schema ready");
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

fn expected_versions() -> Vec<i64> {
    sqlx::migrate!().iter().map(|m| m.version).collect()
}

fn missing_versions(expected: &[i64], applied: &[i64]) -> Vec<i64> {
    expected
        .iter()
        .copied()
        .filter(|v| !applied.contains(v))
        .collect()
}

async fn schema_is_current(pool: &PgPool) -> anyhow::Result<()> {
    let applied: Vec<i64> =
        sqlx::query_scalar("SELECT version FROM _sqlx_migrations WHERE success")
            .fetch_all(pool)
            .await?;
    let missing = missing_versions(&expected_versions(), &applied);
    anyhow::ensure!(
        missing.is_empty(),
        "read-only database lacks migrations {missing:?}"
    );
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::missing_versions;

    #[test]
    fn missing_versions_lists_expected_versions_not_applied() {
        assert_eq!(missing_versions(&[1, 2, 3], &[1, 3]), vec![2]);
        assert_eq!(missing_versions(&[1, 2], &[2, 1, 7]), Vec::<i64>::new());
        assert_eq!(missing_versions(&[1], &[]), vec![1]);
    }

    #[test]
    fn embedded_migrations_are_known() {
        assert!(!super::expected_versions().is_empty());
    }
}
