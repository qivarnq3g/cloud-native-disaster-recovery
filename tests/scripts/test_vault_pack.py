import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
import urllib.error
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from scripts.vault.blob import BlobExists, BlobInfo, download, list_blobs, upload_new
from scripts.vault.pack import fetch_age, newest_pack_time, run, seal_pack, select_images

T0 = datetime(2026, 10, 30, 1, 0, tzinfo=UTC)


class FakeResponse(io.BytesIO):
    def __init__(self, body: bytes = b"", status: int = 201):
        super().__init__(body)
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class Recorder:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, request, timeout=None):
        self.requests.append(request)
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def status(code):
    def http(request, timeout=None):
        if code >= 400:
            raise urllib.error.HTTPError(request.full_url, code, "x", {}, io.BytesIO(b""))
        return FakeResponse(status=code)
    return http


def tmp_file(tmp_path: Path) -> Path:
    p = tmp_path / "src.bin"
    p.write_bytes(b"data")
    return p


def small(tmp_path: Path, name: str = "small.bin") -> Path:
    p = tmp_path / name
    p.write_bytes(b"x" * 10)
    return p


def listing(names_times, marker=""):
    blobs = "".join(
        f"<Blob><Name>{n}</Name><Properties><Last-Modified>{t}</Last-Modified>"
        f"<Content-Length>{s}</Content-Length></Properties></Blob>"
        for n, t, s in names_times)
    return (f'<?xml version="1.0" encoding="utf-8"?><EnumerationResults><Blobs>{blobs}</Blobs>'
            f"<NextMarker>{marker}</NextMarker></EnumerationResults>").encode()


def test_newest_pack_time_only_looks_at_same_server():
    names = ["primary-1/20261030T010000Z.tar.age", "primary-2/20261031T010000Z.tar.age"]
    assert newest_pack_time(names, "primary-1") == datetime(2026, 10, 30, 1, 0, tzinfo=UTC)


def test_newest_pack_time_is_none_without_packs():
    assert newest_pack_time(["primary-2/20261031T010000Z.tar.age"], "primary-1") is None


def test_first_pack_takes_all_images():
    imgs = [BlobInfo("a.png", T0, 10), BlobInfo("b.png", T0 + timedelta(hours=1), 10)]
    assert select_images(imgs, None) == ["a.png", "b.png"]


def test_later_pack_takes_only_newer_images():
    imgs = [BlobInfo("a.png", T0, 10), BlobInfo("b.png", T0 + timedelta(hours=1), 10)]
    assert select_images(imgs, T0) == ["b.png"]


def test_list_blobs_follows_next_marker():
    http = Recorder([
        FakeResponse(listing([("a.png", "Fri, 30 Oct 2026 01:00:00 GMT", 3)], marker="m2"), 200),
        FakeResponse(listing([("b.png", "Fri, 30 Oct 2026 02:00:00 GMT", 4)]), 200),
    ])
    blobs = list_blobs("https://acct.blob.core.windows.net/images", "sv=1&sig=s", http=http)
    assert blobs == [BlobInfo("a.png", T0, 3), BlobInfo("b.png", T0 + timedelta(hours=1), 4)]
    assert "marker=m2" in http.requests[1].full_url
    assert "restype=container&comp=list" in http.requests[0].full_url


def test_download_writes_body_to_file(tmp_path):
    http = Recorder([FakeResponse(b"payload", 200)])
    download("https://x/images", "sig=s", "a b.png", tmp_path / "out", http=http)
    assert (tmp_path / "out").read_bytes() == b"payload"
    assert http.requests[0].full_url == "https://x/images/a%20b.png?sig=s"


def test_upload_new_never_overwrites(tmp_path):
    http = Recorder([FakeResponse(status=201)])
    upload_new("https://x/vault", "sig=s", "p/1.tar.age", tmp_file(tmp_path), http=http)
    req = http.requests[0]
    assert req.get_method() == "PUT"
    assert req.get_header("If-none-match") == "*"
    assert req.get_header("X-ms-blob-type") == "BlockBlob"


