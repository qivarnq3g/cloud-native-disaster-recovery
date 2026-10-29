# Kế hoạch tuần 4A: cụm dự phòng ấm và diễn tập D1 tới D5 trên Azure

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dựng cụm dự phòng ấm, có lệnh chuyển cụm lạnh và ấm tự ghi giờ từng bước, và chạy vòng thử D1 tới D5 trên Azure với số đo theo mục 5.

**Architecture:** Cụm dự phòng là máy ảo k3s thứ hai (`vm-dr-standby`), Postgres ở đó là cụm bản sao CNPG đọc WAL từ kho Nhật, API chạy chế độ chỉ đọc trên kho ảnh dự phòng. Mỗi bước của runbook là một lệnh bọc bởi `step.sh`, ghi giờ vào CSV của lần diễn tập. Một trình điều khiển Python dùng lại `Ledger`, `Writer`, `Prober`, `compare` và `results` của bản kind để tạo tải, phát hiện sự cố và kiểm tra sau khôi phục.

**Tech Stack:** Bash, Python 3.12 (thư viện chuẩn và `azure-storage-blob`), Terraform 1.16.6, k3s, CloudNativePG 1.30.1 với plugin Barman Cloud v0.15.1, Velero v1.18.4, Cloudflare API.

**Spec:** `docs/thiet-ke.md` mục 3, 5, 6 (đặc biệt 5.1 tới 5.4 và 6.1). Kết quả buổi thử và phiên thật: `docs/trial-results.md`.

## Global Constraints

- Tài khoản chỉ có 4 nhân ở `koreacentral`: tối đa hai máy B2als v2 cùng lúc (`session-start.sh` đã chặn máy thứ ba bằng mã 4).
- Không bao giờ đụng nhóm `rg-splitbind-prod`.
- Tên tệp, hàm, biến, cột CSV bằng tiếng Anh; chữ hiển thị và tài liệu bằng tiếng Việt.
- Không viết chú thích trong mã. Giải thích để trong README hoặc kế hoạch.
- Sáu bước đo cố định theo `scripts/kind/results.py`: `detect`, `decide`, `infra`, `restore`, `verify`, `switch`.
- Phát hiện: 5 lần gọi hỏng liên tiếp (`DETECT_THRESHOLD = 5`). Tải trong lúc đo: đúng 1 bài mỗi giây. Thời gian chạy ấm trước sự cố: 90 s.
- Bộ dữ liệu mẫu: 1.000 bài, mỗi bài một ảnh PNG ngẫu nhiên 256 x 256 (khoảng 196 KB, `make_png(seed, 256)`).
- Mục tiêu so sánh (mục 3): RPO 5 phút; RTO cả web lạnh 60 phút, ấm 10 phút.
- Máy ảo không dùng thì tắt hẳn bằng `session-stop.sh` hoặc `standby-down.sh`; không để chạy qua đêm.
- Mọi lệnh dùng khóa hoặc mã đọc từ `~/.dr/`, không in ra màn hình, không ghi vào kho.

## Review Focus

- IP nhà đổi giữa lúc dựng và lúc diễn tập: mọi lệnh cần `kubectl` gọi `refresh_admin_ip` trước (test ở Task 3 và Task 4).
- Cụm dự phòng vừa thành chính mà kho ảnh dự phòng vẫn còn chính sách chép từ kho chính: API ghi ảnh sẽ bị từ chối. Lệnh chuyển ấm phải gỡ chính sách trước khi bật ghi (test ở Task 4).
- Mất kết nối mạng ở nhà trong lúc đo bị tính nhầm thành sự cố: mẫu đo có cột `network_ok`, giây nào điểm đối chứng hỏng thì không tính vào phát hiện (test ở Task 1).
- Diễn tập xong để lại trạng thái lệch (cụm dự phòng đang là chính, `session.json` trỏ sai cụm): lệnh chuyển cụm phải cập nhật `session.json` cùng lúc đổi DNS (test ở Task 4).
- Chạy lại lần diễn tập trùng mã: `step.sh` từ chối ghi đè thư mục `data/drills/<run_id>/` đã có (test ở Task 2).

## Cấu trúc tệp

