# Kế hoạch chạy thử trên Azure

> **Đã chạy 24/10/2026** (05:50-07:20 UTC), kết quả trong [`docs/trial-results.md`](../trial-results.md). Ba nhóm tài nguyên và ngân sách thử đã xóa, kiểm tra lại không còn. Còn Task 11 Step 3: xem chi phí ngày 25/10.

> **Cho người thực hiện (agent):** dùng superpowers:executing-plans hoặc superpowers:subagent-driven-development để làm theo từng task. Các bước dùng ô `- [ ]` để đánh dấu.
>
> **Chỉ chạy khi Quang đã cho phép tạo tài nguyên Azure.** Kế hoạch này tạo máy ảo và tài khoản lưu trữ thật. Ước tính dưới 1 USD cho một buổi khoảng 6 giờ.

**Goal:** trả lời các câu hỏi ở mục 8 của thiết kế chính bằng số đo thật, trước khi viết hạ tầng thật, để nếu câu trả lời nào là "không" thì sửa thiết kế sớm.

**Architecture:** dựng tạm hai máy ảo k3s ở `koreacentral` và các tài khoản lưu trữ ở `japanwest` bằng Azure CLI (không dùng Terraform, vì đây là đồ dùng một lần), cài CNPG, Barman Cloud Plugin, Velero, cert-manager bằng Helm và manifest chính thức, đo, ghi kết quả vào `docs/trial-results.md`, rồi xóa sạch.

**Tech Stack:** Azure CLI 2.89, k3s v1.37.1+k3s1, cert-manager v1.21.2, CloudNativePG 1.30.1, Barman Cloud Plugin v0.15.1, Velero v1.18.4 với plugin Azure v1.14.4, Helm 4, kubectl 1.36, Python 3 với `azure-storage-blob`.

**Spec:** [`docs/thiet-ke.md`](../thiet-ke.md) mục 1, 4, 6, 8; [`docs/thiet-ke-web.md`](../thiet-ke-web.md) mục 7.

## Global Constraints

- Chỉ tạo tài nguyên trong ba nhóm `rg-dr-trial-primary`, `rg-dr-trial-standby` (đều `koreacentral`) và `rg-dr-trial-japan` (`japanwest`). Không đụng nhóm tài nguyên nào khác trong tài khoản: tài khoản còn tài nguyên của một dự án khác.
- Máy ảo: `Standard_B2als_v2`, Ubuntu 24.04, ổ hệ điều hành P4 32 GB. Không bao giờ chạy cùng lúc quá hai máy (giới hạn 4 nhân).
- Phiên bản ghim như mục Tech Stack. Chứng chỉ chỉ xin từ máy chủ **staging** của Let's Encrypt.
- Khóa tài khoản lưu trữ, kubeconfig và khóa SSH nằm trong `~/.dr-trial/` và `~/.ssh/`, không bao giờ nằm trong kho Git. `.gitignore` đã chặn `kubeconfig*`, `*.key`, `.env*`.
- Mọi số đo ghi vào `data/trial/` (CSV) và tóm tắt trong `docs/trial-results.md`. Mốc thời gian theo UTC.
- Kết thúc buổi phải xóa cả ba nhóm tài nguyên và kiểm tra lại là đã xóa.

## Review Focus

- Quên xóa tài nguyên khi một bước lỗi giữa chừng: Task 11 phải chạy được độc lập, kể cả khi các task trước dở dang.
- Nhầm nhóm tài nguyên: mọi lệnh tạo hoặc xóa đều ghi rõ tên nhóm, không dùng nhóm mặc định của CLI.
- Lộ khóa: không dán khóa vào lệnh có ghi lịch sử của kho; đọc khóa từ tệp trong `~/.dr-trial/`.
- Cụm bản sao ghi WAL vào đường dẫn của cụm chính: mỗi cụm một `serverName` riêng, kiểm tra bằng cách liệt kê thư mục trong kho.
- Đo sai vì máy hết tín dụng CPU: ghi số tín dụng còn lại trước mỗi phép đo thời gian.

---

### Task 0: Chuẩn bị công cụ và biến môi trường

**Files:**
- Create: `scripts/trial/env.sh`
- Create: `docs/trial-results.md`
- Create: `data/trial/.gitkeep`

- [x] **Step 1: Cài Helm và kiểm tra công cụ**

```bash
winget install --id Helm.Helm --exact --silent
helm version --short
az version --query '"azure-cli"' -o tsv
kubectl version --client -o json | python -c "import sys,json; print(json.load(sys.stdin)['clientVersion']['gitVersion'])"
python -c "import sys; print(sys.version)"
```

Expected: Helm `v4.x`, azure-cli `2.89.x`, kubectl `v1.36.x`, Python 3.

- [x] **Step 2: Tạo khóa SSH riêng cho buổi thử**

```bash
mkdir -p ~/.dr-trial
[ -f ~/.ssh/dr_trial_ed25519 ] || ssh-keygen -t ed25519 -f ~/.ssh/dr_trial_ed25519 -N "" -C dr-trial
ls -l ~/.ssh/dr_trial_ed25519.pub
```

- [x] **Step 3: Viết tệp biến dùng chung**

`scripts/trial/env.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
export DAY="${DAY:-$(date -u +%m%d)}"
export SUFFIX="${SUFFIX:-$(cat ~/.dr-trial/suffix 2>/dev/null || true)}"
if [ -z "$SUFFIX" ]; then
  SUFFIX="$(python -c 'import secrets; print(secrets.token_hex(3))')"
  echo "$SUFFIX" > ~/.dr-trial/suffix
fi
export RG_PRIMARY=rg-dr-trial-primary
export RG_STANDBY=rg-dr-trial-standby
export RG_JAPAN=rg-dr-trial-japan
export CLUSTER_REGION=koreacentral
export STORAGE_REGION=japanwest
export BACKUP_ACCOUNT="drtrialbk${SUFFIX}"
export IMAGE_ACCOUNT_PRIMARY="drtrialimg${SUFFIX}"
export IMAGE_ACCOUNT_JAPAN="drtrialimgjp${SUFFIX}"
export DNS_PRIMARY="drtrial-primary-${SUFFIX}"
export DNS_STANDBY="drtrial-standby-${SUFFIX}"
export FQDN_PRIMARY="${DNS_PRIMARY}.${CLUSTER_REGION}.cloudapp.azure.com"
export FQDN_STANDBY="${DNS_STANDBY}.${CLUSTER_REGION}.cloudapp.azure.com"
export SSH_KEY=~/.ssh/dr_trial_ed25519
export PRIVATE_DIR=~/.dr-trial
export DATA_DIR="$(git rev-parse --show-toplevel)/data/trial"
export SERVER_PRIMARY="primary-${DAY}"
export SERVER_STANDBY="standby-${DAY}"
```

