# Cách ấm: cụm bản sao ở cụm dự phòng, liên tục đọc WAL của __SOURCE_SERVER__ từ kho sao lưu.
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: db
  namespace: dr-api
spec:
  instances: 1
  imageName: ghcr.io/cloudnative-pg/postgresql:18.6-minimal-trixie
  storage:
    size: 2Gi
  postgresql:
    parameters:
      archive_timeout: "60s"
  bootstrap:
    recovery:
      source: origin
      database: dr
      owner: dr
      secret:
        name: db-app-user
  replica:
    enabled: true
    source: origin
  externalClusters:
    - name: origin
      plugin:
        name: barman-cloud.cloudnative-pg.io
        parameters:
          barmanObjectName: backup-store
          serverName: __SOURCE_SERVER__
  plugins:
    - name: barman-cloud.cloudnative-pg.io
      isWALArchiver: true
      parameters:
        barmanObjectName: backup-store
        serverName: __SERVER__