def test_upload_new_raises_on_existing_name(tmp_path):
    with pytest.raises(BlobExists):
        upload_new("https://x/vault", "sig", "n", tmp_file(tmp_path), http=status(409))


def test_upload_new_treats_worm_overwrite_refusal_as_existing(tmp_path):
    def http(request, timeout=None):
        raise urllib.error.HTTPError(request.full_url, 403, "x", {"x-ms-error-code": "UnauthorizedBlobOverwrite"},
                                     io.BytesIO(b""))
    with pytest.raises(BlobExists):
        upload_new("https://x/vault", "sig", "n", tmp_file(tmp_path), http=http)


def test_upload_new_reraises_other_errors(tmp_path):
    with pytest.raises(urllib.error.HTTPError):
        upload_new("https://x/vault", "sig", "n", tmp_file(tmp_path), http=status(403))


@pytest.fixture
def fake_age(tmp_path):
    log = tmp_path / "age-args.json"
    script = tmp_path / "fake_age.py"
    script.write_text(
        "import json, shutil, sys\n"
        f"json.dump(sys.argv[1:], open({str(log)!r}, 'w'))\n"
        "if 'FAIL' in open(sys.argv[2]).read():\n"
        "    sys.exit(1)\n"
        "out = sys.argv[sys.argv.index('-o') + 1]\n"
        "shutil.copyfileobj(sys.stdin.buffer, open(out, 'wb'))\n")
    if os.name == "nt":
        path = tmp_path / "age.cmd"
        path.write_text(f'@"{sys.executable}" "{script}" %*\n')
    else:
        path = tmp_path / "age"
        path.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n')
        path.chmod(0o755)

    class Fake:
        @property
        def args(self):
            return json.loads(log.read_text())

    fake = Fake()
    fake.path = path
    return fake


def recipients(tmp_path, body="age1quang\n"):
    r = tmp_path / "r.txt"
    r.write_text(body)
    return r


def test_seal_pack_streams_tar_through_age_one_image_at_a_time(fake_age, tmp_path):
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    big = os.urandom(5_000_000)
    held = []

    def fetch(name, dest):
        held.append(len(list(scratch.iterdir())))
        dest.write_bytes(big if name == "big.png" else b"s")

    out = tmp_path / "pack.tar.age"
    seal_pack(fake_age.path, recipients(tmp_path), out, small(tmp_path, "d"), ["big.png", "s.png"], fetch,
              small(tmp_path, "v.tar.gz"), {"k": 1}, scratch)
    assert fake_age.args[:2] == ["-R", str(tmp_path / "r.txt")]
    assert held == [0, 0] and list(scratch.iterdir()) == []
    assert not list(tmp_path.glob("*.tar"))
    with tarfile.open(out) as t:
        assert set(t.getnames()) == {"db.dump", "images/big.png", "images/s.png", "velero/v.tar.gz", "manifest.json"}
        assert t.extractfile("images/big.png").read() == big
        assert json.loads(t.extractfile("manifest.json").read()) == {"k": 1}


def test_seal_pack_raises_when_age_fails(fake_age, tmp_path):
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    with pytest.raises(subprocess.CalledProcessError):
        seal_pack(fake_age.path, recipients(tmp_path, "FAIL"), tmp_path / "o.age", small(tmp_path, "d"), [],
                  lambda n, d: None, small(tmp_path, "v.tar.gz"), {}, scratch)


def age_archive(binary: bytes) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as t:
        info = tarfile.TarInfo("age/age")
        info.size = len(binary)
        info.mode = 0o755
        t.addfile(info, io.BytesIO(binary))
    return buf.getvalue()


@pytest.fixture
def fake_release():
    archive = age_archive(b"\x7fELF fake age")
    return archive, (lambda url, timeout=None: FakeResponse(archive, 200))