- [x] **Step 4: Tạo tệp kết quả**

`docs/trial-results.md`:

```markdown
# Kết quả chạy thử trên Azure

Ngày chạy: <điền khi chạy>. Kế hoạch: `docs/ke-hoach/2026-10-09-chay-thu-azure.md`.

| # | Câu hỏi (mục 8 thiết kế chính) | Kết quả đo | Quyết định |
|---|---|---|---|
| 1 | RAM của một cụm | | |
| 2 | Dung lượng WAL mỗi ngày | | |
| 3 | Thời gian chép ảnh Hàn Quốc sang Nhật | | |
| 4 | Thời gian dựng một cụm mới | | |
| 5 | iNET cho ủy quyền `api.dr` sang Azure DNS (bản ghi NS) | | |
| 6 | CNPG dựng cụm bản sao từ kho ở Nhật; đường dẫn WAL riêng mỗi cụm | | |
| 7 | Chứng chỉ khôi phục bằng Velero được dùng lại, không xin mới | | |
| 8 | GitHub gửi email khi workflow lỗi | | |
| 9 | Bản thu nhỏ vừa máy GitHub | | |
| 10 | Ngân sách Azure có tạo được trên tài khoản sinh viên | | |
| 11 | Thời gian tạo ảnh nhỏ AVIF trên B2als v2 (nếu API đã có) | | |
```

- [x] **Step 5: Commit**

```bash
mkdir -p data/trial && touch data/trial/.gitkeep
chmod +x scripts/trial/env.sh
git add scripts/trial/env.sh docs/trial-results.md data/trial/.gitkeep
git commit -m "Thêm biến và bảng kết quả cho buổi chạy thử Azure"
```

### Task 1: Ngân sách và nhóm tài nguyên thử

**Files:**
- Create: `infra/trial/budget.json`
- Modify: `docs/trial-results.md` (dòng 10)

- [x] **Step 1: Tạo ba nhóm tài nguyên**

```bash
source scripts/trial/env.sh
az group create -n "$RG_PRIMARY" -l "$CLUSTER_REGION" --tags project=dr-trial -o none
az group create -n "$RG_STANDBY" -l "$CLUSTER_REGION" --tags project=dr-trial -o none
az group create -n "$RG_JAPAN" -l "$STORAGE_REGION" --tags project=dr-trial -o none
az group list --query "[?tags.project=='dr-trial'].name" -o tsv
```

Expected: đúng ba tên `rg-dr-trial-*`.

- [x] **Step 2: Thử tạo ngân sách có cảnh báo email**

`infra/trial/budget.json`:

```json
{
  "properties": {
    "category": "Cost",
    "amount": 25,
    "timeGrain": "Monthly",
    "timePeriod": { "startDate": "2026-10-01T00:00:00Z", "endDate": "2026-12-31T00:00:00Z" },
    "filter": {
      "dimensions": { "name": "ResourceGroupName", "operator": "In", "values": ["rg-dr-trial-primary", "rg-dr-trial-standby", "rg-dr-trial-japan"] }
    },
    "notifications": {
      "half": { "enabled": true, "operator": "GreaterThan", "threshold": 50, "contactEmails": ["qivarnq3g@gmail.com"] },
      "eighty": { "enabled": true, "operator": "GreaterThan", "threshold": 80, "contactEmails": ["qivarnq3g@gmail.com"] },
      "full": { "enabled": true, "operator": "GreaterThan", "threshold": 100, "contactEmails": ["qivarnq3g@gmail.com"] }
    }
  }
}
```

```bash
SUB=$(az account show --query id -o tsv)
az rest --method put \
  --url "https://management.azure.com/subscriptions/$SUB/providers/Microsoft.Consumption/budgets/dr-trial?api-version=2023-05-01" \
  --body @infra/trial/budget.json --query "properties.amount"
```

Expected: `25`. Nếu lỗi vì loại tài khoản không hỗ trợ ngân sách, ghi nguyên văn mã lỗi vào dòng 10 của `docs/trial-results.md`; quyết định khi đó là "xem số dư thủ công mỗi tuần" (mục 7.2 thiết kế chính).

- [x] **Step 3: Ghi kết quả và commit**

```bash
git add infra/trial/budget.json docs/trial-results.md
git commit -m "Chạy thử: nhóm tài nguyên và ngân sách"
```

### Task 2: Dựng cụm chính và đo thời gian dựng

**Files:**
- Create: `infra/trial/cloud-init-k3s.yaml.tpl`
- Create: `scripts/trial/create-cluster.sh`
- Create: `data/trial/cluster-build.csv` (script tự ghi)

- [x] **Step 1: Mẫu cloud-init cài k3s**

`infra/trial/cloud-init-k3s.yaml.tpl`:

```yaml
#cloud-config
package_update: false
runcmd:
  - curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION="v1.37.1+k3s1" INSTALL_K3S_EXEC="server --write-kubeconfig-mode=600 --tls-san=__FQDN__" sh -
```

- [x] **Step 2: Script dựng cụm có ghi mốc thời gian**

