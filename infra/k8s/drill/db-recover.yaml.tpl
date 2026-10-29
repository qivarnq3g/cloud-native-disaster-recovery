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
  bootstrap:
    recovery:
      source: previous
      database: dr
      owner: dr
      secret:
        name: db-app-user
  externalClusters:
    - name: previous
      plugin:
        name: barman-cloud.cloudnative-pg.io
        parameters:
          barmanObjectName: japan-store
          serverName: __SOURCE_SERVER__
