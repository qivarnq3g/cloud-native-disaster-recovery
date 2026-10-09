# Kế hoạch chạy thử trên Azure

> **Cho người thực hiện (agent):** dùng superpowers:executing-plans hoặc superpowers:subagent-driven-development để làm theo từng task. Các bước dùng ô `- [ ]` để đánh dấu.
>
> **Chỉ chạy khi Quang đã cho phép tạo tài nguyên Azure.** Kế hoạch này tạo máy ảo và tài khoản lưu trữ thật. Ước tính dưới 1 USD cho một buổi khoảng 6 giờ.

**Goal:** trả lời các câu hỏi ở mục 8 của thiết kế chính bằng số đo thật, trước khi viết hạ tầng thật, để nếu câu trả lời nào là "không" thì sửa thiết kế sớm.

**Architecture:** dựng tạm hai máy ảo k3s ở `koreacentral` và các tài khoản lưu trữ ở `japanwest` bằng Azure CLI (không dùng Terraform, vì đây là đồ dùng một lần), cài CNPG, Barman Cloud Plugin, Velero, cert-manager bằng Helm và manifest chính thức, đo, ghi kết quả vào `docs/lam-thu.md`, rồi xóa sạch.

**Tech Stack:** Azure CLI 2.89, k3s v1.37.1+k3s1, cert-manager v1.21.2, CloudNativePG 1.30.1, Barman Cloud Plugin v0.15.1, Velero v1.18.4 với plugin Azure v1.14.4, Helm 4, kubectl 1.36, Python 3 với `azure-storage-blob`.

**Spec:** [`docs/thiet-ke.md`](../thiet-ke.md) mục 1, 4, 6, 8; [`docs/thiet-ke-web.md`](../thiet-ke-web.md) mục 7.

## Global Constraints

- Chỉ tạo tài nguyên trong ba nhóm `rg-dr-thu-chinh`, `rg-dr-thu-du-phong` (đều `koreacentral`) và `rg-dr-thu-nhat` (`japanwest`). Không đụng nhóm tài nguyên nào khác trong tài khoản: tài khoản còn tài nguyên của một dự án khác.
- Máy ảo: `Standard_B2als_v2`, Ubuntu 24.04, ổ hệ điều hành P4 32 GB. Không bao giờ chạy cùng lúc quá hai máy (giới hạn 4 nhân).
- Phiên bản ghim như mục Tech Stack. Chứng chỉ chỉ xin từ máy chủ **staging** của Let's Encrypt.
- Khóa tài khoản lưu trữ, kubeconfig và khóa SSH nằm trong `~/.dr-thu/` và `~/.ssh/`, không bao giờ nằm trong kho Git. `.gitignore` đã chặn `kubeconfig*`, `*.key`, `.env*`.
- Mọi số đo ghi vào `data/lam-thu/` (CSV) và tóm tắt trong `docs/lam-thu.md`. Mốc thời gian theo UTC.
- Kết thúc buổi phải xóa cả ba nhóm tài nguyên và kiểm tra lại là đã xóa.

## Review Focus

- Quên xóa tài nguyên khi một bước lỗi giữa chừng: Task 11 phải chạy được độc lập, kể cả khi các task trước dở dang.
- Nhầm nhóm tài nguyên: mọi lệnh tạo hoặc xóa đều ghi rõ tên nhóm, không dùng nhóm mặc định của CLI.
- Lộ khóa: không dán khóa vào lệnh có ghi lịch sử của kho; đọc khóa từ tệp trong `~/.dr-thu/`.
- Cụm bản sao ghi WAL vào đường dẫn của cụm chính: mỗi cụm một `serverName` riêng, kiểm tra bằng cách liệt kê thư mục trong kho.
- Đo sai vì máy hết tín dụng CPU: ghi số tín dụng còn lại trước mỗi phép đo thời gian.

---

### Task 0: Chuẩn bị công cụ và biến môi trường

**Files:**
- Create: `scripts/thu/bien.sh`
- Create: `docs/lam-thu.md`
- Create: `data/lam-thu/.gitkeep`

- [ ] **Step 1: Cài Helm và kiểm tra công cụ**

```bash
winget install --id Helm.Helm --exact --silent
helm version --short
az version --query '"azure-cli"' -o tsv
kubectl version --client -o json | python -c "import sys,json; print(json.load(sys.stdin)['clientVersion']['gitVersion'])"
python -c "import sys; print(sys.version)"
```

Expected: Helm `v4.x`, azure-cli `2.89.x`, kubectl `v1.36.x`, Python 3.

- [ ] **Step 2: Tạo khóa SSH riêng cho buổi thử**

```bash
mkdir -p ~/.dr-thu
[ -f ~/.ssh/dr_thu_ed25519 ] || ssh-keygen -t ed25519 -f ~/.ssh/dr_thu_ed25519 -N "" -C dr-thu
ls -l ~/.ssh/dr_thu_ed25519.pub
```

- [ ] **Step 3: Viết tệp biến dùng chung**

