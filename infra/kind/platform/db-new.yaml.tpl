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
    initdb:
      database: dr
      owner: dr
      secret:
        name: db-app-user
  plugins:
    - name: barman-cloud.cloudnative-pg.io
      isWALArchiver: true
      parameters:
        barmanObjectName: backup-store
        serverName: __SERVER__