| Tệp | Việc |
|---|---|
| `scripts/kind/workload.py` | Thêm `host` cho `ApiClient` để gọi thẳng IP của từng cụm |
| `scripts/kind/probe.py` | Thêm điểm đối chứng mạng vào `Prober` |
| `scripts/azure/step.sh` | Bọc một lệnh runbook, ghi `step,started_at,ended_at,result` |
| `infra/k8s/platform/db-replica.yaml.tpl` | Cụm bản sao CNPG đọc WAL của cụm chính từ kho Nhật |
| `infra/k8s/platform/db-recover-to-backup.yaml.tpl` | Khôi phục về đúng một bản đầy đủ (dùng cho bộ dữ liệu mẫu) |
| `scripts/azure/install-software.sh` | Thêm chế độ `replica` qua biến `DR_DB_MODE` |
| `scripts/azure/standby-up.sh`, `standby-down.sh` | Dựng và xóa cụm dự phòng ấm |
| `scripts/azure/failover-warm.sh` | Chuyển sang cụm dự phòng ấm |
| `scripts/azure/failover-cold.sh` | Dựng cụm mới từ kho Nhật và chuyển sang |
| `scripts/azure/restore-namespace.sh` | Khôi phục namespace và cơ sở dữ liệu về ngay trước lúc xóa (D1) |
| `scripts/azure/copy-images.sh` | Chép ảnh từ bản chép ở Nhật sang kho ảnh dự phòng (D4) |
| `scripts/azure/break.sh` | Năm cách phá của D1 tới D5 |
| `scripts/azure/seed.sh`, `reset-seed.sh` | Tạo bộ dữ liệu mẫu và đưa cơ sở dữ liệu về đúng bộ mẫu |
| `scripts/dr/azure_drill.py` | Trình điều khiển một lần diễn tập |
| `tests/scripts/test_azure_drill.py`, `test_failover_scripts.py`, `test_step_script.py` | Test |
| `docs/dien-tap/README.md`, `docs/dien-tap/<run_id>.md` | Mẫu và biên bản từng lần |
| `docs/runbook.md` | Runbook sửa theo vòng thử |

---

### Task 1: Gọi thẳng từng cụm và điểm đối chứng mạng

**Files:**
- Modify: `scripts/kind/workload.py` (lớp `ApiClient`), `scripts/kind/probe.py` (lớp `Sample`, `Prober`)
- Test: `tests/scripts/test_kind_probe.py` (thêm), `tests/scripts/test_kind_workload.py` (thêm)

**Interfaces:**
- Produces:
  - `ApiClient(base: str, code: str = "", timeout: float = 5, host: str | None = None)`: khi có `host` thì mọi yêu cầu gửi tiêu đề `Host: <host>`. Dùng `ApiClient("http://20.0.0.9", host="api.dr.qivarn.id.vn")` để gọi thẳng một cụm qua cổng 80 của Traefik.
  - `Prober(targets, watch, interval=1.0, control: Callable[[], bool] | None = None)`. `Sample` thêm trường `network_ok: bool` (mặc định `True`). Khi `control()` trả `False`, mẫu của giây đó có `network_ok=False` và không được đưa vào `FailureDetector.feed`.

- [ ] Step 1: Test trước

```python
def test_api_client_sends_host_header(fake_server):
    ApiClient(fake_server.url, host="api.dr.qivarn.id.vn").healthz()
    assert fake_server.last_headers["Host"] == "api.dr.qivarn.id.vn"

def test_network_outage_is_not_detected_as_incident():
    p = Prober({"public": always_failing()}, watch="public", interval=0, control=lambda: False)
    run_ticks(p, 10)
    assert not p.detected.is_set() and all(not s.network_ok for s in p.samples)

def test_failures_with_network_up_are_detected():
    p = Prober({"public": always_failing()}, watch="public", interval=0, control=lambda: True)
    run_ticks(p, 5)
    assert p.detected.is_set()
```

`fake_server`, `always_failing`, `run_ticks` là hàm dựng trong tệp test; nếu `test_kind_probe.py` đã có hàm tương tự thì dùng lại.

- [ ] Step 2: test FAIL. Step 3: sửa hai lớp. Step 4: `python -m pytest tests/scripts -q` PASS (trừ `test_kind_store` chmod trên Windows), và workflow `kind-mini` trên PR vẫn xanh vì bản kind không truyền `control`.