`scripts/trial/create-cluster.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/env.sh"
NAME="$1"; RG="$2"; DNS="$3"; FQDN="$4"
MY_IP="$(curl -s https://api.ipify.org)"
CI="$PRIVATE_DIR/cloud-init-$NAME.yaml"
sed "s/__FQDN__/$FQDN/" infra/trial/cloud-init-k3s.yaml.tpl > "$CI"
mark() { echo "$NAME,$1,$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$DATA_DIR/cluster-build.csv"; }
[ -f "$DATA_DIR/cluster-build.csv" ] || echo "cluster,mark,time_utc" > "$DATA_DIR/cluster-build.csv"
mark start
az vm create -g "$RG" -n "vm-$NAME" -l "$CLUSTER_REGION" --image Ubuntu2404 --size Standard_B2als_v2 \
  --admin-username dr --ssh-key-values "$SSH_KEY.pub" --public-ip-sku Standard \
  --public-ip-address-dns-name "$DNS" --custom-data "$CI" --nsg-rule NONE \
  --os-disk-size-gb 32 --storage-sku Premium_LRS -o none
mark vm_created
az network nsg rule create -g "$RG" --nsg-name "vm-${NAME}NSG" -n admin --priority 100 \
  --source-address-prefixes "$MY_IP/32" --destination-port-ranges 22 6443 --access Allow --protocol Tcp -o none
az network nsg rule create -g "$RG" --nsg-name "vm-${NAME}NSG" -n web --priority 110 \
  --source-address-prefixes Internet --destination-port-ranges 80 443 --access Allow --protocol Tcp -o none
until ssh -i "$SSH_KEY" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=5 "dr@$FQDN" 'sudo test -f /etc/rancher/k3s/k3s.yaml' 2>/dev/null; do sleep 5; done
mark k3s_installed
ssh -i "$SSH_KEY" "dr@$FQDN" 'sudo cat /etc/rancher/k3s/k3s.yaml' | sed "s/127.0.0.1/$FQDN/" > "$PRIVATE_DIR/kubeconfig-$NAME"
export KUBECONFIG="$PRIVATE_DIR/kubeconfig-$NAME"
until kubectl wait --for=condition=Ready node --all --timeout=10s >/dev/null 2>&1; do sleep 5; done
mark node_ready
until kubectl -n kube-system rollout status deploy/traefik --timeout=10s >/dev/null 2>&1; do sleep 5; done
mark traefik_ready
```

- [x] **Step 3: Chạy cho cụm chính**

```bash
chmod +x scripts/trial/create-cluster.sh
source scripts/trial/env.sh
scripts/trial/create-cluster.sh primary "$RG_PRIMARY" "$DNS_PRIMARY" "$FQDN_PRIMARY"
KUBECONFIG=~/.dr-trial/kubeconfig-primary kubectl get nodes -o wide
cat data/trial/cluster-build.csv
```

Expected: một nút `Ready`; CSV có 5 mốc. Thời gian dựng = `traefik_ready - start`.

- [x] **Step 4: Ghi tín dụng CPU lúc bắt đầu**

```bash
VM_ID=$(az vm show -g "$RG_PRIMARY" -n vm-primary --query id -o tsv)
az monitor metrics list --resource "$VM_ID" --metric "CPU Credits Remaining" --interval PT5M --query "value[0].timeseries[0].data[-1].average" -o tsv
```

Ghi số này cạnh thời gian dựng ở dòng 4 của `docs/trial-results.md`.

- [x] **Step 5: Commit**

```bash
git add infra/trial/cloud-init-k3s.yaml.tpl scripts/trial/create-cluster.sh data/trial/cluster-build.csv docs/trial-results.md
git commit -m "Chạy thử: dựng cụm chính, đo thời gian"
```

### Task 3: Tài khoản lưu trữ và đo thời gian chép ảnh

**Files:**
- Create: `scripts/trial/create-storage.sh`
- Create: `scripts/trial/measure-image-replication.py`
- Create: `data/trial/image-replication.csv` (script tự ghi)

- [x] **Step 1: Tạo ba tài khoản lưu trữ và bật phiên bản, change feed, chép ảnh**

`scripts/trial/create-storage.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/env.sh"
create() {
  az storage account create -n "$1" -g "$2" -l "$3" --sku Standard_LRS --kind StorageV2 \
    --min-tls-version TLS1_2 --allow-blob-public-access false -o none
  az storage account keys list -n "$1" -g "$2" --query "[0].value" -o tsv > "$PRIVATE_DIR/key-$1"
}
create "$BACKUP_ACCOUNT" "$RG_JAPAN" "$STORAGE_REGION"
create "$IMAGE_ACCOUNT_PRIMARY" "$RG_PRIMARY" "$CLUSTER_REGION"
create "$IMAGE_ACCOUNT_JAPAN" "$RG_JAPAN" "$STORAGE_REGION"
az storage account blob-service-properties update -n "$IMAGE_ACCOUNT_PRIMARY" -g "$RG_PRIMARY" --enable-versioning true --enable-change-feed true -o none
az storage account blob-service-properties update -n "$IMAGE_ACCOUNT_JAPAN" -g "$RG_JAPAN" --enable-versioning true -o none
for c in cnpg velero; do
  az storage container create -n "$c" --account-name "$BACKUP_ACCOUNT" --account-key "$(cat "$PRIVATE_DIR/key-$BACKUP_ACCOUNT")" -o none
done
az storage container create -n images --account-name "$IMAGE_ACCOUNT_PRIMARY" --account-key "$(cat "$PRIVATE_DIR/key-$IMAGE_ACCOUNT_PRIMARY")" -o none
az storage container create -n images --account-name "$IMAGE_ACCOUNT_JAPAN" --account-key "$(cat "$PRIVATE_DIR/key-$IMAGE_ACCOUNT_JAPAN")" -o none
SOURCE_ID=$(az storage account show -n "$IMAGE_ACCOUNT_PRIMARY" -g "$RG_PRIMARY" --query id -o tsv)
DEST_ID=$(az storage account show -n "$IMAGE_ACCOUNT_JAPAN" -g "$RG_JAPAN" --query id -o tsv)
MSYS_NO_PATHCONV=1 az storage account or-policy create -g "$RG_JAPAN" -n "$IMAGE_ACCOUNT_JAPAN" \
  --source-account "$SOURCE_ID" --destination-account "$DEST_ID" \
  --source-container images --destination-container images -o json > "$PRIVATE_DIR/or-policy.json"
MSYS_NO_PATHCONV=1 az storage account or-policy create -g "$RG_PRIMARY" -n "$IMAGE_ACCOUNT_PRIMARY" --policy "@$(cygpath -m "$PRIVATE_DIR/or-policy.json")" -o none
az storage account or-policy list -g "$RG_PRIMARY" -n "$IMAGE_ACCOUNT_PRIMARY" --query "[].rules[].sourceContainer" -o tsv
```