`scripts/thu/bien.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
export NGAY="${NGAY:-$(date -u +%m%d)}"
export HAU_TO="${HAU_TO:-$(cat ~/.dr-thu/hau-to 2>/dev/null || true)}"
if [ -z "$HAU_TO" ]; then
  HAU_TO="$(python -c 'import secrets; print(secrets.token_hex(3))')"
  echo "$HAU_TO" > ~/.dr-thu/hau-to
fi
export RG_CHINH=rg-dr-thu-chinh
export RG_DU_PHONG=rg-dr-thu-du-phong
export RG_NHAT=rg-dr-thu-nhat
export VUNG_CUM=koreacentral
export VUNG_KHO=japanwest
export KHO_SAO_LUU="drthusl${HAU_TO}"
export KHO_ANH_CHINH="drthuanh${HAU_TO}"
export KHO_ANH_NHAT="drthuanhnb${HAU_TO}"
export DNS_CHINH="drthu-chinh-${HAU_TO}"
export DNS_DU_PHONG="drthu-dp-${HAU_TO}"
export FQDN_CHINH="${DNS_CHINH}.${VUNG_CUM}.cloudapp.azure.com"
export FQDN_DU_PHONG="${DNS_DU_PHONG}.${VUNG_CUM}.cloudapp.azure.com"
export KHOA_SSH=~/.ssh/dr_thu_ed25519
export THU_MUC_RIENG=~/.dr-thu
export DU_LIEU="$(git rev-parse --show-toplevel)/data/lam-thu"
export SERVER_CHINH="chinh-${NGAY}"
export SERVER_DU_PHONG="du-phong-${NGAY}"
```

- [ ] **Step 4: Tạo tệp kết quả**

`docs/lam-thu.md`:

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

- [ ] **Step 5: Commit**

```bash
mkdir -p data/lam-thu && touch data/lam-thu/.gitkeep
chmod +x scripts/thu/bien.sh
git add scripts/thu/bien.sh docs/lam-thu.md data/lam-thu/.gitkeep
git commit -m "Thêm biến và bảng kết quả cho buổi chạy thử Azure"
```

### Task 1: Ngân sách và nhóm tài nguyên thử

**Files:**
- Create: `infra/thu/ngan-sach.json`
- Modify: `docs/lam-thu.md` (dòng 10)

- [ ] **Step 1: Tạo ba nhóm tài nguyên**

```bash
source scripts/thu/bien.sh
az group create -n "$RG_CHINH" -l "$VUNG_CUM" --tags du-an=dr-thu -o none
az group create -n "$RG_DU_PHONG" -l "$VUNG_CUM" --tags du-an=dr-thu -o none
az group create -n "$RG_NHAT" -l "$VUNG_KHO" --tags du-an=dr-thu -o none
az group list --query "[?tags.\"du-an\"=='dr-thu'].name" -o tsv
```

Expected: đúng ba tên `rg-dr-thu-*`.

- [ ] **Step 2: Thử tạo ngân sách có cảnh báo email**

`infra/thu/ngan-sach.json`:

```json
{
  "properties": {
    "category": "Cost",
    "amount": 25,
    "timeGrain": "Monthly",
    "timePeriod": { "startDate": "2026-10-01T00:00:00Z", "endDate": "2026-12-31T00:00:00Z" },
    "filter": {
      "dimensions": { "name": "ResourceGroupName", "operator": "In", "values": ["rg-dr-thu-chinh", "rg-dr-thu-du-phong", "rg-dr-thu-nhat"] }
    },
    "notifications": {
      "nua": { "enabled": true, "operator": "GreaterThan", "threshold": 50, "contactEmails": ["qivarnq3g@gmail.com"] },
      "tam-muoi": { "enabled": true, "operator": "GreaterThan", "threshold": 80, "contactEmails": ["qivarnq3g@gmail.com"] },
      "het": { "enabled": true, "operator": "GreaterThan", "threshold": 100, "contactEmails": ["qivarnq3g@gmail.com"] }
    }
  }
}
```

```bash
SUB=$(az account show --query id -o tsv)
az rest --method put \
  --url "https://management.azure.com/subscriptions/$SUB/providers/Microsoft.Consumption/budgets/dr-thu?api-version=2023-05-01" \
  --body @infra/thu/ngan-sach.json --query "properties.amount"
```

Expected: `25`. Nếu lỗi vì loại tài khoản không hỗ trợ ngân sách, ghi nguyên văn mã lỗi vào dòng 10 của `docs/lam-thu.md`; quyết định khi đó là "xem số dư thủ công mỗi tuần" (mục 7.2 thiết kế chính).

- [ ] **Step 3: Ghi kết quả và commit**

```bash
git add infra/thu/ngan-sach.json docs/lam-thu.md
git commit -m "Chạy thử: nhóm tài nguyên và ngân sách"
```

### Task 2: Dựng cụm chính và đo thời gian dựng

**Files:**
- Create: `infra/thu/cloud-init-k3s.yaml.mau`
- Create: `scripts/thu/dung-cum.sh`
- Create: `data/lam-thu/dung-cum.csv` (script tự ghi)

- [ ] **Step 1: Mẫu cloud-init cài k3s**

`infra/thu/cloud-init-k3s.yaml.mau`:

```yaml
#cloud-config
package_update: false
runcmd:
  - curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION="v1.37.1+k3s1" INSTALL_K3S_EXEC="server --write-kubeconfig-mode=600 --tls-san=__FQDN__" sh -
```

- [ ] **Step 2: Script dựng cụm có ghi mốc thời gian**

