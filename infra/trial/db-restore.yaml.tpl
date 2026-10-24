apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: db-cold
spec:
  instances: 1
  imageName: ghcr.io/cloudnative-pg/postgresql:18
  storage:
    size: 5Gi
  bootstrap:
    recovery:
      source: primary
  externalClusters:
    - name: primary
      plugin:
        name: barman-cloud.cloudnative-pg.io
        parameters:
          barmanObjectName: japan-store
          serverName: __SERVER_PRIMARY__