- [ ] Step 5: Commit `Đo: gọi thẳng từng cụm và điểm đối chứng mạng`

---

### Task 2: `step.sh` ghi giờ từng bước runbook

**Files:**
- Create: `scripts/azure/step.sh`, `tests/scripts/test_step_script.py`

**Interfaces:**
- Produces: `step.sh <run_id> <step> -- <lệnh...>`: `<step>` phải thuộc sáu bước ở Global Constraints, khác thì thoát 64. Ghi một dòng `step,started_at,ended_at,result` (UTC, `result` là `ok` hoặc `fail`) vào `$DR_DATA_DIR/drills/<run_id>/steps.csv`, trả đúng mã thoát của lệnh. `step.sh <run_id> --new` tạo thư mục, thoát 3 nếu thư mục đã có.

- [ ] Step 1: Test trước (chạy bằng `bash`, `DR_DATA_DIR` trỏ vào thư mục tạm)

```python
def test_records_ok_and_passes_exit_code(tmp_data):
    assert run_step("r1", "--new").returncode == 0
    assert run_step("r1", "restore", "--", "true").returncode == 0
    assert run_step("r1", "verify", "--", "false").returncode == 1
    rows = read_steps(tmp_data, "r1")
    assert [(r["step"], r["result"]) for r in rows] == [("restore", "ok"), ("verify", "fail")]

def test_unknown_step_is_refused(tmp_data):
    run_step("r1", "--new")
    assert run_step("r1", "deploy", "--", "true").returncode == 64

def test_new_refuses_existing_run(tmp_data):
    run_step("r1", "--new")
    assert run_step("r1", "--new").returncode == 3
```

- [ ] Step 2: FAIL. Step 3: viết `step.sh` (dùng `lib.sh` cho `die`). Step 4: PASS. Step 5: Commit `Đo: step.sh ghi giờ từng bước runbook`

---

### Task 3: Cụm dự phòng ấm

**Files:**
- Create: `infra/k8s/platform/db-replica.yaml.tpl`, `scripts/azure/standby-up.sh`, `scripts/azure/standby-down.sh`
- Modify: `scripts/azure/install-software.sh`, `scripts/azure/deploy-api.sh` (kho ảnh theo cụm đã có sẵn), `tests/scripts/test_session_scripts.py`

**Interfaces:**
- Consumes: `cluster-up.sh`, `install-software.sh`, `deploy-api.sh`, `refresh_admin_ip`, `session get server_name`.
- Produces:
  - `db-replica.yaml.tpl` giống `infra/kind/platform/db-replica.yaml.tpl` nhưng `barmanObjectName: japan-store`, thêm `archive_timeout: "60s"`, `__SOURCE_SERVER__` là `server_name` của cụm chính, `__SERVER__` là `standby-<giờ>`.
  - `install-software.sh <cluster> <server_name> <source_server>` với `DR_DB_MODE=replica` thì dựng cụm bản sao thay cho khôi phục; không tạo `ScheduledBackup` và lịch Velero khi là bản sao.
  - `standby-up.sh <image_tag>`: thoát 3 nếu `vm-dr-standby` đã có; thoát 5 nếu `session get state` khác `running`. Rồi `cluster-up.sh standby`, `DR_DB_MODE=replica install-software.sh standby standby-<giờ> <server_name hiện tại>`, `DR_READ_ONLY=true deploy-api.sh standby <image_tag>`; ghi `standby_server` vào `~/.dr/standby-server`; mốc vào `data/azure/standby.csv`.
  - `standby-down.sh`: `refresh_admin_ip standby`, `terraform destroy` stack `cluster` của `standby`, kiểm tra `az vm list -g rg-dr-standby` rỗng.

- [ ] Step 1: Test trước (dùng `FakeTools` có sẵn)

```python
def test_standby_up_refuses_when_primary_not_running(fake_tools):
    fake_tools.session = {"state": "stopped", "cluster": "primary"}
    assert fake_tools.run("standby-up.sh", "abc").returncode == 5

def test_standby_up_installs_replica_from_primary_server(fake_tools):
    fake_tools.session = {"state": "running", "cluster": "primary", "server_name": "primary-202610300100"}
    r = fake_tools.run("standby-up.sh", "abc")
    assert r.returncode == 0, r.stderr
    assert "primary-202610300100" in fake_tools.calls and "DR_DB_MODE=replica" in fake_tools.env_log

def test_standby_down_refreshes_admin_ip_first(fake_tools):
    fake_tools.vms = ["vm-dr-standby"]
    fake_tools.run("standby-down.sh")
    calls = fake_tools.calls
    assert calls.index("nsg rule update -g rg-dr-standby") < calls.index("destroy")
```