`scripts/thu/dung-cum.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/bien.sh"
TEN="$1"; RG="$2"; DNS="$3"; FQDN="$4"
IP_TOI="$(curl -s https://api.ipify.org)"
CI="$THU_MUC_RIENG/cloud-init-$TEN.yaml"
sed "s/__FQDN__/$FQDN/" infra/thu/cloud-init-k3s.yaml.mau > "$CI"
moc() { echo "$TEN,$1,$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$DU_LIEU/dung-cum.csv"; }
[ -f "$DU_LIEU/dung-cum.csv" ] || echo "cum,moc,thoi_diem_utc" > "$DU_LIEU/dung-cum.csv"
moc bat_dau
az vm create -g "$RG" -n "vm-$TEN" -l "$VUNG_CUM" --image Ubuntu2404 --size Standard_B2als_v2 \
  --admin-username dr --ssh-key-values "$KHOA_SSH.pub" --public-ip-sku Standard \
  --public-ip-address-dns-name "$DNS" --custom-data "$CI" --nsg-rule NONE \
  --os-disk-size-gb 32 --storage-sku Premium_LRS -o none
moc may_ao_xong
az network nsg rule create -g "$RG" --nsg-name "vm-${TEN}NSG" -n quan-tri --priority 100 \
  --source-address-prefixes "$IP_TOI/32" --destination-port-ranges 22 6443 --access Allow --protocol Tcp -o none
az network nsg rule create -g "$RG" --nsg-name "vm-${TEN}NSG" -n web --priority 110 \
  --source-address-prefixes Internet --destination-port-ranges 80 443 --access Allow --protocol Tcp -o none
until ssh -i "$KHOA_SSH" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=5 "dr@$FQDN" 'sudo test -f /etc/rancher/k3s/k3s.yaml' 2>/dev/null; do sleep 5; done
moc k3s_cai_xong
ssh -i "$KHOA_SSH" "dr@$FQDN" 'sudo cat /etc/rancher/k3s/k3s.yaml' | sed "s/127.0.0.1/$FQDN/" > "$THU_MUC_RIENG/kubeconfig-$TEN"
export KUBECONFIG="$THU_MUC_RIENG/kubeconfig-$TEN"
until kubectl wait --for=condition=Ready node --all --timeout=10s >/dev/null 2>&1; do sleep 5; done
moc nut_san_sang
until kubectl -n kube-system rollout status deploy/traefik --timeout=10s >/dev/null 2>&1; do sleep 5; done
moc traefik_san_sang
```

- [ ] **Step 3: Chạy cho cụm chính**

```bash
chmod +x scripts/thu/dung-cum.sh
source scripts/thu/bien.sh
scripts/thu/dung-cum.sh chinh "$RG_CHINH" "$DNS_CHINH" "$FQDN_CHINH"
KUBECONFIG=~/.dr-thu/kubeconfig-chinh kubectl get nodes -o wide
cat data/lam-thu/dung-cum.csv
```

Expected: một nút `Ready`; CSV có 5 mốc. Thời gian dựng = `traefik_san_sang - bat_dau`.

- [ ] **Step 4: Ghi tín dụng CPU lúc bắt đầu**

```bash
VM_ID=$(az vm show -g "$RG_CHINH" -n vm-chinh --query id -o tsv)
az monitor metrics list --resource "$VM_ID" --metric "CPU Credits Remaining" --interval PT5M --query "value[0].timeseries[0].data[-1].average" -o tsv
```

Ghi số này cạnh thời gian dựng ở dòng 4 của `docs/lam-thu.md`.

- [ ] **Step 5: Commit**

```bash
git add infra/thu/cloud-init-k3s.yaml.mau scripts/thu/dung-cum.sh data/lam-thu/dung-cum.csv docs/lam-thu.md
git commit -m "Chạy thử: dựng cụm chính, đo thời gian"
```

### Task 3: Tài khoản lưu trữ và đo thời gian chép ảnh

**Files:**
- Create: `scripts/thu/tao-kho.sh`
- Create: `scripts/thu/do-chep-anh.py`
- Create: `data/lam-thu/chep-anh.csv` (script tự ghi)

- [ ] **Step 1: Tạo ba tài khoản lưu trữ và bật phiên bản, change feed, chép ảnh**

`scripts/thu/tao-kho.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/bien.sh"
tao() {
  az storage account create -n "$1" -g "$2" -l "$3" --sku Standard_LRS --kind StorageV2 \
    --min-tls-version TLS1_2 --allow-blob-public-access false -o none
  az storage account keys list -n "$1" -g "$2" --query "[0].value" -o tsv > "$THU_MUC_RIENG/khoa-$1"
}
tao "$KHO_SAO_LUU" "$RG_NHAT" "$VUNG_KHO"
tao "$KHO_ANH_CHINH" "$RG_CHINH" "$VUNG_CUM"
tao "$KHO_ANH_NHAT" "$RG_NHAT" "$VUNG_KHO"
az storage account blob-service-properties update -n "$KHO_ANH_CHINH" -g "$RG_CHINH" --enable-versioning true --enable-change-feed true -o none
az storage account blob-service-properties update -n "$KHO_ANH_NHAT" -g "$RG_NHAT" --enable-versioning true -o none
for c in cnpg velero; do
  az storage container create -n "$c" --account-name "$KHO_SAO_LUU" --account-key "$(cat "$THU_MUC_RIENG/khoa-$KHO_SAO_LUU")" -o none
done
az storage container create -n anh --account-name "$KHO_ANH_CHINH" --account-key "$(cat "$THU_MUC_RIENG/khoa-$KHO_ANH_CHINH")" -o none
az storage container create -n anh --account-name "$KHO_ANH_NHAT" --account-key "$(cat "$THU_MUC_RIENG/khoa-$KHO_ANH_NHAT")" -o none
NGUON_ID=$(az storage account show -n "$KHO_ANH_CHINH" -g "$RG_CHINH" --query id -o tsv)
DICH_ID=$(az storage account show -n "$KHO_ANH_NHAT" -g "$RG_NHAT" --query id -o tsv)
az storage account or-policy create -g "$RG_NHAT" -n "$KHO_ANH_NHAT" \
  --source-account "$NGUON_ID" --destination-account "$DICH_ID" \
  --source-container anh --destination-container anh -o json > "$THU_MUC_RIENG/or-policy.json"
az storage account or-policy create -g "$RG_CHINH" -n "$KHO_ANH_CHINH" --policy "@$THU_MUC_RIENG/or-policy.json" -o none
az storage account or-policy list -g "$RG_CHINH" -n "$KHO_ANH_CHINH" --query "[].rules[].sourceContainer" -o tsv
```

