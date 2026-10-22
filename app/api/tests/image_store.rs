mod common;

use bytes::Bytes;
use common::{ALL_STORES, dead_store, read_only_store, writable_store};
use uuid::Uuid;

#[tokio::test]
async fn puts_and_gets_original_and_thumbnail() {
    for kind in ALL_STORES {
        let store = writable_store(kind);
        let id = Uuid::now_v7();
        assert_eq!(store.get_original(id).await.unwrap(), None, "{kind:?}");
        store
            .put_original(id, Bytes::from_static(b"original"))
            .await
            .unwrap();
        store
            .put_thumbnail(id, Bytes::from_static(b"thumbnail"))
            .await
            .unwrap();
        assert_eq!(
            store.get_original(id).await.unwrap(),
            Some(Bytes::from_static(b"original")),
            "{kind:?}"
        );
        assert_eq!(
            store.get_thumbnail(id).await.unwrap(),
            Some(Bytes::from_static(b"thumbnail")),
            "{kind:?}"
        );
        store.delete_thumbnail(id).await.unwrap();
        assert_eq!(store.get_thumbnail(id).await.unwrap(), None, "{kind:?}");
    }
}

#[tokio::test]
async fn probe_needs_only_read_access() {
    for kind in ALL_STORES {
        writable_store(kind).probe().await.unwrap();
        read_only_store(kind).probe().await.unwrap();
    }
}

#[tokio::test]
async fn read_only_credentials_cannot_write() {
    for kind in ALL_STORES {
        let id = Uuid::now_v7();
        assert!(
            read_only_store(kind)
                .put_thumbnail(id, Bytes::from_static(b"x"))
                .await
                .is_err(),
            "{kind:?}"
        );
        assert_eq!(
            writable_store(kind).get_thumbnail(id).await.unwrap(),
            None,
            "{kind:?}"
        );
    }
}

#[tokio::test]
async fn dead_store_fails_fast() {
    let started = std::time::Instant::now();
    assert!(dead_store().probe().await.is_err());
    assert!(started.elapsed() < std::time::Duration::from_secs(20));
}