`FakeTools.env_log` là phần mở rộng nhỏ: công cụ giả ghi thêm `DR_DB_MODE` và `DR_READ_ONLY` vào `env.log`.

- [ ] Step 2: FAIL. Step 3: viết mẫu và script. Step 4: PASS.

- [ ] Step 5: Chạy thật. `session-start.sh primary <sha>`, rồi `standby-up.sh <sha>`.
Expected: trên cụm dự phòng `kubectl -n dr-api get clusters.postgresql.cnpg.io db` báo `Cluster in healthy state`, `psql -c "SELECT pg_is_in_recovery()"` trả `t`; đăng một bài ở cụm chính, sau tối đa 2 phút bài đó có ở cụm dự phòng; `curl --resolve api.dr.qivarn.id.vn:443:<ip dự phòng> https://api.dr.qivarn.id.vn/healthz` trả `"read_only":true`. Ghi độ trễ bản sao đo được vào `docs/trial-results.md` mục mới "Cụm dự phòng ấm".

- [ ] Step 6: Commit `Hạ tầng: cụm dự phòng ấm đọc WAL từ kho Nhật`

---

### Task 4: Lệnh chuyển cụm ấm và lạnh

**Files:**
- Create: `scripts/azure/failover-warm.sh`, `scripts/azure/failover-cold.sh`, `scripts/azure/copy-images.sh`, `tests/scripts/test_failover_scripts.py`

**Interfaces:**
- Consumes: `step.sh` (Task 2), `dns_switch.py`, `session set`, `refresh_admin_ip`, `session-start.sh`.
- Produces (mọi lệnh nhận `<run_id>` để `step.sh` ghi giờ; không có `run_id` thì chạy không ghi):
  - `failover-warm.sh <run_id>`: bước `restore`: `refresh_admin_ip standby`; vá `spec.replica.enabled=false` trên `clusters.postgresql.cnpg.io/db`; chờ `pg_is_in_recovery()` là `f` (tối đa 600 s); xóa chính sách object replication có đích là `drimgstb<sfx>` (`az storage account or-policy list/delete` trên tài khoản đích); đặt `IMAGE_STORE_READ_ONLY=false` trong ConfigMap `api-site`; `rollout restart deploy/api` và chờ. Bước `switch`: `dns_switch.py <ip dự phòng>`, rồi `session set cluster=standby server_name=<standby_server>`.
  - `failover-cold.sh <run_id> <cluster>`: bước `infra`: `cluster-up.sh <cluster>` (bỏ qua nếu máy đã có). Bước `restore`: `install-software.sh <cluster> <cluster>-<giờ> <server_name trong session.json>` rồi `deploy-api.sh`; nếu `DR_IMAGES_FROM_COPY=true` thì chạy `copy-images.sh` song song và chờ cả hai. Bước `switch`: như bản ấm.
  - `restore-namespace.sh <run_id> <target_time>` (D1, trên cụm chính): bước `restore`: tạo lại namespace `dr-api`; Velero khôi phục từ bản `hourly` mới nhất với `--selector 'app.kubernetes.io/managed-by notin (cloudnative-pg)'`; dựng `db` từ `db-recover.yaml.tpl` thêm `recoveryTarget.targetTime: <target_time>` (giờ phá trừ 1 giây) và `server_name` mới; chờ Ready; chờ `/healthz` trả 200; `session set server_name=<mới>`.
  - `copy-images.sh`: chép mọi blob trong `drimgcopy<sfx>/images` sang `drimgstb<sfx>/images` bằng `az storage blob copy start-batch`, chờ tới khi mọi blob ở đích có `copy.status=success`; in số ảnh và số giây.
  - Sau khi Terraform `storage` chạy lại, chính sách replication sang kho dự phòng được tạo lại: ghi rõ trong runbook bước dựng lại sau diễn tập.