```bash
chmod +x scripts/thu/tao-kho.sh && scripts/thu/tao-kho.sh
```

Expected: dòng cuối in `anh`.

- [ ] **Step 2: Script đo độ trễ chép ảnh**

`scripts/thu/do-chep-anh.py`:

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

RIENG = Path.home() / ".dr-thu"
NGUON = os.environ["KHO_ANH_CHINH"]
DICH = os.environ["KHO_ANH_NHAT"]
SO_ANH = int(sys.argv[1]) if len(sys.argv) > 1 else 200
KICH_THUOC = 200 * 1024
HET_GIO = 1800
RA = Path(os.environ["DU_LIEU"]) / "chep-anh.csv"


def client(ten):
    khoa = (RIENG / f"khoa-{ten}").read_text().strip()
    return BlobServiceClient(f"https://{ten}.blob.core.windows.net", credential=khoa).get_container_client("anh")


def utc(t):
    return datetime.fromtimestamp(t, timezone.utc).isoformat()


def theo_doi(dich, ten, luc_gui, ket_qua, khoa_ket_qua):
    while time.time() - luc_gui < HET_GIO:
        try:
            dich.get_blob_client(ten).get_blob_properties()
            with khoa_ket_qua:
                ket_qua.append((ten, utc(luc_gui), utc(time.time()), round(time.time() - luc_gui, 1)))
            return
        except ResourceNotFoundError:
            time.sleep(2)
    with khoa_ket_qua:
        ket_qua.append((ten, utc(luc_gui), "", ""))


def main():
    nguon, dich = client(NGUON), client(DICH)
    ket_qua, khoa_ket_qua, luong = [], threading.Lock(), []
    for i in range(SO_ANH):
        ten = f"thu/{int(time.time())}-{i:04d}.bin"
        luc_gui = time.time()
        nguon.upload_blob(ten, os.urandom(KICH_THUOC))
        t = threading.Thread(target=theo_doi, args=(dich, ten, luc_gui, ket_qua, khoa_ket_qua))
        t.start()
        luong.append(t)
        time.sleep(max(0.0, 1.0 - (time.time() - luc_gui)))
    for t in luong:
        t.join()
    with RA.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["blob", "gui_utc", "co_o_nhat_utc", "do_tre_giay"])
        w.writerows(sorted(ket_qua))
    tre = sorted(r[3] for r in ket_qua if r[3] != "")
    thieu = sum(1 for r in ket_qua if r[3] == "")
    if tre:
        print(f"n={len(tre)} thieu={thieu} trung_vi={tre[len(tre)//2]} p95={tre[int(len(tre)*0.95)-1]} lon_nhat={tre[-1]}")
    else:
        print(f"khong anh nao toi Nhat trong {HET_GIO} giay")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Chạy đo 200 ảnh**

```bash
python -m venv ~/.dr-thu/venv
~/.dr-thu/venv/Scripts/python -m pip install -q "azure-storage-blob==12.*"
source scripts/thu/bien.sh
~/.dr-thu/venv/Scripts/python scripts/thu/do-chep-anh.py 200
```

Expected: một dòng `n=… thieu=… trung_vi=… p95=… lon_nhat=…`. Ghi vào dòng 3 của `docs/lam-thu.md`. Quyết định: RPO của ảnh trong mục 3 thiết kế chính đặt không thấp hơn p95 đo được.

- [ ] **Step 4: Commit**

```bash
git add scripts/thu/tao-kho.sh scripts/thu/do-chep-anh.py data/lam-thu/chep-anh.csv docs/lam-thu.md
git commit -m "Chạy thử: kho lưu trữ, đo độ trễ chép ảnh sang Nhật"
```

### Task 4: Cài phần mềm vào cụm chính và đo RAM

**Files:**
- Create: `infra/thu/velero-values.yaml.mau`
- Create: `infra/thu/csdl-chinh.yaml.mau`
- Create: `infra/thu/tai-thu.yaml`
- Create: `scripts/thu/cai-phan-mem.sh`

- [ ] **Step 1: Mẫu cấu hình Velero**

`infra/thu/velero-values.yaml.mau`:

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
        storageAccount: __KHO_SAO_LUU__
        storageAccountKeyEnvVar: AZURE_STORAGE_ACCOUNT_ACCESS_KEY
        subscriptionId: __SUB__
        resourceGroup: rg-dr-thu-nhat
  volumeSnapshotLocation: []
snapshotsEnabled: false
deployNodeAgent: false
credentials:
  useSecret: true
  secretContents:
    cloud: |
      AZURE_STORAGE_ACCOUNT_ACCESS_KEY=__KHOA__
      AZURE_CLOUD_NAME=AzurePublicCloud
```

- [ ] **Step 2: Mẫu cơ sở dữ liệu có gửi WAL sang Nhật**

`infra/thu/csdl-chinh.yaml.mau`:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: kho-nhat-khoa
type: Opaque
stringData:
  TEN: __KHO_SAO_LUU__
  KHOA: __KHOA__
---
apiVersion: barmancloud.cnpg.io/v1
kind: ObjectStore
metadata:
  name: kho-nhat
spec:
  retentionPolicy: "7d"
  configuration:
    destinationPath: https://__KHO_SAO_LUU__.blob.core.windows.net/cnpg
    azureCredentials:
      storageAccount:
        name: kho-nhat-khoa
        key: TEN
      storageKey:
        name: kho-nhat-khoa
        key: KHOA
    wal:
      compression: gzip
---
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: csdl
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
        barmanObjectName: kho-nhat
        serverName: __SERVER__
```

