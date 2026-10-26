"""Chạy một lần diễn tập trên bản thu nhỏ và ghi số đo (mục 5 và 6 thiết kế).

    python -m scripts.kind.scenario D1|D2|D3|D6 --run-id ID [--iteration N]

Cần môi trường do `up.sh` dựng (D3 cần hồ sơ full). Sáu bước của mục 5.2:
detect, decide, infra, restore, verify, switch. Bản thu nhỏ không có DNS nên bước switch
luôn ghi `not_applicable` (mục 6.4), và RTO ở đây là tổng năm bước đầu.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from scripts.kind import results, store
from scripts.kind.probe import Prober, wait_healthy
from scripts.kind.verify import check_images, compare, content_digest
from scripts.kind.workload import ApiClient, Ledger, Writer, post_one, read_ledger

ROOT = Path(__file__).resolve().parents[2]
STATE = Path(os.environ.get("DR_KIND_STATE", Path.home() / ".dr-kind"))
DATA = Path(os.environ.get("DR_KIND_DATA", ROOT / "data" / "kind"))
PORTS = {"primary": int(os.environ.get("PRIMARY_PORT", 18080)),
         "standby": int(os.environ.get("STANDBY_PORT", 28080))}
WARMUP_S = float(os.environ.get("WARMUP_S", 90))
# Velero sao lưu cấu hình của namespace, không lấy cơ sở dữ liệu (mục 4.2): bỏ Cluster CNPG,
# ổ đĩa, pod và mọi đối tượng CNPG tự sinh (nhãn app.kubernetes.io/managed-by=cloudnative-pg), để CNPG
# tự dựng lại cùng cơ sở dữ liệu.
VELERO_EXCLUDED = [
    "clusters.postgresql.cnpg.io", "backups.postgresql.cnpg.io", "scheduledbackups.postgresql.cnpg.io",
    "persistentvolumeclaims", "persistentvolumes", "pods", "replicasets.apps", "endpoints",
    "endpointslices.discovery.k8s.io", "events", "events.events.k8s.io",
]


def now() -> datetime:
    return datetime.now(UTC)


def log(msg: str) -> None:
    print(f"{now():%H:%M:%S} {msg}", file=sys.stderr, flush=True)


def run(cmd: list[str], input: str | None = None, timeout: float = 900, check: bool = True) -> str:
    p = subprocess.run(cmd, input=input, capture_output=True, text=True, timeout=timeout)
    if check and p.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd[:6])} lỗi {p.returncode}: {p.stderr.strip()[-800:]}")
    return p.stdout


def kubectl(cluster: str, *args: str, **kw) -> str:
    return run(["kubectl", "--context", f"kind-{cluster}", *args], **kw)


def lib(*args: str, timeout: float = 1800) -> str:
    """Gọi một hàm của lib.sh để Python và bash dùng chung một cách làm."""
    script = f'source "{ROOT}/scripts/kind/lib.sh"; "$@"'
    return run(["bash", "-c", script, "lib", *args], timeout=timeout)


def api(cluster: str) -> ApiClient:
    return ApiClient(f"http://127.0.0.1:{PORTS[cluster]}", (STATE / "secret-code").read_text().strip())


def server_name(cluster: str) -> str:
    return f"{cluster}-{now():%Y%m%d%H%M%S}"


def apply_template(cluster: str, tpl: str, **values: str) -> None:
    text = (ROOT / "infra" / "kind" / "platform" / tpl).read_text()
    for k, v in values.items():
        text = text.replace(f"__{k}__", v)
    kubectl(cluster, "apply", "-f", "-", input=text)


def wait_for(cond, timeout: float, what: str, interval: float = 1.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = cond()
        if value:
            return value
        time.sleep(interval)
    raise TimeoutError(f"quá {timeout:.0f} s chờ {what}")


# ---------- Velero bằng tài nguyên Kubernetes, không cần CLI velero ----------

VELERO_DONE = ("Completed", "PartiallyFailed", "Failed", "FailedValidation")


def velero_backup(cluster: str, name: str) -> None:
    doc = {
        "apiVersion": "velero.io/v1", "kind": "Backup",
        "metadata": {"name": name, "namespace": "velero"},
        "spec": {
            "includedNamespaces": ["dr-api"], "excludedResources": VELERO_EXCLUDED,
            "labelSelector": {"matchExpressions": [{"key": "app.kubernetes.io/managed-by", "operator": "NotIn",
                                                    "values": ["cloudnative-pg"]}]},
            "snapshotVolumes": False, "ttl": "72h0m0s",
        },
    }
    kubectl(cluster, "apply", "-f", "-", input=json.dumps(doc))
    phase = wait_for(lambda: (p := velero_phase(cluster, "backups", name)) in VELERO_DONE and p,
                     600, f"bản Velero {name}")
    if phase != "Completed":
        raise RuntimeError(f"bản Velero {name} kết thúc ở {phase}")


def velero_phase(cluster: str, kind: str, name: str) -> str:
    return kubectl(cluster, "-n", "velero", "get", f"{kind}.velero.io", name, "-o",
                   "jsonpath={.status.phase}", check=False).strip()


def velero_restore(cluster: str, backup: str) -> str:
    # Cụm mới thấy bản sao lưu sau một chu kỳ đồng bộ của Velero (10 s, xem values/velero.yaml.tpl).
    wait_for(lambda: velero_phase(cluster, "backups", backup) == "Completed", 300, f"Velero ở {cluster} thấy {backup}")
    name = f"restore-{now():%Y%m%d%H%M%S}"
    doc = {
        "apiVersion": "velero.io/v1", "kind": "Restore",
        "metadata": {"name": name, "namespace": "velero"},
        "spec": {"backupName": backup, "includedNamespaces": ["dr-api"], "preserveNodePorts": True,
                 "existingResourcePolicy": "none"},
    }
    kubectl(cluster, "apply", "-f", "-", input=json.dumps(doc))
    phase = wait_for(lambda: (p := velero_phase(cluster, "restores", name)) in VELERO_DONE and p,
                     600, f"Velero khôi phục {backup}")
    if phase not in ("Completed", "PartiallyFailed"):
        raise RuntimeError(f"Velero khôi phục {backup} kết thúc ở {phase}")
    return phase


# ---------- Cơ sở dữ liệu ----------

def db_pod(cluster: str) -> str:
    return kubectl(cluster, "-n", "dr-api", "get", "pod", "-l", "cnpg.io/cluster=db,cnpg.io/instanceRole=primary",
                   "-o", "jsonpath={.items[0].metadata.name}").strip()


def psql(cluster: str, sql: str) -> str:
    return kubectl(cluster, "-n", "dr-api", "exec", db_pod(cluster), "-c", "postgres", "--",
                   "psql", "-U", "postgres", "-d", "dr", "-AtF,", "-c", sql)


def db_rows(cluster: str) -> dict[str, str]:
    out = psql(cluster, "SELECT id, encode(image_sha256, 'hex') FROM posts")
    return dict(line.split(",", 1) for line in out.splitlines() if line)


def db_digest(cluster: str) -> str:
    return psql(cluster, "SELECT md5(string_agg(id::text || ':' || encode(image_sha256, 'hex'), ',' ORDER BY id)) "
                         "FROM posts").strip()


def lose_cluster(cluster: str) -> None:
    """Mất cụm đột ngột như mất máy: dừng ngay container của nút, rồi dọn cụm (không tính giờ)."""
    run(["docker", "kill", f"{cluster}-control-plane"])
    threading.Thread(target=run, args=(["kind", "delete", "cluster", "--name", cluster],), daemon=True).start()


# ---------- Một lần diễn tập ----------

class Drill:
    def __init__(self, scenario: str, run_id: str, iteration: int):
        self.scenario, self.run_id, self.iteration = scenario, run_id, iteration
        self.ledger_path = STATE / "ledger.csv"
        self.ledger = Ledger(self.ledger_path)
        self.times: dict[str, datetime] = {}
        self.step_results: dict[str, str] = {}
        self.target = "primary"

    def prepare(self, with_standby: bool) -> tuple[Writer, Prober]:
        wait_healthy(api("primary"), 120)
        # Trước mỗi lần diễn tập: bản đầy đủ của cơ sở dữ liệu và một bản Velero (mục 4.1).
        self.backup = f"pre-{self.run_id}".lower()[:63]
        log("bản đầy đủ và bản Velero trước diễn tập")
        lib("db_backup", "primary", self.backup)
        velero_backup("primary", self.backup)
        targets = {"primary": api("primary")}
        if with_standby:
            targets["standby"] = api("standby")
        writer = Writer(api("primary"), self.ledger)
        prober = Prober(targets, watch="primary")
        writer.start()
        prober.start()
        log(f"đăng 1 bài/giây trong {WARMUP_S:.0f} s trước sự cố")
        time.sleep(WARMUP_S)
        return writer, prober

    def incident(self, breaker, writer: Writer, prober: Prober) -> None:
        self.times["incident"] = now()
        log(f"{self.scenario}: sự cố")
        breaker()
        if not prober.detected.wait(180):
            raise TimeoutError("không phát hiện được sự cố trong 180 s")
        self.times["detected"] = prober.detector.detected_at
        writer.stop()
        log(f"phát hiện sau {(self.times['detected'] - self.times['incident']).total_seconds():.1f} s; "
            f"đã xác nhận {writer.acked} bài trong lúc chạy")
        # Quyết định kích hoạt: tự động, ngay khi phát hiện (người trực ở bản thu nhỏ là script).
        self.times["decided"] = now()

    def verify(self, cluster: str) -> dict:
        start = now()
        rows = db_rows(cluster)
        ledger = read_ledger(self.ledger_path)
        report = compare(ledger, rows, self.times["incident"])
        pg_digest = db_digest(cluster)
        if pg_digest != content_digest(rows):
            raise RuntimeError("mã nội dung tính trong Postgres khác mã tính trong Python")
        client = api(cluster)
        client.timeout = 30
        report.images_checked = len(rows)
        report.images_bad = check_images(rows, client.image)
        # Chức năng: đăng một bài mới rồi đọc lại ảnh (bài thử giữ lại, mục 5.3).
        try:
            entry = post_one(client, self.ledger, max(e.seq for e in ledger) + 1, "check")
            data = client.image(entry.post_id)
            functional = data is not None and hashlib.sha256(data).hexdigest() == entry.sha256
        except Exception as e:
            log(f"kiểm tra chức năng lỗi: {e}")
            functional = False
        self.times["verify_start"], self.times["verified"] = start, now()
        log(f"kiểm tra: {report.posts_restored}/{report.posts_acked} bài còn, thiếu {report.posts_missing} "
            f"(RPO {report.rpo_s} s), lỗ hổng {report.posts_holes}, ngoài sổ {report.posts_extra}, "
            f"mã nội dung {'khớp' if report.digest_match else 'KHÁC'}, ảnh hỏng {len(report.images_bad)}, "
            f"chức năng {'đạt' if functional else 'LỖI'}")
        return {"report": report, "digest": pg_digest, "functional": functional}

    def write(self, outcome: dict) -> bool:
        t = self.times
        rows = [
            results.step_row(self.run_id, self.scenario, self.iteration, "detect", t["incident"], t["detected"], "ok"),
            results.step_row(self.run_id, self.scenario, self.iteration, "decide", t["detected"], t["decided"], "ok"),
            results.step_row(self.run_id, self.scenario, self.iteration, "infra", t["decided"], t["infra_done"],
                             self.step_results.get("infra", "ok")),
            results.step_row(self.run_id, self.scenario, self.iteration, "restore", t["infra_done"], t["restored"],
                             "ok"),
        ]
        r = outcome["report"]
        passed = r.ok and outcome["functional"]
        rows.append(results.step_row(self.run_id, self.scenario, self.iteration, "verify", t["restored"],
                                     t["verified"], "ok" if passed else "fail"))
        rows.append(results.step_row(self.run_id, self.scenario, self.iteration, "switch", None, None,
                                     "not_applicable"))
        results.append_rows(DATA / "steps.csv", results.STEP_FIELDS, rows)
        results.append_rows(DATA / "runs.csv", results.RUN_FIELDS, [{
            **runner_info(), "run_id": self.run_id, "scenario": self.scenario, "iteration": self.iteration,
            "seed_posts": sum(e.source == "seed" for e in read_ledger(self.ledger_path)),
            "incident_at": results.iso(t["incident"]), "detected_at": results.iso(t["detected"]),
            "service_restored_at": results.iso(t["restored"]), "verified_at": results.iso(t["verified"]),
            "rto_s": f"{(t['verified'] - t['incident']).total_seconds():.1f}",
            "posts_acked": r.posts_acked, "posts_restored": r.posts_restored, "posts_missing": r.posts_missing,
            "posts_missing_beyond_rpo": r.posts_missing_beyond_rpo, "posts_holes": r.posts_holes,
            "posts_extra": r.posts_extra, "rpo_s": r.rpo_s, "digest_match": str(r.digest_match).lower(),
            "content_digest": outcome["digest"], "images_checked": r.images_checked,
            "images_bad": len(r.images_bad), "functional_ok": str(outcome["functional"]).lower(),
            "result": "pass" if passed else "fail",
        }])
        log(f"{self.scenario} {'ĐẠT' if passed else 'KHÔNG ĐẠT'}: RTO (5 bước) "
            f"{(t['verified'] - t['incident']).total_seconds():.1f} s")
        return passed


def runner_info() -> dict:
    mem = 0
    try:
        from scripts.kind.resources import parse_meminfo
        mem = parse_meminfo(Path("/proc/meminfo").read_text())[0]
    except OSError:
        pass
    return {"runner": os.environ.get("RUNNER_NAME", platform.node()), "cpus": os.cpu_count(), "mem_total_mb": mem}


def restore_cold(d: Drill, cluster: str, bucket: str) -> None:
    """Dựng cơ sở dữ liệu bằng CNPG và cấu hình bằng Velero, chạy song song (mục 3, 6.1)."""
    source = (STATE / "server-primary").read_text().strip()
    new = server_name(cluster)
    lib("site_config", cluster, bucket, "false")
    kubectl(cluster, "apply", "-f", str(ROOT / "infra/kind/platform/object-store.yaml"))
    apply_template(cluster, "db-recover.yaml.tpl", SERVER=new, SOURCE_SERVER=source)
    (STATE / f"server-{cluster}").write_text(new)
    errors: list[Exception] = []

    def velero() -> None:
        try:
            phase = velero_restore(cluster, d.backup)
            log(f"Velero khôi phục cấu hình: {phase}")
        except Exception as e:
            errors.append(e)

    t = threading.Thread(target=velero)
    t.start()
    lib("wait_db", cluster)
    log("CNPG: cơ sở dữ liệu Ready")
    t.join()
    if errors:
        raise errors[0]
    d.times["restored"] = wait_healthy(api(cluster), 600)


def d1(d: Drill) -> None:
    writer, prober = d.prepare(with_standby=False)
    d.incident(lambda: kubectl("primary", "delete", "namespace", "dr-api", "--wait=false"), writer, prober)
    # Dựng hạ tầng: namespace cũ phải xóa xong mới khôi phục vào được.
    wait_for(lambda: kubectl("primary", "get", "namespace", "dr-api", check=False) == "", 600,
             "namespace dr-api xóa xong")
    d.times["infra_done"] = now()
    restore_cold(d, "primary", "images")
    prober.stop()
    d.write(d.verify("primary")) or sys.exit(1)


def d2(d: Drill) -> None:
    if "standby" in run(["kind", "get", "clusters"]).split():
        log("cách lạnh: xóa cụm dự phòng có sẵn trước khi diễn tập")
        run(["kind", "delete", "cluster", "--name", "standby"])
    writer, prober = d.prepare(with_standby=False)
    d.incident(lambda: lose_cluster("primary"), writer, prober)
    os.environ["DR_KIND_RUN_ID"] = d.run_id
    run([str(ROOT / "scripts/kind/create-cluster.sh"), "standby"], timeout=1800)
    d.times["infra_done"] = now()
    # Ảnh: dùng bản chép (images-copy), kho ảnh chính coi như mất cùng cụm.
    restore_cold(d, "standby", "images-copy")
    prober.stop()
    d.write(d.verify("standby")) or sys.exit(1)


def d3(d: Drill) -> None:
    lib("wait_db", "standby", "60s")
    writer, prober = d.prepare(with_standby=True)
    d.incident(lambda: lose_cluster("primary"), writer, prober)
    # Cách ấm: cụm dự phòng đã chạy sẵn, không phải dựng gì.
    d.times["infra_done"] = now()
    d.step_results["infra"] = "not_needed"
    kubectl("standby", "-n", "dr-api", "patch", "clusters.postgresql.cnpg.io", "db", "--type", "merge",
            "-p", '{"spec":{"replica":{"enabled":false}}}')
    wait_for(lambda: psql("standby", "SELECT pg_is_in_recovery()").strip() == "f", 600, "Postgres dự phòng thành chính")
    log("Postgres ở cụm dự phòng đã thành cụm chính")
    # API ở cụm dự phòng để 0 bản chạy (xem up.sh), giờ mới bật.
    kubectl("standby", "-n", "dr-api", "scale", "deploy/api", "--replicas=1")
    d.times["restored"] = wait_healthy(api("standby"), 600)
    prober.stop()
    d.write(d.verify("standby")) or sys.exit(1)


D6_ATTEMPTS = [
    # (tên, danh tính, mong bị từ chối)
    ("delete_version", "admin", True),
    ("delete_version_bypass_governance", "admin", True),
    ("shorten_retention", "admin", True),
    ("delete_version_as_writer", "vault-writer", True),
    ("delete_bucket", "admin", True),
    ("overwrite", "admin", False),
    ("delete_latest", "admin", False),
]


def d6(d: Drill) -> None:
    """Thử xóa và ghi đè két bằng khóa tài khoản; đúng là bị từ chối và bản gốc còn nguyên."""
    from botocore.exceptions import ClientError

    creds = store.load(STATE)
    admin = store.client(creds)
    writer = store.client(creds, "vault-writer")
    pod = db_pod("primary")
    dump = subprocess.run(["kubectl", "--context", "kind-primary", "-n", "dr-api", "exec", pod, "-c", "postgres",
                           "--", "pg_dump", "-U", "postgres", "-Fc", "dr"], capture_output=True, check=True).stdout
    key = f"bundles/{d.run_id}/dr.dump"
    sha = hashlib.sha256(dump).hexdigest()
    version = writer.put_object(Bucket=store.VAULT_BUCKET, Key=key, Body=dump)["VersionId"]
    log(f"job két: tải lên {key} ({len(dump)} byte), phiên bản {version}")

    def intact() -> bool:
        try:
            body = admin.get_object(Bucket=store.VAULT_BUCKET, Key=key, VersionId=version)["Body"].read()
            return hashlib.sha256(body).hexdigest() == sha
        except ClientError:
            return False

    def attempt(name: str, who: str) -> None:
        s3 = store.client(creds, who)
        b = store.VAULT_BUCKET
        if name in ("delete_version", "delete_version_as_writer"):
            s3.delete_object(Bucket=b, Key=key, VersionId=version)
        elif name == "delete_version_bypass_governance":
            s3.delete_object(Bucket=b, Key=key, VersionId=version, BypassGovernanceRetention=True)
        elif name == "shorten_retention":
            s3.put_object_retention(Bucket=b, Key=key, VersionId=version, BypassGovernanceRetention=True,
                                    Retention={"Mode": "COMPLIANCE", "RetainUntilDate": now() + timedelta(seconds=5)})
        elif name == "delete_bucket":
            s3.delete_bucket(Bucket=b)
        elif name == "overwrite":
            s3.put_object(Bucket=b, Key=key, Body=b"ghi de")
        elif name == "delete_latest":
            s3.delete_object(Bucket=b, Key=key)

    rows, all_ok = [], True
    for name, who, expect_refused in D6_ATTEMPTS:
        code = ""
        try:
            attempt(name, who)
            refused = False
        except ClientError as e:
            refused, code = True, e.response["Error"]["Code"]
        ok_intact = intact()
        passed = ok_intact and refused == expect_refused
        all_ok &= passed
        log(f"D6 {name} ({who}): {'bị từ chối ' + code if refused else 'được chấp nhận'}, "
            f"bản gốc {'còn nguyên' if ok_intact else 'MẤT'}")
        rows.append({"run_id": d.run_id, "iteration": d.iteration, "attempt": name, "identity": who,
                     "refused": str(refused).lower(), "error_code": code,
                     "original_intact": str(ok_intact).lower(), "result": "pass" if passed else "fail"})
    results.append_rows(DATA / "d6.csv", results.D6_FIELDS, rows)
    results.append_rows(DATA / "runs.csv", results.RUN_FIELDS, [{
        **runner_info(), "run_id": d.run_id, "scenario": "D6", "iteration": d.iteration,
        "result": "pass" if all_ok else "fail"}])
    all_ok or sys.exit(1)


SCENARIOS = {"D1": d1, "D2": d2, "D3": d3, "D6": d6}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m scripts.kind.scenario")
    p.add_argument("scenario", choices=sorted(SCENARIOS))
    p.add_argument("--run-id", default=None)
    p.add_argument("--iteration", type=int, default=1)
    a = p.parse_args(argv)
    run_id = a.run_id or f"local-{a.scenario}-{now():%Y%m%d%H%M%S}"
    SCENARIOS[a.scenario](Drill(a.scenario, run_id, a.iteration))
    return 0


if __name__ == "__main__":
    sys.exit(main())
