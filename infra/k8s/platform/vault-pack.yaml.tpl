apiVersion: batch/v1
kind: Job
metadata:
  name: __NAME__
  namespace: dr-api
  labels:
    app: vault-pack
spec:
  backoffLimit: 0
  ttlSecondsAfterFinished: 86400
  activeDeadlineSeconds: 1800
  template:
    metadata:
      labels:
        app: vault-pack
    spec:
      restartPolicy: Never
      initContainers:
        - name: dump
          image: ghcr.io/cloudnative-pg/postgresql:18.6-minimal-trixie
          command: ["pg_dump", "-Fc", "-h", "db-rw", "-U", "dr", "-d", "dr", "-f", "/work/db.dump"]
          env:
            - name: PGPASSWORD
              valueFrom:
                secretKeyRef:
                  name: db-app-user
                  key: password
          volumeMounts:
            - name: work
              mountPath: /work
      containers:
        - name: pack
          image: python:3.12-slim
          workingDir: /code
          command: ["python", "-m", "scripts.vault.pack", "--work", "/work"]
          env:
            - name: RECIPIENTS_FILE
              value: /code/scripts/vault/vault-recipients.txt
          envFrom:
            - configMapRef:
                name: vault-config
            - secretRef:
                name: vault-sas
          volumeMounts:
            - name: work
              mountPath: /work
            - name: code
              mountPath: /code/scripts/vault
              readOnly: true
      volumes:
        - name: work
          emptyDir:
            sizeLimit: 4Gi
        - name: code
          configMap:
            name: vault-code