- [ ] **Step 3: Tải giả lập 1 bài mỗi giây trong 1 giờ**

`infra/thu/tai-thu.yaml`:

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: tai-thu
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
                  name: csdl-app
                  key: uri
          command:
            - bash
            - -c
            - |
              psql "$URI" -qc "CREATE TABLE IF NOT EXISTS bai_thu(id bigserial PRIMARY KEY, noi_dung text, tao_luc timestamptz DEFAULT now())"
              for i in $(seq 1 3600); do
                psql "$URI" -qc "INSERT INTO bai_thu(noi_dung) VALUES (repeat(md5(random()::text), 10))"
                sleep 1
              done
```

- [ ] **Step 4: Script cài phần mềm vào một cụm**

`scripts/thu/cai-phan-mem.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/bien.sh"
TEN="$1"
export KUBECONFIG="$THU_MUC_RIENG/kubeconfig-$TEN"
KHOA="$(cat "$THU_MUC_RIENG/khoa-$KHO_SAO_LUU")"
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
sed -e "s/__KHO_SAO_LUU__/$KHO_SAO_LUU/" -e "s/__SUB__/$SUB/" -e "s|__KHOA__|$KHOA|" \
  infra/thu/velero-values.yaml.mau > "$THU_MUC_RIENG/velero-values-$TEN.yaml"
helm upgrade --install velero vmware-tanzu/velero -n velero --create-namespace \
  -f "$THU_MUC_RIENG/velero-values-$TEN.yaml" --wait
kubectl -n velero get backupstoragelocation default -o jsonpath='{.status.phase}{"\n"}'
```

- [ ] **Step 5: Cài, dựng cơ sở dữ liệu, đo RAM lúc rảnh**

```bash
chmod +x scripts/thu/cai-phan-mem.sh
source scripts/thu/bien.sh
scripts/thu/cai-phan-mem.sh chinh
export KUBECONFIG=~/.dr-thu/kubeconfig-chinh
sed -e "s/__KHO_SAO_LUU__/$KHO_SAO_LUU/g" -e "s|__KHOA__|$(cat ~/.dr-thu/khoa-$KHO_SAO_LUU)|" -e "s/__SERVER__/$SERVER_CHINH/" \
  infra/thu/csdl-chinh.yaml.mau | kubectl apply -f -
kubectl wait --for=condition=Ready cluster/csdl --timeout=600s
ssh -i "$KHOA_SSH" "dr@$FQDN_CHINH" free -m
kubectl top pods -A --sort-by=memory | head -15
```

Expected: `Available` của BackupStorageLocation; cluster `csdl` Ready; ghi `used` của `free -m` (rảnh).

- [ ] **Step 6: Chạy tải 1 giờ, đo RAM đỉnh và dung lượng WAL**

```bash
kubectl apply -f infra/thu/tai-thu.yaml
for i in $(seq 1 12); do
  ssh -i "$KHOA_SSH" "dr@$FQDN_CHINH" "free -m | awk '/Mem:/{print \$3}'" | sed "s/^/$(date -u +%H:%M:%S),/" >> "$DU_LIEU/ram-chinh.csv"
  sleep 300
done
KHOA="$(cat ~/.dr-thu/khoa-$KHO_SAO_LUU)"
az storage blob list --account-name "$KHO_SAO_LUU" --account-key "$KHOA" -c cnpg --prefix "$SERVER_CHINH/wals/" \
  --num-results 100000 --query "[length(@), sum([].properties.contentLength)]" -o tsv
```

Expected: hai số: số tệp WAL và tổng byte trong khoảng 1 giờ. WAL mỗi ngày = tổng byte × 24. Ghi RAM đỉnh (`max` của `ram-chinh.csv`) vào dòng 1, WAL vào dòng 2.

Quyết định:
- RAM đỉnh trên 80% của 4 GB (khoảng 3.200 MB dùng) thì đổi sang B2as v2 (mục 8 thiết kế chính).
- WAL mỗi ngày trên 2 GB thì đặt `bootstrap.initdb.walSegmentSize: 1` (MB) cho cụm thật và đo lại ở bản thu nhỏ.

- [ ] **Step 7: Commit**

```bash
git add infra/thu scripts/thu/cai-phan-mem.sh data/lam-thu/ram-chinh.csv docs/lam-thu.md
git commit -m "Chạy thử: cài phần mềm, đo RAM và dung lượng WAL"
```

### Task 5: Chứng chỉ staging và sao lưu Velero ở cụm chính

**Files:**
- Create: `infra/thu/tls-thu.yaml.mau`

- [ ] **Step 1: Mẫu dịch vụ thử có chứng chỉ staging**

`infra/thu/tls-thu.yaml.mau`:

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
      name: le-staging-khoa
    solvers:
      - http01:
          ingress:
            ingressClassName: traefik
---
apiVersion: v1
kind: Namespace
metadata:
  name: thu-tls
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: whoami
  namespace: thu-tls
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
  namespace: thu-tls
spec:
  selector: { app: whoami }
  ports: [{ port: 80, targetPort: 80 }]
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: whoami
  namespace: thu-tls
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

- [ ] **Step 2: Xin chứng chỉ và sao lưu**

```bash
source scripts/thu/bien.sh
export KUBECONFIG=~/.dr-thu/kubeconfig-chinh
sed "s/__HOST__/$FQDN_CHINH/g" infra/thu/tls-thu.yaml.mau | kubectl apply -f -
kubectl -n thu-tls wait --for=condition=Ready certificate/whoami-tls --timeout=600s
kubectl -n thu-tls get secret whoami-tls -o jsonpath='{.data.tls\.crt}' | base64 -d | openssl x509 -noout -serial -issuer
kubectl -n velero create -f - <<EOF
apiVersion: velero.io/v1
kind: Backup
metadata:
  name: thu-tls-1
