initContainers:
  - name: velero-plugin-for-microsoft-azure
    image: velero/velero-plugin-for-microsoft-azure:v1.14.4
    volumeMounts:
      - mountPath: /target
        name: plugins
configuration:
  backupStorageLocation:
    - name: default
      provider: azure
      bucket: velero
      config:
        storageAccount: __BACKUP_ACCOUNT__
        storageAccountKeyEnvVar: AZURE_STORAGE_ACCOUNT_ACCESS_KEY
        subscriptionId: __SUB__
        resourceGroup: rg-dr-backup
  volumeSnapshotLocation: []
snapshotsEnabled: false
deployNodeAgent: false
credentials:
  useSecret: true
  secretContents:
    cloud: |
      AZURE_STORAGE_ACCOUNT_ACCESS_KEY=__KEY__
      AZURE_CLOUD_NAME=AzurePublicCloud