- [ ] Step 1: Test trước (công cụ giả; `az storage account or-policy list` trả một chính sách có `destinationAccount` là `drimgstbabc123`)

```python
def test_warm_promotes_db_before_enabling_image_writes(fake_tools):
    r = fake_tools.run("failover-warm.sh", "r1")
    assert r.returncode == 0, r.stderr
    c = fake_tools.calls
    assert c.index('"replica":{"enabled":false}') < c.index("or-policy delete") < c.index("IMAGE_STORE_READ_ONLY=false")

def test_warm_switches_dns_and_session_together(fake_tools):
    fake_tools.run("failover-warm.sh", "r1")
    doc = fake_tools.session_doc()
    assert doc["cluster"] == "standby" and "dns_switch" in fake_tools.calls

def test_warm_stops_if_promotion_never_finishes(fake_tools):
    fake_tools.in_recovery = "t"
    r = fake_tools.run("failover-warm.sh", "r1")
    assert r.returncode == 1 and "dns_switch" not in fake_tools.calls

def test_restore_namespace_skips_cnpg_objects_and_targets_time(fake_tools):
    fake_tools.run("restore-namespace.sh", "r1", "2026-10-30T01:02:03Z")
    assert "managed-by notin (cloudnative-pg)" in fake_tools.calls
    assert "targetTime: 2026-10-30T01:02:03Z" in fake_tools.applied_yaml

def test_cold_copies_images_only_when_asked(fake_tools):
    fake_tools.run("failover-cold.sh", "r1", "standby")
    assert "copy start-batch" not in fake_tools.calls
    fake_tools.extra_env["DR_IMAGES_FROM_COPY"] = "true"
    fake_tools.run("failover-cold.sh", "r2", "standby")
    assert "copy start-batch" in fake_tools.calls
```

- [ ] Step 2: FAIL. Step 3: viết ba script. Step 4: PASS.
- [ ] Step 5: Commit `DR: lệnh chuyển cụm ấm và lạnh, chép ảnh từ Nhật`

---

### Task 5: Bộ dữ liệu mẫu và đưa về trạng thái ban đầu

**Files:**
- Create: `infra/k8s/platform/db-recover-to-backup.yaml.tpl`, `scripts/azure/seed.sh`, `scripts/azure/reset-seed.sh`
- Test: `tests/scripts/test_session_scripts.py` (thêm)

**Interfaces:**
- Produces:
  - `seed.sh`: chỉ chạy khi phiên `running` và cơ sở dữ liệu có dưới 100 bài, khác thì thoát 3. Đăng 1.000 bài bằng `python -m scripts.kind.workload seed` (nếu dòng lệnh này chưa có thì thêm, dùng `seed(api, ledger, 1000, workers=8)`), sổ ghi ở `~/.dr/seed-ledger.csv`. Rồi tạo bản đầy đủ CNPG tên `seed-<giờ>` và ghi `.status.backupId` của nó cùng `server_name` vào `~/.dr/seed.json`.
  - `db-recover-to-backup.yaml.tpl`: như `db-recover.yaml.tpl` nhưng thêm `bootstrap.recovery.recoveryTarget.backupID: __BACKUP_ID__`.
  - `reset-seed.sh <cluster>`: xóa `clusters.postgresql.cnpg.io/db`, dựng lại từ mẫu trên với `server_name` mới `<cluster>-<giờ>`, chờ Ready, `rollout restart deploy/api`, chép `~/.dr/seed-ledger.csv` thành sổ của lần diễn tập kế tiếp, cập nhật `session.json`. Sau khi xong, `SELECT count(*) FROM posts` phải là 1000.

- [ ] Step 1: Test trước cho phần chặn

```python
def test_seed_refuses_non_empty_database(fake_tools):
    fake_tools.session = {"state": "running", "cluster": "primary"}
    fake_tools.post_count = 25
    assert fake_tools.run("seed.sh").returncode == 3

def test_reset_uses_recorded_backup_id(fake_tools, tmp_path):
    fake_tools.private.joinpath("seed.json").write_text('{"backup_id": "20261030T010203", "server_name": "primary-202610300100"}')
    fake_tools.session = {"state": "running", "cluster": "primary"}
    fake_tools.run("reset-seed.sh", "primary")
    assert "20261030T010203" in fake_tools.applied_yaml
```