spec:
  includedNamespaces: [thu-tls]
  storageLocation: default
  ttl: 72h0m0s
EOF
kubectl -n velero wait --for=jsonpath='{.status.phase}'=Completed backup/thu-tls-1 --timeout=600s
```

Expected: serial và issuer có chữ `STAGING`; backup `Completed`. Ghi serial lại để so ở Task 6.

### Task 6: Cụm dự phòng: bản sao CNPG, đổi vai, khôi phục lạnh, khôi phục chứng chỉ

**Files:**
- Create: `infra/thu/csdl-ban-sao.yaml.mau`
- Create: `infra/thu/csdl-khoi-phuc.yaml.mau`

- [ ] **Step 1: Sao lưu đầy đủ đầu tiên ở cụm chính**

```bash
export KUBECONFIG=~/.dr-thu/kubeconfig-chinh
kubectl create -f - <<EOF
apiVersion: postgresql.cnpg.io/v1
kind: Backup
metadata:
  name: dau-tien
spec:
  cluster:
    name: csdl
  method: plugin
  pluginConfiguration:
    name: barman-cloud.cloudnative-pg.io
EOF
kubectl wait --for=jsonpath='{.status.phase}'=completed backup/dau-tien --timeout=900s
```

- [ ] **Step 2: Dựng cụm dự phòng và cài phần mềm (đo thời gian như cụm chính)**

```bash
source scripts/thu/bien.sh
scripts/thu/dung-cum.sh du-phong "$RG_DU_PHONG" "$DNS_DU_PHONG" "$FQDN_DU_PHONG"
scripts/thu/cai-phan-mem.sh du-phong
```

- [ ] **Step 3: Mẫu cụm bản sao đọc WAL từ Nhật**

`infra/thu/csdl-ban-sao.yaml.mau`:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: kho-nhat-khoa
type: Opaque
stringData:
  TEN: __KHO_SAO_LUU__
  KHOA: __KHOA__
---
apiVersion: barmancloud.cnpg.io/v1
kind: ObjectStore
metadata:
  name: kho-nhat
spec:
  retentionPolicy: "7d"
  configuration:
    destinationPath: https://__KHO_SAO_LUU__.blob.core.windows.net/cnpg
    azureCredentials:
      storageAccount:
        name: kho-nhat-khoa
        key: TEN
      storageKey:
        name: kho-nhat-khoa
        key: KHOA
    wal:
      compression: gzip
---
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: csdl
spec:
  instances: 1
  imageName: ghcr.io/cloudnative-pg/postgresql:18
  storage:
    size: 5Gi
  bootstrap:
    recovery:
      source: chinh
  replica:
    enabled: true
    source: chinh
  externalClusters:
    - name: chinh
      plugin:
        name: barman-cloud.cloudnative-pg.io
        parameters:
          barmanObjectName: kho-nhat
          serverName: __SERVER_CHINH__
  plugins:
    - name: barman-cloud.cloudnative-pg.io
      isWALArchiver: true
      parameters:
        barmanObjectName: kho-nhat
        serverName: __SERVER_DU_PHONG__
```

- [ ] **Step 4: Dựng bản sao, đo độ trễ theo kịp**

```bash
export KUBECONFIG=~/.dr-thu/kubeconfig-du-phong
sed -e "s/__KHO_SAO_LUU__/$KHO_SAO_LUU/g" -e "s|__KHOA__|$(cat ~/.dr-thu/khoa-$KHO_SAO_LUU)|" \
  -e "s/__SERVER_CHINH__/$SERVER_CHINH/" -e "s/__SERVER_DU_PHONG__/$SERVER_DU_PHONG/" \
  infra/thu/csdl-ban-sao.yaml.mau | kubectl apply -f -
kubectl wait --for=condition=Ready cluster/csdl --timeout=1200s
MOC="moc-$(date -u +%s)"
KUBECONFIG=~/.dr-thu/kubeconfig-chinh kubectl exec csdl-1 -c postgres -- psql -d app -qc "INSERT INTO bai_thu(noi_dung) VALUES ('$MOC')"
T0=$(date -u +%s)
until kubectl exec csdl-1 -c postgres -- psql -d app -tAc "SELECT count(*) FROM bai_thu WHERE noi_dung='$MOC'" | grep -q 1; do sleep 2; done
echo "do_tre_ban_sao_giay=$(( $(date -u +%s) - T0 ))"
az storage blob list --account-name "$KHO_SAO_LUU" --account-key "$(cat ~/.dr-thu/khoa-$KHO_SAO_LUU)" -c cnpg \
  --delimiter / --query "[].name" -o tsv
```

Expected: bản sao Ready; độ trễ dưới khoảng 2 phút (archive_timeout 60 giây cộng thời gian đọc); danh sách thư mục trong `cnpg` có `$SERVER_CHINH/` và **không** có tệp WAL mới nào của cụm dự phòng ghi vào thư mục `$SERVER_CHINH/`. Ghi vào dòng 6.

- [ ] **Step 5: Đổi vai bản sao thành chính, đo thời gian**

