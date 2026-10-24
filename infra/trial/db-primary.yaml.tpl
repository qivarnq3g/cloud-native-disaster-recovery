apiVersion: v1
kind: Secret
metadata:
  name: japan-store-key
type: Opaque
stringData:
  NAME: __BACKUP_ACCOUNT__
  KEY: __KEY__
---
apiVersion: barmancloud.cnpg.io/v1
kind: ObjectStore
metadata:
  name: japan-store
spec:
  retentionPolicy: "7d"
  configuration:
    destinationPath: https://__BACKUP_ACCOUNT__.blob.core.windows.net/cnpg
    azureCredentials:
      storageAccount:
        name: japan-store-key
        key: NAME
      storageKey:
        name: japan-store-key
        key: KEY
    wal:
      compression: gzip
---
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: db
spec:
  instances: 1
  imageName: ghcr.io/cloudnative-pg/postgresql:18
  storage:
    size: 5Gi
  postgresql:
    parameters:
      archive_timeout: "60s"
  plugins:
    - name: barman-cloud.cloudnative-pg.io
      isWALArchiver: true
      parameters:
        barmanObjectName: japan-store
        serverName: __SERVER__