- [ ] Step 2: FAIL. Step 3: viết. Step 4: PASS.
- [ ] Step 5: Chạy thật một lần. Expected: `seed.sh` xong dưới 20 phút; `reset-seed.sh primary` đưa số bài về 1000 và mã băm nội dung trùng với lúc tạo mẫu. Nếu CNPG không nhận `recoveryTarget.backupID` với plugin, ghi lỗi thật vào `docs/trial-results.md` và chuyển sang khôi phục theo thời điểm (`targetTime` là giờ kết thúc của bản `seed`).
- [ ] Step 6: Commit `Đo: bộ dữ liệu mẫu 1.000 bài và lệnh đưa về mẫu`

---

### Task 6: Cách phá và trình điều khiển một lần diễn tập

**Files:**
- Create: `scripts/azure/break.sh`, `scripts/dr/azure_drill.py`, `tests/scripts/test_azure_drill.py`

**Interfaces:**
- Consumes: `ApiClient(host=...)`, `Prober(control=...)` (Task 1), `Ledger`, `Writer`, `read_ledger`, `post_one` (`scripts/kind/workload.py`), `compare`, `content_digest`, `check_images` (`scripts/kind/verify.py`), `results.step_row`, `results.append_rows`, `STEP_FIELDS`, `RUN_FIELDS` (`scripts/kind/results.py`), `step.sh` và các lệnh chuyển cụm (Task 2, 4).
- Produces:
  - `break.sh <scenario>`: `D1` xóa namespace `dr-api` trên cụm chính; `D2`, `D3` `az vm delete -g rg-dr-primary -n vm-dr-primary --yes --force-deletion true --no-wait`; `D4`, `D5` `az group delete -n rg-dr-primary --yes --no-wait`. Mọi nhánh in giờ UTC bắt đầu phá.
  - `RUNBOOK: dict[str, list[tuple[str, list[str]]]]` trong `azure_drill.py`: với mỗi tình huống, danh sách `(step, lệnh)` cho các bước `infra`, `restore`, `switch`. D1: `infra` là `not_needed`, `restore` là `restore-namespace.sh <run_id> <giờ phá - 1 s>`, `switch` là `not_needed`. D2: `failover-cold.sh <run_id> standby`. D3: `failover-warm.sh <run_id>`. D4: như D2 với `DR_IMAGES_FROM_COPY=true`. D5: như D3.
  - `def run(scenario: str, run_id: str, iteration: int, decide: Callable[[], None]) -> bool`: kiểm tra trước (cụm chính `/healthz` trả 200; D3, D5 thì cụm dự phòng cũng trả 200 và đang `read_only`); tạo `step.sh <run_id> --new`; chạy `Writer` 1 bài/giây vào `https://api.dr.qivarn.id.vn` và `Prober` với ba đích `public`, `primary`, `standby` (gọi thẳng IP) cộng đối chứng `https://www.gstatic.com/generate_204`; chờ 90 s; `break.sh`; chờ phát hiện (tối đa 180 s); gọi `decide()`; chạy `RUNBOOK[scenario]`; kiểm tra (bước `verify`) bằng `compare` trên cụm đang phục vụ; ghi `steps.csv` và `runs.csv` vào `data/drills/<run_id>/` với cùng cột như bản kind. Trả `True` khi kiểm tra đạt.
  - Dòng lệnh: `python -m scripts.dr.azure_drill <D1..D5> --run-id <id> [--iteration N] [--auto-decide]`. Không có `--auto-decide` thì `decide` chờ người trực nhấn Enter, và giờ nhấn là mốc kết thúc bước `decide`.

- [ ] Step 1: Test trước (giả `subprocess`, `ApiClient`, đồng hồ)