```bash
chmod +x scripts/trial/create-storage.sh && scripts/trial/create-storage.sh
```

Expected: dòng cuối in `images`.

- [x] **Step 2: Script đo độ trễ chép ảnh**

`scripts/trial/measure-image-replication.py`:

```python
import csv
import os
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from azure.core.exceptions import ResourceNotFoundError
from azure.storage.blob import BlobServiceClient

PRIVATE_DIR = Path.home() / ".dr-trial"
SOURCE = os.environ["IMAGE_ACCOUNT_PRIMARY"]
DEST = os.environ["IMAGE_ACCOUNT_JAPAN"]
COUNT = int(sys.argv[1]) if len(sys.argv) > 1 else 200
SIZE = 200 * 1024
TIMEOUT = 1800
OUT = Path(os.environ["DATA_DIR"]) / "image-replication.csv"


def client(account):
    key = (PRIVATE_DIR / f"key-{account}").read_text().strip()
    return BlobServiceClient(f"https://{account}.blob.core.windows.net", credential=key).get_container_client("images")


def utc(t):
    return datetime.fromtimestamp(t, timezone.utc).isoformat()


def watch(dest, name, sent_at, results, lock):
    while time.time() - sent_at < TIMEOUT:
        try:
            dest.get_blob_client(name).get_blob_properties()
            with lock:
                results.append((name, utc(sent_at), utc(time.time()), round(time.time() - sent_at, 1)))
            return
        except ResourceNotFoundError:
            time.sleep(2)
    with lock:
        results.append((name, utc(sent_at), "", ""))


def main():
    source, dest = client(SOURCE), client(DEST)
    results, lock, threads = [], threading.Lock(), []
    for i in range(COUNT):
        name = f"trial/{int(time.time())}-{i:04d}.bin"
        sent_at = time.time()
        source.upload_blob(name, os.urandom(SIZE))
        t = threading.Thread(target=watch, args=(dest, name, sent_at, results, lock))
        t.start()
        threads.append(t)
        time.sleep(max(0.0, 1.0 - (time.time() - sent_at)))
    for t in threads:
        t.join()
    with OUT.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["blob", "sent_utc", "in_japan_utc", "lag_s"])
        w.writerows(sorted(results))
    lags = sorted(r[3] for r in results if r[3] != "")
    missing = sum(1 for r in results if r[3] == "")
    if lags:
        print(f"n={len(lags)} missing={missing} median={lags[len(lags)//2]} p95={lags[int(len(lags)*0.95)-1]} max={lags[-1]}")
    else:
        print(f"no image reached Japan within {TIMEOUT} seconds")


if __name__ == "__main__":
    main()
```

- [x] **Step 3: Chạy đo 200 ảnh**

```bash
python -m venv ~/.dr-trial/venv
~/.dr-trial/venv/Scripts/python -m pip install -q "azure-storage-blob==12.*"
source scripts/trial/env.sh
~/.dr-trial/venv/Scripts/python scripts/trial/measure-image-replication.py 200
```

Expected: một dòng `n=… missing=… median=… p95=… max=…`. Ghi vào dòng 3 của `docs/trial-results.md`. Quyết định: RPO của ảnh trong mục 3 thiết kế chính đặt không thấp hơn p95 đo được.

- [x] **Step 4: Commit**

```bash
git add scripts/trial/create-storage.sh scripts/trial/measure-image-replication.py data/trial/image-replication.csv docs/trial-results.md
git commit -m "Chạy thử: kho lưu trữ, đo độ trễ chép ảnh sang Nhật"
```

### Task 4: Cài phần mềm vào cụm chính và đo RAM

**Files:**
- Create: `infra/trial/velero-values.yaml.tpl`
- Create: `infra/trial/db-primary.yaml.tpl`
- Create: `infra/trial/load-test.yaml`
- Create: `scripts/trial/install-software.sh`

- [x] **Step 1: Mẫu cấu hình Velero**

`infra/trial/velero-values.yaml.tpl`:

```yaml
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
        resourceGroup: rg-dr-trial-japan
  volumeSnapshotLocation: []
snapshotsEnabled: false
deployNodeAgent: false
credentials:
  useSecret: true
  secretContents:
    cloud: |
      AZURE_STORAGE_ACCOUNT_ACCESS_KEY=__KEY__
      AZURE_CLOUD_NAME=AzurePublicCloud
```

- [x] **Step 2: Mẫu cơ sở dữ liệu có gửi WAL sang Nhật**

`infra/trial/db-primary.yaml.tpl`:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: japan-store-key
type: Opaque
stringData:
  NAME: __BACKUP_ACCOUNT__
  KEY: __KEY__
---
apiVersion: barmancloud.cnpg.io/v1
kind: ObjectStore
metadata:
  name: japan-store
spec:
  retentionPolicy: "7d"
  configuration:
    destinationPath: https://__BACKUP_ACCOUNT__.blob.core.windows.net/cnpg
    azureCredentials:
      storageAccount:
        name: japan-store-key
        key: NAME
      storageKey:
        name: japan-store-key
        key: KEY
    wal:
      compression: gzip
---
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: db
spec:
  instances: 1
  imageName: ghcr.io/cloudnative-pg/postgresql:18
  storage:
    size: 5Gi
  postgresql:
    parameters:
      archive_timeout: "60s"
  plugins:
    - name: barman-cloud.cloudnative-pg.io
      isWALArchiver: true
      parameters:
        barmanObjectName: japan-store
        serverName: __SERVER__
