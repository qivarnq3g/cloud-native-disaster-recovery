#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose up -d --wait csdl azurite seaweedfs
KET_NOI="DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;"
az storage container create --name anh --connection-string "$KET_NOI" -o none
SAS="$(az storage container generate-sas --name anh --connection-string "$KET_NOI" --permissions r --expiry 2099-01-01T00:00Z -o tsv)"
for i in $(seq 1 30); do
  if docker compose exec -T seaweedfs sh -c 'echo "s3.bucket.create -name anh" | weed shell' >/dev/null 2>&1; then break; fi
  sleep 2
done
echo "AZURITE_SAS_DOC=$SAS"