```python
def test_runbook_covers_three_steps_for_each_scenario():
    for s in ("D1", "D2", "D3", "D4", "D5"):
        assert [step for step, _ in RUNBOOK[s]] == ["infra", "restore", "switch"]

def test_d4_cold_copies_images():
    assert any("DR_IMAGES_FROM_COPY=true" in " ".join(cmd) for _, cmd in RUNBOOK["D4"])

def test_run_refuses_warm_scenario_without_standby(fake_env):
    fake_env.standby_health = None
    assert run("D3", "r1", 1, decide=lambda: None) is False and fake_env.broke is False

def test_decide_time_is_recorded_between_detect_and_infra(fake_env):
    run("D2", "r1", 1, decide=fake_env.advance(seconds=42))
    steps = fake_env.steps("r1")
    assert steps["decide"].duration_s == 42 and steps["decide"].ended_at <= steps["infra"].started_at

def test_network_outage_seconds_excluded_from_detect(fake_env):
    fake_env.control_down_for = 10
    run("D2", "r1", 1, decide=lambda: None)
    assert fake_env.steps("r1")["detect"].duration_s < 15
```

- [ ] Step 2: FAIL. Step 3: viết `break.sh` và `azure_drill.py`. Step 4: PASS.
- [ ] Step 5: Commit `DR: trình điều khiển diễn tập trên Azure và năm cách phá`

---

### Task 7: Vòng thử D1 tới D5, biên bản và runbook

**Files:**
- Create: `docs/dien-tap/README.md` (mẫu biên bản), `docs/dien-tap/<run_id>.md` (năm biên bản)
- Modify: `docs/runbook.md`, `docs/trial-results.md`, `scripts/README.md`

**Interfaces:**
- Consumes: mọi thứ ở Task 1 tới 6.

- [ ] Step 1: Mẫu biên bản `docs/dien-tap/README.md`: mã lần, tình huống, người chạy, người bấm giờ, giờ phá, sáu bước với giờ máy ghi và giờ bấm tay, kết quả kiểm tra (bài thiếu, RPO, ảnh hỏng, chức năng), sự cố ngoài kế hoạch, sửa runbook gì.

- [ ] Step 2: Chuẩn bị mỗi lần: `session-start.sh primary <sha>`; lần đầu `seed.sh`, các lần sau `reset-seed.sh primary`; D3, D5 thêm `standby-up.sh <sha>`; laptop đồng bộ giờ (`w32tm /resync`).

- [ ] Step 3: Chạy lần lượt `python -m scripts.dr.azure_drill D1 --run-id trial-D1-1`, rồi D2, D3, D4, D5. Sau mỗi lần dựng lại trạng thái ban đầu: D2, D3 thì `terraform` stack `cluster` của `primary` bị xóa ngoài Terraform nên chạy `terraform state rm` cho máy ảo rồi `session-stop.sh standby` và `session-start.sh primary <sha>`; D4, D5 thì thêm Terraform `storage` apply để tạo lại `rg-dr-primary`, kho ảnh chính và chính sách replication.
Expected mỗi lần: `data/drills/<run_id>/steps.csv` có đủ sáu bước, `runs.csv` có `result=pass`. Lần nào `fail` thì ghi nguyên nhân vào biên bản, sửa, chạy lại đúng tình huống đó.

- [ ] Step 4: Sửa `docs/runbook.md` theo những gì đã làm thật: mỗi bước một lệnh có `step.sh`, ai quyết định, mẫu tin nhắn Zalo (mục 6.2), bước dựng lại sau diễn tập, chỗ để chìa khóa (không ghi chìa).

- [ ] Step 5: `docs/trial-results.md` mục mới "Vòng thử" với bảng sáu bước của năm lần, RPO thật, so với mục tiêu ở mục 3.

- [ ] Step 6: Tắt hết: `session-stop.sh <cụm đang chính>`, `standby-down.sh` nếu còn; `az vm list -g rg-dr-primary` và `-g rg-dr-standby` rỗng.

- [ ] Step 7: Commit `Diễn tập: vòng thử D1 tới D5, biên bản và runbook sửa theo thực tế`

---

## Ngoài kế hoạch này

- Két, mã hóa `age`, D6 và D7 trên Azure: kế hoạch `2026-10-29-vault-age.md`.
- Vòng chính thức (D1 tới D5 mỗi tình huống 3 lần, có lần không báo trước, có lượt do Huong-19 hoặc minhthw1605 tự chạy): dùng nguyên công cụ của kế hoạch này, chỉ khác lịch chạy.
- Server của bạn (tầng 3, mục 4.3), nút kích hoạt trên GitHub (mục 6.2): làm thêm nếu kịp.
- Script vẽ biểu đồ từ `data/drills/` (giao cho minhthw1605 theo bảng phân công).