```

- [x] **Step 3: Tải giả lập 1 bài mỗi giây trong 1 giờ**

`infra/trial/load-test.yaml`:

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: load-test
spec:
  backoffLimit: 0
  template:
    spec:
      restartPolicy: Never
      containers:
        - name: psql
          image: ghcr.io/cloudnative-pg/postgresql:18
          env:
            - name: URI
              valueFrom:
                secretKeyRef:
                  name: db-app
                  key: uri
          command:
            - bash
            - -c
            - |
              psql "$URI" -qc "CREATE TABLE IF NOT EXISTS trial_posts(id bigserial PRIMARY KEY, content text, created_at timestamptz DEFAULT now())"
              for i in $(seq 1 3600); do
                psql "$URI" -qc "INSERT INTO trial_posts(content) VALUES (repeat(md5(random()::text), 10))"
                sleep 1
              done
```

- [x] **Step 4: Script cài phần mềm vào một cụm**

`scripts/trial/install-software.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/env.sh"
NAME="$1"
export KUBECONFIG="$PRIVATE_DIR/kubeconfig-$NAME"
KEY="$(cat "$PRIVATE_DIR/key-$BACKUP_ACCOUNT")"
SUB="$(az account show --query id -o tsv)"
helm repo add jetstack https://charts.jetstack.io --force-update >/dev/null
helm repo add cnpg https://cloudnative-pg.github.io/charts --force-update >/dev/null
helm repo add vmware-tanzu https://vmware-tanzu.github.io/helm-charts --force-update >/dev/null
helm upgrade --install cert-manager jetstack/cert-manager -n cert-manager --create-namespace \
  --version v1.21.2 --set crds.enabled=true --wait
CHART_CNPG="$(helm search repo cnpg/cloudnative-pg --versions -o json | python -c "import sys,json; print(next(c['version'] for c in json.load(sys.stdin) if c['app_version']=='1.30.1'))")"
helm upgrade --install cnpg cnpg/cloudnative-pg -n cnpg-system --create-namespace --version "$CHART_CNPG" --wait
kubectl apply -f https://github.com/cloudnative-pg/plugin-barman-cloud/releases/download/v0.15.1/manifest.yaml
kubectl -n cnpg-system rollout status deploy/barman-cloud --timeout=300s
sed -e "s/__BACKUP_ACCOUNT__/$BACKUP_ACCOUNT/" -e "s/__SUB__/$SUB/" -e "s|__KEY__|$KEY|" \
  infra/trial/velero-values.yaml.tpl > "$PRIVATE_DIR/velero-values-$NAME.yaml"
helm upgrade --install velero vmware-tanzu/velero -n velero --create-namespace \
  -f "$PRIVATE_DIR/velero-values-$NAME.yaml" --wait
kubectl -n velero get backupstoragelocation default -o jsonpath='{.status.phase}{"\n"}'
```

- [x] **Step 5: Cài, dựng cơ sở dữ liệu, đo RAM lúc rảnh**

```bash
chmod +x scripts/trial/install-software.sh
source scripts/trial/env.sh
scripts/trial/install-software.sh primary
export KUBECONFIG=~/.dr-trial/kubeconfig-primary
sed -e "s/__BACKUP_ACCOUNT__/$BACKUP_ACCOUNT/g" -e "s|__KEY__|$(cat ~/.dr-trial/key-$BACKUP_ACCOUNT)|" -e "s/__SERVER__/$SERVER_PRIMARY/" \
  infra/trial/db-primary.yaml.tpl | kubectl apply -f -
kubectl wait --for=condition=Ready cluster/db --timeout=600s
ssh -i "$SSH_KEY" "dr@$FQDN_PRIMARY" free -m
kubectl top pods -A --sort-by=memory | head -15
```

Expected: `Available` của BackupStorageLocation; cluster `db` Ready; ghi `used` của `free -m` (rảnh).

- [x] **Step 6: Chạy tải 1 giờ, đo RAM đỉnh và dung lượng WAL**

```bash
kubectl apply -f infra/trial/load-test.yaml
for i in $(seq 1 12); do
  ssh -i "$SSH_KEY" "dr@$FQDN_PRIMARY" "free -m | awk '/Mem:/{print \$3}'" | sed "s/^/$(date -u +%H:%M:%S),/" >> "$DATA_DIR/ram-primary.csv"
  sleep 300
done
KEY="$(cat ~/.dr-trial/key-$BACKUP_ACCOUNT)"
az storage blob list --account-name "$BACKUP_ACCOUNT" --account-key "$KEY" -c cnpg --prefix "$SERVER_PRIMARY/wals/" \
  --num-results 100000 --query "[length(@), sum([].properties.contentLength)]" -o tsv
```

Expected: hai số: số tệp WAL và tổng byte trong khoảng 1 giờ. WAL mỗi ngày = tổng byte × 24. Ghi RAM đỉnh (`max` của `ram-primary.csv`) vào dòng 1, WAL vào dòng 2.

Quyết định:
- RAM đỉnh trên 80% của 4 GB (khoảng 3.200 MB dùng) thì đổi sang B2as v2 (mục 8 thiết kế chính).
- WAL mỗi ngày trên 2 GB thì đặt `bootstrap.initdb.walSegmentSize: 1` (MB) cho cụm thật và đo lại ở bản thu nhỏ.

- [x] **Step 7: Commit**

```bash
git add infra/trial scripts/trial/install-software.sh data/trial/ram-primary.csv docs/trial-results.md
git commit -m "Chạy thử: cài phần mềm, đo RAM và dung lượng WAL"
```

### Task 5: Chứng chỉ staging và sao lưu Velero ở cụm chính

**Files:**
- Create: `infra/trial/tls-test.yaml.tpl`

- [x] **Step 1: Mẫu dịch vụ thử có chứng chỉ staging**

`infra/trial/tls-test.yaml.tpl`:

```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: le-staging
spec:
  acme:
    server: https://acme-staging-v02.api.letsencrypt.org/directory
    email: qivarnq3g@gmail.com
    privateKeySecretRef:
      name: le-staging-key
    solvers:
      - http01:
          ingress:
            ingressClassName: traefik
---
apiVersion: v1
kind: Namespace
metadata:
  name: tls-test
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: whoami
  namespace: tls-test
spec:
  replicas: 1
  selector:
    matchLabels: { app: whoami }
  template:
    metadata:
      labels: { app: whoami }
    spec:
      containers:
        - name: whoami
          image: traefik/whoami:v1.11
          ports: [{ containerPort: 80 }]
---
apiVersion: v1
kind: Service
metadata:
  name: whoami
  namespace: tls-test
spec:
  selector: { app: whoami }
  ports: [{ port: 80, targetPort: 80 }]
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: whoami
  namespace: tls-test
  annotations:
    cert-manager.io/cluster-issuer: le-staging
spec:
  ingressClassName: traefik
  tls:
    - hosts: [__HOST__]
      secretName: whoami-tls
  rules:
    - host: __HOST__
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service: { name: whoami, port: { number: 80 } }
```

- [x] **Step 2: Xin chứng chỉ và sao lưu**

```bash
source scripts/trial/env.sh
export KUBECONFIG=~/.dr-trial/kubeconfig-primary
sed "s/__HOST__/$FQDN_PRIMARY/g" infra/trial/tls-test.yaml.tpl | kubectl apply -f -
kubectl -n tls-test wait --for=condition=Ready certificate/whoami-tls --timeout=600s
kubectl -n tls-test get secret whoami-tls -o jsonpath='{.data.tls\.crt}' | base64 -d | openssl x509 -noout -serial -issuer
kubectl -n velero create -f - <<EOF
apiVersion: velero.io/v1
kind: Backup
metadata:
  name: tls-test-1
spec:
  includedNamespaces: [tls-test]
  storageLocation: default
  ttl: 72h0m0s
EOF
kubectl -n velero wait --for=jsonpath='{.status.phase}'=Completed backups.velero.io/tls-test-1 --timeout=600s
```

Expected: serial và issuer có chữ `STAGING`; backup `Completed`. Ghi serial lại để so ở Task 6.

### Task 6: Cụm dự phòng: bản sao CNPG, đổi vai, khôi phục lạnh, khôi phục chứng chỉ

**Files:**
- Create: `infra/trial/db-replica.yaml.tpl`
- Create: `infra/trial/db-restore.yaml.tpl`

- [x] **Step 1: Sao lưu đầy đủ đầu tiên ở cụm chính**

```bash
export KUBECONFIG=~/.dr-trial/kubeconfig-primary
kubectl create -f - <<EOF
apiVersion: postgresql.cnpg.io/v1
kind: Backup
metadata:
  name: first
spec:
  cluster:
    name: db
  method: plugin
  pluginConfiguration:
    name: barman-cloud.cloudnative-pg.io
EOF
kubectl wait --for=jsonpath='{.status.phase}'=completed backups.postgresql.cnpg.io/first --timeout=900s
```

- [x] **Step 2: Dựng cụm dự phòng và cài phần mềm (đo thời gian như cụm chính)**

```bash
source scripts/trial/env.sh
scripts/trial/create-cluster.sh standby "$RG_STANDBY" "$DNS_STANDBY" "$FQDN_STANDBY"
scripts/trial/install-software.sh standby
```

- [x] **Step 3: Mẫu cụm bản sao đọc WAL từ Nhật**

`infra/trial/db-replica.yaml.tpl`:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: japan-store-key
type: Opaque
stringData:
  NAME: __BACKUP_ACCOUNT__
  KEY: __KEY__
---
apiVersion: barmancloud.cnpg.io/v1
kind: ObjectStore
metadata:
  name: japan-store
spec:
  retentionPolicy: "7d"
  configuration:
    destinationPath: https://__BACKUP_ACCOUNT__.blob.core.windows.net/cnpg
    azureCredentials:
      storageAccount:
        name: japan-store-key
        key: NAME
      storageKey:
        name: japan-store-key
        key: KEY
    wal:
      compression: gzip
---
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: db
spec:
  instances: 1
  imageName: ghcr.io/cloudnative-pg/postgresql:18
  storage:
    size: 5Gi
  bootstrap:
    recovery:
      source: primary
  replica:
    enabled: true
    source: primary
  externalClusters:
    - name: primary
      plugin:
        name: barman-cloud.cloudnative-pg.io
        parameters:
          barmanObjectName: japan-store
          serverName: __SERVER_PRIMARY__
  plugins:
    - name: barman-cloud.cloudnative-pg.io
      isWALArchiver: true
      parameters:
        barmanObjectName: japan-store
        serverName: __SERVER_STANDBY__
```

- [x] **Step 4: Dựng bản sao, đo độ trễ theo kịp**

```bash
export KUBECONFIG=~/.dr-trial/kubeconfig-standby
sed -e "s/__BACKUP_ACCOUNT__/$BACKUP_ACCOUNT/g" -e "s|__KEY__|$(cat ~/.dr-trial/key-$BACKUP_ACCOUNT)|" \
  -e "s/__SERVER_PRIMARY__/$SERVER_PRIMARY/" -e "s/__SERVER_STANDBY__/$SERVER_STANDBY/" \
  infra/trial/db-replica.yaml.tpl | kubectl apply -f -
kubectl wait --for=condition=Ready cluster/db --timeout=1200s
MARK="mark-$(date -u +%s)"
KUBECONFIG=~/.dr-trial/kubeconfig-primary kubectl exec db-1 -c postgres -- psql -d app -qc "INSERT INTO trial_posts(content) VALUES ('$MARK')"
T0=$(date -u +%s)
until kubectl exec db-1 -c postgres -- psql -d app -tAc "SELECT count(*) FROM trial_posts WHERE content='$MARK'" | grep -q 1; do sleep 2; done
echo "replica_lag_s=$(( $(date -u +%s) - T0 ))"
az storage blob list --account-name "$BACKUP_ACCOUNT" --account-key "$(cat ~/.dr-trial/key-$BACKUP_ACCOUNT)" -c cnpg \
  --delimiter / --query "[].name" -o tsv
