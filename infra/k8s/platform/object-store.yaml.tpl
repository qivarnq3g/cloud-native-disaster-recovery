apiVersion: barmancloud.cnpg.io/v1
kind: ObjectStore
metadata:
  name: japan-store
  namespace: dr-api
spec:
  retentionPolicy: "7d"
  configuration:
    destinationPath: https://__BACKUP_ACCOUNT__.blob.core.windows.net/cnpg
    azureCredentials:
      storageAccount:
        name: japan-store-sas
        key: ACCOUNT
      storageSasToken:
        name: japan-store-sas
        key: SAS
    wal:
      compression: gzip
    data:
      compression: gzip
