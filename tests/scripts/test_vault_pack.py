import hashlib
import io
import json
import os
import sys
import tarfile
import urllib.error
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from scripts.vault.blob import BlobExists, BlobInfo, download, list_blobs, upload_new
from scripts.vault.pack import build_tar, encrypt, fetch_age, newest_pack_time, select_images

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


def test_upload_new_reraises_other_errors(tmp_path):
    with pytest.raises(urllib.error.HTTPError):
        upload_new("https://x/vault", "sig", "n", tmp_file(tmp_path), http=status(403))


def test_build_tar_streams_to_disk(tmp_path):
    big = tmp_path / "big.png"
    big.write_bytes(os.urandom(5_000_000))
    out = build_tar(tmp_path, dump=small(tmp_path, "d"), images={"big.png": big},
                    velero=small(tmp_path, "v.tar.gz"), manifest={"k": 1})
    assert out.is_file() and out.stat().st_size > 5_000_000
    with tarfile.open(out) as t:
        assert {"db.dump", "images/big.png", "manifest.json", "velero/v.tar.gz"} <= set(t.getnames())
        assert json.loads(t.extractfile("manifest.json").read()) == {"k": 1}


@pytest.fixture
def fake_age(tmp_path):
    log = tmp_path / "age-args.json"
    script = tmp_path / "fake_age.py"
    script.write_text(
        "import json, sys\n"
        f"json.dump(sys.argv[1:], open({str(log)!r}, 'w'))\n"
        "out = sys.argv[sys.argv.index('-o') + 1]\n"
        "open(out, 'wb').write(b'age')\n")
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


def test_encrypt_uses_recipients_file(fake_age, tmp_path):
    src = small(tmp_path, "x.tar")
    out = encrypt(fake_age.path, tmp_path / "r.txt", src)
    assert fake_age.args[:2] == ["-R", str(tmp_path / "r.txt")]
    assert out == src.with_name("x.tar.age") and out.read_bytes() == b"age"


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


def test_run_packs_new_images_and_uploads_under_server_folder(tmp_path, monkeypatch, fake_age):
    import scripts.vault.pack as pack
    (tmp_path / "db.dump").write_bytes(b"dump")
    stores = {
        "https://v/vault": [BlobInfo("srv/20261030T010000Z.tar.age", T0, 1)],
        "https://i/images": [BlobInfo("old.png", T0 - timedelta(hours=1), 1), BlobInfo("new.png", T0 + timedelta(hours=1), 1)],
    }
    uploads = []
    monkeypatch.setattr(pack, "list_blobs", lambda url, sas, prefix="": stores[url])
    monkeypatch.setattr(pack, "download", lambda url, sas, name, dest: dest.write_bytes(name.encode()))
    monkeypatch.setattr(pack, "fetch_age", lambda dest, sha256: fake_age.path)

    def upload(url, sas, name, src):
        uploads.append((url, name, src.read_bytes()))
    monkeypatch.setattr(pack, "upload_new", upload)
    for k, v in {"SERVER_NAME": "srv", "POST_COUNT": "7", "CONTENT_DIGEST": "abc", "VELERO_BACKUP": "stop-1",
                 "IMAGE_CONTAINER_URL": "https://i/images", "IMAGE_SAS": "s", "VELERO_CONTAINER_URL": "https://b/velero",
                 "VELERO_SAS": "s", "VAULT_CONTAINER_URL": "https://v/vault", "VAULT_SAS": "s", "AGE_SHA256": "00",
                 "RECIPIENTS_FILE": str(tmp_path / "r.txt")}.items():
        monkeypatch.setenv(k, v)
    real_build = pack.build_tar
    seen = {}

    def build(work, dump, images, velero, manifest):
        seen.update(manifest=manifest, images=sorted(images), velero=velero.name)
        return real_build(work, dump, images, velero, manifest)
    monkeypatch.setattr(pack, "build_tar", build)

    name = pack.run(tmp_path)
    assert name.startswith("srv/") and name.endswith(".tar.age")
    assert uploads == [("https://v/vault", name, b"age")]
    assert seen["images"] == ["new.png"] and seen["velero"] == "stop-1.tar.gz"
    assert seen["manifest"]["images_since"] == "2026-10-30T01:00:00Z" and seen["manifest"]["post_count"] == 7
    assert not (tmp_path / "pack.tar").exists() and not (tmp_path / "images").exists()