```

Expected: bản sao Ready; độ trễ dưới khoảng 2 phút (archive_timeout 60 giây cộng thời gian đọc); danh sách thư mục trong `cnpg` có `$SERVER_PRIMARY/` và **không** có tệp WAL mới nào của cụm dự phòng ghi vào thư mục `$SERVER_PRIMARY/`. Ghi vào dòng 6.

- [x] **Step 5: Đổi vai bản sao thành chính, đo thời gian**

```bash
T0=$(date -u +%s)
kubectl patch cluster db --type merge -p '{"spec":{"replica":{"enabled":false}}}'
until kubectl exec db-1 -c postgres -- psql -d app -tAc "SELECT pg_is_in_recovery()" | grep -q f; do sleep 2; done
echo "promote_s=$(( $(date -u +%s) - T0 ))"
kubectl exec db-1 -c postgres -- psql -d app -qc "INSERT INTO trial_posts(content) VALUES ('after-promote')"
```

Expected: ghi được sau khi đổi vai; ghi thời gian vào dòng 6.

- [x] **Step 6: Mẫu khôi phục lạnh và đo thời gian**

`infra/trial/db-restore.yaml.tpl`:

```yaml
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
```

```bash
T0=$(date -u +%s)
sed "s/__SERVER_PRIMARY__/$SERVER_PRIMARY/" infra/trial/db-restore.yaml.tpl | kubectl apply -f -
kubectl wait --for=condition=Ready cluster/db-cold --timeout=1800s
echo "cold_restore_s=$(( $(date -u +%s) - T0 ))"
kubectl exec db-cold-1 -c postgres -- psql -d app -tAc "SELECT count(*), max(created_at) FROM trial_posts"
```

Expected: số dòng và `max(created_at)` cách lúc chạy lệnh không quá vài phút; ghi thời gian khôi phục vào dòng 6.

- [x] **Step 7: Khôi phục chứng chỉ bằng Velero ở cụm dự phòng**

```bash
export KUBECONFIG=~/.dr-trial/kubeconfig-standby
source scripts/trial/env.sh
sed "s/__HOST__/$FQDN_PRIMARY/g" infra/trial/tls-test.yaml.tpl | python -c "import sys; d=sys.stdin.read().split('\n---\n'); print(d[0])" | kubectl apply -f -
kubectl -n velero wait --for=jsonpath='{.status.phase}'=Available backupstoragelocations.velero.io/default --timeout=300s
kubectl -n velero create -f - <<EOF
apiVersion: velero.io/v1
kind: Restore
metadata:
  name: tls-test-1
spec:
  backupName: tls-test-1
EOF
kubectl -n velero wait --for=jsonpath='{.status.phase}'=Completed restores.velero.io/tls-test-1 --timeout=600s
kubectl -n tls-test get secret whoami-tls -o jsonpath='{.data.tls\.crt}' | base64 -d | openssl x509 -noout -serial
sleep 600
kubectl -n tls-test get certificaterequest --no-headers | wc -l
kubectl -n tls-test get certificate whoami-tls -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}{"\n"}'
```

Expected: serial giống hệt serial ở Task 5; sau 10 phút số CertificateRequest ở cụm dự phòng là `0` hoặc chỉ có bản được khôi phục, và Certificate `True`. Ghi vào dòng 7. Nếu cert-manager xin chứng chỉ mới thì quyết định: khi khôi phục, tắt cert-manager cho tới khi Secret đã về, và ghi vào runbook.

- [x] **Step 8: Commit**

```bash
git add infra/trial/db-replica.yaml.tpl infra/trial/db-restore.yaml.tpl docs/trial-results.md data/trial/cluster-build.csv
git commit -m "Chạy thử: bản sao, đổi vai, khôi phục lạnh, khôi phục chứng chỉ"
```

### Task 7: Ủy quyền DNS `api.dr` trên iNET (chỉ xem, không tạo)

**Files:**
- Modify: `docs/trial-results.md` (dòng 5)

- [x] **Step 1: Xem trang quản lý DNS của `qivarn.id.vn` bằng Edge của Quang (Claude in Chrome)**

Mở trang quản lý bản ghi của tên miền trong iNET OnePortal. Kiểm tra danh sách loại bản ghi có `NS` và cho phép tên `api.dr` không. Không bấm lưu, không tạo bản ghi.

Expected: một trong hai: có `NS` cho tên con, hoặc không. Ghi vào dòng 5 kèm ảnh chụp lưu trong `personal/Minh-chung/` (ngoài kho). Nếu không có `NS`: quyết định đổi bản ghi A của `api.dr` trên iNET bằng tay khi chuyển cụm, thời gian ghi nhớ 60 giây (mục 8 thiết kế chính), và tính bước này vào thời gian chuyển lưu lượng.

### Task 8: GitHub có gửi email khi workflow lỗi

Hai workflow thử ở Task 8 và 9 chạy khi đẩy nhánh thử, không dùng `workflow_dispatch`: GitHub chỉ cho chạy bằng tay workflow đã có trên nhánh mặc định.

**Files:**
- Create: `.github/workflows/fail-test.yml` (xóa ở Step 3)

- [x] **Step 1: Workflow cố ý lỗi, chỉ chạy bằng tay**

`.github/workflows/fail-test.yml`:

```yaml
name: fail-test
on:
  push:
    branches: [trial/fail-email]
jobs:
  fail:
    runs-on: ubuntu-latest
    steps:
      - run: exit 1
```

- [x] **Step 2: Chạy và nhờ Quang xem hộp thư**

```bash
git checkout -b trial/fail-email
git add .github/workflows/fail-test.yml
git commit -m "Thử email khi workflow lỗi"
git push -u origin trial/fail-email
sleep 60
gh run list --workflow fail-test.yml --limit 1 --json conclusion,createdAt
```

Expected: `conclusion` là `failure`. Quang kiểm tra hộp thư `qivarnq3g@gmail.com` có thư "Run failed" của GitHub. Ghi vào dòng 8.

- [x] **Step 3: Dọn nhánh thử**

```bash
git checkout main
git push origin --delete trial/fail-email
git branch -D trial/fail-email
```

### Task 9: Bản thu nhỏ có vừa máy GitHub không

**Files:**
- Create: `.github/workflows/kind-test.yml` (xóa ở Step 3)

- [x] **Step 1: Workflow dựng hai cụm kind và đo tài nguyên**

`.github/workflows/kind-test.yml`:

```yaml
name: kind-test
on:
  push:
    branches: [trial/kind]