```bash
T0=$(date -u +%s)
kubectl patch cluster csdl --type merge -p '{"spec":{"replica":{"enabled":false}}}'
until kubectl exec csdl-1 -c postgres -- psql -d app -tAc "SELECT pg_is_in_recovery()" | grep -q f; do sleep 2; done
echo "doi_vai_giay=$(( $(date -u +%s) - T0 ))"
kubectl exec csdl-1 -c postgres -- psql -d app -qc "INSERT INTO bai_thu(noi_dung) VALUES ('sau-doi-vai')"
```

Expected: ghi được sau khi đổi vai; ghi thời gian vào dòng 6.

- [ ] **Step 6: Mẫu khôi phục lạnh và đo thời gian**

`infra/thu/csdl-khoi-phuc.yaml.mau`:

```yaml
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: csdl-lanh
spec:
  instances: 1
  imageName: ghcr.io/cloudnative-pg/postgresql:18
  storage:
    size: 5Gi
  bootstrap:
    recovery:
      source: chinh
  externalClusters:
    - name: chinh
      plugin:
        name: barman-cloud.cloudnative-pg.io
        parameters:
          barmanObjectName: kho-nhat
          serverName: __SERVER_CHINH__
```

```bash
T0=$(date -u +%s)
sed "s/__SERVER_CHINH__/$SERVER_CHINH/" infra/thu/csdl-khoi-phuc.yaml.mau | kubectl apply -f -
kubectl wait --for=condition=Ready cluster/csdl-lanh --timeout=1800s
echo "khoi_phuc_lanh_giay=$(( $(date -u +%s) - T0 ))"
kubectl exec csdl-lanh-1 -c postgres -- psql -d app -tAc "SELECT count(*), max(tao_luc) FROM bai_thu"
```

Expected: số dòng và `max(tao_luc)` cách lúc chạy lệnh không quá vài phút; ghi thời gian khôi phục vào dòng 6.

- [ ] **Step 7: Khôi phục chứng chỉ bằng Velero ở cụm dự phòng**

```bash
export KUBECONFIG=~/.dr-thu/kubeconfig-du-phong
source scripts/thu/bien.sh
sed "s/__HOST__/$FQDN_CHINH/g" infra/thu/tls-thu.yaml.mau | python -c "import sys; d=sys.stdin.read().split('\n---\n'); print(d[0])" | kubectl apply -f -
kubectl -n velero wait --for=jsonpath='{.status.phase}'=Available backupstoragelocation/default --timeout=300s
kubectl -n velero create -f - <<EOF
apiVersion: velero.io/v1
kind: Restore
metadata:
  name: thu-tls-1
spec:
  backupName: thu-tls-1
EOF
kubectl -n velero wait --for=jsonpath='{.status.phase}'=Completed restore/thu-tls-1 --timeout=600s
kubectl -n thu-tls get secret whoami-tls -o jsonpath='{.data.tls\.crt}' | base64 -d | openssl x509 -noout -serial
sleep 600
kubectl -n thu-tls get certificaterequest --no-headers | wc -l
kubectl -n thu-tls get certificate whoami-tls -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}{"\n"}'
```

Expected: serial giống hệt serial ở Task 5; sau 10 phút số CertificateRequest ở cụm dự phòng là `0` hoặc chỉ có bản được khôi phục, và Certificate `True`. Ghi vào dòng 7. Nếu cert-manager xin chứng chỉ mới thì quyết định: khi khôi phục, tắt cert-manager cho tới khi Secret đã về, và ghi vào runbook.

- [ ] **Step 8: Commit**

```bash
git add infra/thu/csdl-ban-sao.yaml.mau infra/thu/csdl-khoi-phuc.yaml.mau docs/lam-thu.md data/lam-thu/dung-cum.csv
git commit -m "Chạy thử: bản sao, đổi vai, khôi phục lạnh, khôi phục chứng chỉ"
```

### Task 7: Ủy quyền DNS `api.dr` trên iNET (chỉ xem, không tạo)

**Files:**
- Modify: `docs/lam-thu.md` (dòng 5)

- [ ] **Step 1: Xem trang quản lý DNS của `qivarn.id.vn` bằng Edge của Quang (Claude in Chrome)**

Mở trang quản lý bản ghi của tên miền trong iNET OnePortal. Kiểm tra danh sách loại bản ghi có `NS` và cho phép tên `api.dr` không. Không bấm lưu, không tạo bản ghi.

Expected: một trong hai: có `NS` cho tên con, hoặc không. Ghi vào dòng 5 kèm ảnh chụp lưu trong `personal/Minh-chung/` (ngoài kho). Nếu không có `NS`: quyết định đổi bản ghi A của `api.dr` trên iNET bằng tay khi chuyển cụm, thời gian ghi nhớ 60 giây (mục 8 thiết kế chính), và tính bước này vào thời gian chuyển lưu lượng.

### Task 8: GitHub có gửi email khi workflow lỗi

**Files:**
- Create: `.github/workflows/thu-loi.yml` (xóa ở Step 3)

- [ ] **Step 1: Workflow cố ý lỗi, chỉ chạy bằng tay**

`.github/workflows/thu-loi.yml`:

```yaml
name: thu-loi
on:
  workflow_dispatch:
jobs:
  loi:
    runs-on: ubuntu-latest
    steps:
      - run: exit 1
```

- [ ] **Step 2: Chạy và nhờ Quang xem hộp thư**

```bash
git checkout -b thu/email-loi
git add .github/workflows/thu-loi.yml
git commit -m "Thử email khi workflow lỗi"
git push -u origin thu/email-loi
gh workflow run thu-loi.yml --ref thu/email-loi
sleep 60
gh run list --workflow thu-loi.yml --limit 1 --json conclusion,createdAt
```

Expected: `conclusion` là `failure`. Quang kiểm tra hộp thư `qivarnq3g@gmail.com` có thư "Run failed" của GitHub. Ghi vào dòng 8.

