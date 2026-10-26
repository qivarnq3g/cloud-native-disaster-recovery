# Dựng cơ sở dữ liệu từ bản đầy đủ và WAL của __SOURCE_SERVER__, rồi ghi WAL mới vào __SERVER__.
# Không đặt thời điểm đích: CNPG đọc hết WAL có trong kho. Cụm cũ đã mất hoặc bị xóa nên WAL cuối cùng
# trong kho luôn có trước lúc sự cố; đặt thời điểm đích sau đoạn WAL đó thì Postgres dừng với lỗi.
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