jobs:
  measure:
    runs-on: ubuntu-latest
    timeout-minutes: 60
    steps:
      - name: Cài kind và helm
        run: |
          curl -fsSLo kind https://kind.sigs.k8s.io/dl/v0.33.0/kind-linux-amd64
          chmod +x kind && sudo mv kind /usr/local/bin/kind
          curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-4 | bash
      - name: Hai cụm kind
        run: |
          kind create cluster --name primary --wait 300s
          kind create cluster --name standby --wait 300s
      - name: SeaweedFS
        run: docker run -d --name seaweedfs --network kind -p 8333:8333 chrislusf/seaweedfs:4.48 server -s3
      - name: Phần mềm vào hai cụm
        run: |
          helm repo add jetstack https://charts.jetstack.io
          helm repo add cnpg https://cloudnative-pg.github.io/charts
          helm repo add vmware-tanzu https://vmware-tanzu.github.io/helm-charts
          for c in primary standby; do
            kubectl config use-context kind-$c
            helm install cert-manager jetstack/cert-manager -n cert-manager --create-namespace --version v1.21.2 --set crds.enabled=true --wait
            helm install cnpg cnpg/cloudnative-pg -n cnpg-system --create-namespace --wait
            kubectl apply -f https://github.com/cloudnative-pg/plugin-barman-cloud/releases/download/v0.15.1/manifest.yaml
            kubectl -n cnpg-system rollout status deploy/barman-cloud --timeout=300s
            helm install velero vmware-tanzu/velero -n velero --create-namespace --set snapshotsEnabled=false --set deployNodeAgent=false --set configuration.backupStorageLocation=null --set configuration.volumeSnapshotLocation=null
            kubectl apply -f - <<EOF
          apiVersion: postgresql.cnpg.io/v1
          kind: Cluster
          metadata:
            name: db
          spec:
            instances: 1
            imageName: ghcr.io/cloudnative-pg/postgresql:18
            storage:
              size: 2Gi
          EOF
            kubectl wait --for=condition=Ready cluster/db --timeout=600s
          done
      - name: Đo
        run: |
          free -m
          df -h /
          docker system df
          nproc
```

- [x] **Step 2: Chạy và đọc kết quả**

```bash
git checkout -b trial/kind
git add .github/workflows/kind-test.yml
git commit -m "Thử bản thu nhỏ trên máy GitHub"
git push -u origin trial/kind
gh run watch "$(gh run list --workflow kind-test.yml --limit 1 --json databaseId -q '.[0].databaseId')" --exit-status
gh run view --log "$(gh run list --workflow kind-test.yml --limit 1 --json databaseId -q '.[0].databaseId')" | grep -A20 "Đo"
```

Expected: workflow thành công; `free -m` còn trên 4 GB trống, `df -h /` còn trên 3 GB. Ghi vào dòng 9. Nếu thiếu: quyết định chạy bản thu nhỏ với một cụm kind và đổi vai trong cùng cụm, ghi vào mục 6.4 thiết kế chính.

- [x] **Step 3: Dọn nhánh thử**

```bash
git checkout main
git push origin --delete trial/kind
git branch -D trial/kind
```

### Task 10: Thời gian tạo ảnh nhỏ AVIF trên B2als v2 (chỉ khi API đã có)

Bỏ qua task này nếu kế hoạch API (`docs/ke-hoach/2026-10-09-api.md`) chưa làm tới Task 6 (ví dụ `bench-thumbnail`).

- [x] **Step 1: Biên dịch ví dụ đo và chạy trên máy ảo**

```bash
source scripts/trial/env.sh
MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd -W)/app/api:/src" -w /src rust:1.97.1-alpine \
  sh -c 'apk add --no-cache build-base nasm >/dev/null && cargo build --release --features production --example bench-thumbnail --target-dir /src/target-musl'
scp -i "$SSH_KEY" app/api/target-musl/release/examples/bench-thumbnail "dr@$FQDN_PRIMARY:/tmp/"
ssh -i "$SSH_KEY" "dr@$FQDN_PRIMARY" "chmod +x /tmp/bench-thumbnail && /tmp/bench-thumbnail 50"
```

Expected: dòng `n=50 median_ms=… p95_ms=…`. Ghi vào dòng 11. Ngưỡng: p95 không quá 500 ms; vượt thì đổi ảnh nhỏ sang WebP (mục 7 thiết kế web).

### Task 11: Dọn sạch

Chạy được độc lập với các task trước.

- [x] **Step 1: Xóa ba nhóm tài nguyên và đợi xong**

```bash
source scripts/trial/env.sh
for rg in "$RG_PRIMARY" "$RG_STANDBY" "$RG_JAPAN"; do
  az group exists -n "$rg" | grep -q true && az group delete -n "$rg" --yes --no-wait
done
for rg in "$RG_PRIMARY" "$RG_STANDBY" "$RG_JAPAN"; do
  az group wait -n "$rg" --deleted --timeout 3600 || true
done
az group list --query "[?starts_with(name,'rg-dr-trial')].name" -o tsv
```

Expected: dòng cuối rỗng.

- [x] **Step 2: Xóa ngân sách thử nếu đã tạo, xóa tệp riêng**

```bash
SUB=$(az account show --query id -o tsv)
az rest --method delete --url "https://management.azure.com/subscriptions/$SUB/providers/Microsoft.Consumption/budgets/dr-trial?api-version=2023-05-01" || true
rm -f ~/.dr-trial/kubeconfig-* ~/.dr-trial/key-* ~/.dr-trial/velero-values-* ~/.dr-trial/cloud-init-* ~/.dr-trial/or-policy.json
```

- [x] **Step 3: Ghi chi phí ngày hôm sau và kết luận**

Ngày hôm sau, xem chi phí của ba nhóm trong Cost Management và ghi vào cuối `docs/trial-results.md`. Với mỗi dòng có quyết định đổi thiết kế, sửa mục tương ứng trong `docs/thiet-ke.md` và `docs/thiet-ke-web.md`.

```bash
git add docs/trial-results.md docs/thiet-ke.md docs/thiet-ke-web.md
git commit -m "Kết quả chạy thử và các chỗ sửa thiết kế"
```
