# Chart 12.2.1 là bản mới nhất (app 1.18.2); ghi đè image lên v1.18.4 như docs/versions.md.
image:
  tag: v1.18.4
upgradeCRDs: false
initContainers:
  - name: velero-plugin-for-aws
    image: docker.io/velero/velero-plugin-for-aws:v1.14.4
    volumeMounts:
      - mountPath: /target
        name: plugins
configuration:
  backupSyncPeriod: 10s
  backupStorageLocation:
    - name: default
      provider: aws
      bucket: velero
      config:
        region: us-east-1
        s3ForcePathStyle: "true"
        s3Url: http://dr-seaweedfs:8333
        checksumAlgorithm: ""
  volumeSnapshotLocation: []
snapshotsEnabled: false
deployNodeAgent: false
credentials:
  useSecret: true
  secretContents:
    cloud: |
      [default]
      aws_access_key_id=__ACCESS_KEY__
      aws_secret_access_key=__SECRET_KEY__