- [ ] **Step 3: Dọn nhánh thử**

```bash
git checkout main
git push origin --delete thu/email-loi
git branch -D thu/email-loi
```

### Task 9: Bản thu nhỏ có vừa máy GitHub không

**Files:**
- Create: `.github/workflows/thu-kind.yml` (xóa ở Step 3)

- [ ] **Step 1: Workflow dựng hai cụm kind và đo tài nguyên**

`.github/workflows/thu-kind.yml`:

```yaml
name: thu-kind
on:
  workflow_dispatch:
jobs:
  do:
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
          kind create cluster --name chinh --wait 300s
          kind create cluster --name du-phong --wait 300s
      - name: SeaweedFS
        run: docker run -d --name seaweedfs --network kind -p 8333:8333 chrislusf/seaweedfs:4.48 server -s3
      - name: Phần mềm vào hai cụm
        run: |
          helm repo add jetstack https://charts.jetstack.io
          helm repo add cnpg https://cloudnative-pg.github.io/charts
          helm repo add vmware-tanzu https://vmware-tanzu.github.io/helm-charts
          for c in chinh du-phong; do
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
            name: csdl
          spec:
            instances: 1
            imageName: ghcr.io/cloudnative-pg/postgresql:18
            storage:
              size: 2Gi
          EOF
            kubectl wait --for=condition=Ready cluster/csdl --timeout=600s
          done
      - name: Đo
        run: |
          free -m
          df -h /
          docker system df
          nproc
```

- [ ] **Step 2: Chạy và đọc kết quả**

```bash
git checkout -b thu/kind
git add .github/workflows/thu-kind.yml
git commit -m "Thử bản thu nhỏ trên máy GitHub"
git push -u origin thu/kind
gh workflow run thu-kind.yml --ref thu/kind
gh run watch "$(gh run list --workflow thu-kind.yml --limit 1 --json databaseId -q '.[0].databaseId')" --exit-status
gh run view --log "$(gh run list --workflow thu-kind.yml --limit 1 --json databaseId -q '.[0].databaseId')" | grep -A20 "Đo"
```

Expected: workflow thành công; `free -m` còn trên 4 GB trống, `df -h /` còn trên 3 GB. Ghi vào dòng 9. Nếu thiếu: quyết định chạy bản thu nhỏ với một cụm kind và đổi vai trong cùng cụm, ghi vào mục 6.4 thiết kế chính.

- [ ] **Step 3: Dọn nhánh thử**

```bash
git checkout main
git push origin --delete thu/kind
git branch -D thu/kind
```

### Task 10: Thời gian tạo ảnh nhỏ AVIF trên B2als v2 (chỉ khi API đã có)

Bỏ qua task này nếu kế hoạch API (`docs/ke-hoach/2026-10-09-api.md`) chưa làm tới Task 6 (ví dụ `do-anh-nho`).

- [ ] **Step 1: Biên dịch ví dụ đo và chạy trên máy ảo**

```bash
source scripts/thu/bien.sh
MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd -W)/app/api:/src" -w /src rust:1.97.1-alpine \n  sh -c 'apk add --no-cache build-base nasm >/dev/null && cargo build --release --features phat_hanh --example do-anh-nho --target-dir /src/target-musl'
scp -i "$KHOA_SSH" app/api/target-musl/release/examples/do-anh-nho "dr@$FQDN_CHINH:/tmp/"
ssh -i "$KHOA_SSH" "dr@$FQDN_CHINH" /tmp/do-anh-nho 50
```

Expected: dòng `n=50 trung_vi_ms=… p95_ms=…`. Ghi vào dòng 11. Ngưỡng: p95 không quá 500 ms; vượt thì đổi ảnh nhỏ sang WebP (mục 7 thiết kế web).

### Task 11: Dọn sạch

Chạy được độc lập với các task trước.

- [ ] **Step 1: Xóa ba nhóm tài nguyên và đợi xong**

```bash
source scripts/thu/bien.sh
for rg in "$RG_CHINH" "$RG_DU_PHONG" "$RG_NHAT"; do
  az group exists -n "$rg" | grep -q true && az group delete -n "$rg" --yes --no-wait
done
for rg in "$RG_CHINH" "$RG_DU_PHONG" "$RG_NHAT"; do
  az group wait -n "$rg" --deleted --timeout 3600 || true
done
az group list --query "[?starts_with(name,'rg-dr-thu')].name" -o tsv
```

Expected: dòng cuối rỗng.

- [ ] **Step 2: Xóa ngân sách thử nếu đã tạo, xóa tệp riêng**

```bash
SUB=$(az account show --query id -o tsv)
az rest --method delete --url "https://management.azure.com/subscriptions/$SUB/providers/Microsoft.Consumption/budgets/dr-thu?api-version=2023-05-01" || true
rm -f ~/.dr-thu/kubeconfig-* ~/.dr-thu/khoa-* ~/.dr-thu/velero-values-* ~/.dr-thu/cloud-init-* ~/.dr-thu/or-policy.json
```

- [ ] **Step 3: Ghi chi phí ngày hôm sau và kết luận**

Ngày hôm sau, xem chi phí của ba nhóm trong Cost Management và ghi vào cuối `docs/lam-thu.md`. Với mỗi dòng có quyết định đổi thiết kế, sửa mục tương ứng trong `docs/thiet-ke.md` và `docs/thiet-ke-web.md`.

```bash
git add docs/lam-thu.md docs/thiet-ke.md docs/thiet-ke-web.md
git commit -m "Kết quả chạy thử và các chỗ sửa thiết kế"
```