def test_fetch_age_refuses_wrong_hash(tmp_path, fake_release):
    _, http = fake_release
    with pytest.raises(ValueError):
        fetch_age(tmp_path, sha256="00" * 32, http=http)


def test_fetch_age_unpacks_binary_when_hash_matches(tmp_path, fake_release):
    archive, http = fake_release
    path = fetch_age(tmp_path, sha256=hashlib.sha256(archive).hexdigest(), http=http)
    assert path.read_bytes() == b"\x7fELF fake age"



def test_run_takes_pack_time_before_listing_images_and_packs_only_newer(tmp_path, monkeypatch, fake_age):
    import scripts.vault.pack as pack
    (tmp_path / "db.dump").write_bytes(b"dump")
    stores = {
        "https://v/vault": [BlobInfo("srv/20261030T010000Z.tar.age", T0, 1)],
        "https://i/images": [BlobInfo("old.png", T0 - timedelta(hours=1), 1), BlobInfo("new.png", T0 + timedelta(hours=1), 1)],
    }
    events, uploads = [], []
    started = T0 + timedelta(hours=2, microseconds=5)

    def list_blobs(url, sas, prefix=""):
        events.append(f"list {url}")
        return stores[url]

    def clock():
        events.append("clock")
        return started

    def upload(url, sas, name, src):
        uploads.append((url, name, src.read_bytes()))
    monkeypatch.setattr(pack, "list_blobs", list_blobs)
    monkeypatch.setattr(pack, "download", lambda url, sas, name, dest: dest.write_bytes(name.encode()))
    monkeypatch.setattr(pack, "fetch_age", lambda dest, sha256: fake_age.path)
    monkeypatch.setattr(pack, "upload_new", upload)
    for k, v in {"SERVER_NAME": "srv", "POST_COUNT": "7", "CONTENT_DIGEST": "abc", "VELERO_BACKUP": "stop-1",
                 "IMAGE_CONTAINER_URL": "https://i/images", "IMAGE_SAS": "s", "VELERO_CONTAINER_URL": "https://b/velero",
                 "VELERO_SAS": "s", "VAULT_CONTAINER_URL": "https://v/vault", "VAULT_SAS": "s", "AGE_SHA256": "00",
                 "RECIPIENTS_FILE": str(recipients(tmp_path))}.items():
        monkeypatch.setenv(k, v)

    name = run(tmp_path, now=clock)
    assert events.index("clock") < events.index("list https://i/images")
    assert name == "srv/20261030T030000Z.tar.age"
    assert [(u, n) for u, n, _ in uploads] == [("https://v/vault", name)]
    sealed = tmp_path / "sealed.tar"
    sealed.write_bytes(uploads[0][2])
    with tarfile.open(sealed) as t:
        assert [m for m in t.getnames() if m.startswith("images/")] == ["images/new.png"]
        manifest = json.loads(t.extractfile("manifest.json").read())
    assert manifest["created_at"] == "2026-10-30T03:00:00Z" and manifest["images"] == ["new.png"]
    assert manifest["images_since"] == "2026-10-30T01:00:00Z" and manifest["post_count"] == 7
    assert manifest["velero_backup"] == "stop-1"
    assert sorted(x.name for x in tmp_path.iterdir()) == sorted(["age-args.json", "age.cmd" if os.name == "nt" else "age",
                                                                 "db.dump", "fake_age.py", "r.txt", "sealed.tar"])


def test_seal_pack_never_leaves_a_partial_pack_when_an_image_download_fails(fake_age, tmp_path):
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    out = tmp_path / "o.age"

    def fetch(name, dest):
        raise urllib.error.URLError("timed out")

    with pytest.raises(urllib.error.URLError):
        seal_pack(fake_age.path, recipients(tmp_path), out, small(tmp_path, "d"), ["a.png"], fetch,
                  small(tmp_path, "v.tar.gz"), {}, scratch)
    assert not out.exists()
