import hashlib
import io
import json
import os
import sys
import tarfile
from pathlib import Path

import pytest

from scripts.vault.restore_test import DecryptError, check, decrypt, plan_packs, read_pack


def test_packs_are_ordered_by_time_for_one_server():
    names = ["p/20261031T010000Z.tar.age", "q/20261030T010000Z.tar.age", "p/20261030T010000Z.tar.age"]
    assert plan_packs(names, "p") == ["p/20261030T010000Z.tar.age", "p/20261031T010000Z.tar.age"]


def fake_age(tmp_path: Path, body: str) -> Path:
    script = tmp_path / "fake_age.py"
    script.write_text(body)
    if os.name == "nt":
        path = tmp_path / "age.cmd"
        path.write_text(f'@"{sys.executable}" "{script}" %*\n')
    else:
        path = tmp_path / "age"
        path.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n')
        path.chmod(0o755)
    return path


@pytest.fixture
def fake_age_failing(tmp_path):
    class Fake:
        path = fake_age(tmp_path, "import sys\nsys.stderr.write('age: error: no identity matched any of the recipients\\n')\nsys.exit(1)\n")
    return Fake()


def test_wrong_key_raises_decrypt_error(fake_age_failing, tmp_path):
    with pytest.raises(DecryptError, match="no identity matched"):
        decrypt(fake_age_failing.path, tmp_path / "k", tmp_path / "x.age")


def test_decrypt_writes_plain_file_next_to_source(tmp_path):
    age = fake_age(tmp_path, "import sys\nargs = sys.argv[1:]\nopen(args[args.index('-o') + 1], 'wb').write(open(args[-1], 'rb').read()[::-1])\n")
    src = tmp_path / "x.tar.age"
    src.write_bytes(b"cba")
    out = decrypt(age, tmp_path / "k", src)
    assert out == tmp_path / "x.tar" and out.read_bytes() == b"abc"


def test_missing_image_is_named():
    r = check({"post_count": 2, "content_digest": "d", "images": ["a.png", "b.png"]}, 2, "d", {"a.png"})
    assert not r.ok and r.missing_images == ["b.png"]


def _uuid7_at(iso: str) -> str:
    from datetime import datetime

    ms = int(datetime.fromisoformat(iso).timestamp() * 1000)
    h = f"{ms:012x}" + "7000800000000000abcd"
    return f"original/{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def test_missing_image_within_image_rpo_before_incident_is_allowed():
    from datetime import datetime

    incident = datetime.fromisoformat("2026-11-07T13:43:34+00:00")
    recent = _uuid7_at("2026-11-07T13:42:04+00:00")
    old = _uuid7_at("2026-11-07T13:30:00+00:00")
    r = check({"post_count": 2, "content_digest": "d", "images": [recent, old]}, 2, "d", {old},
              incident_at=incident)
    assert r.ok and r.missing_images == [] and r.images_lost_within_rpo == [recent]
    r = check({"post_count": 2, "content_digest": "d", "images": [recent, old]}, 2, "d", {recent},
              incident_at=incident)
    assert not r.ok and r.missing_images == [old]


def test_without_incident_every_missing_image_fails():
    recent = _uuid7_at("2026-11-07T13:42:04+00:00")
    r = check({"post_count": 1, "content_digest": "d", "images": [recent]}, 1, "d", set())
    assert not r.ok and r.missing_images == [recent] and r.images_lost_within_rpo == []


def test_non_uuid_names_are_never_excused():
    from datetime import datetime

    r = check({"post_count": 1, "content_digest": "d", "images": ["original/x"]}, 1, "d", set(),
              incident_at=datetime.fromisoformat("2026-11-07T13:43:34+00:00"))
    assert not r.ok and r.missing_images == ["original/x"]


def test_all_match_is_ok():
    assert check({"post_count": 1, "content_digest": "d", "images": ["a.png"]}, 1, "d", {"a.png"}).ok


def test_digest_mismatch_fails():
    r = check({"post_count": 1, "content_digest": "d", "images": []}, 1, "e", set())
    assert not r.ok and r.count_match and not r.digest_match


def make_pack(path: Path, images: dict[str, bytes], manifest: dict, dump: bytes = b"dump") -> Path:
    with tarfile.open(path, "w") as t:
        for name, body in [("db.dump", dump), *[(f"images/{k}", v) for k, v in images.items()],
                           ("manifest.json", json.dumps(manifest).encode())]:
            info = tarfile.TarInfo(name)
            info.size = len(body)
            t.addfile(info, io.BytesIO(body))
    return path


def test_read_pack_hashes_images_and_keeps_dump(tmp_path):
    tar = make_pack(tmp_path / "p.tar", {"original/1": b"one"}, {"post_count": 1})
    pack = read_pack(tar, tmp_path / "out.dump")
    assert pack.manifest == {"post_count": 1}
    assert pack.image_hashes == {"original/1": hashlib.sha256(b"one").hexdigest()}
    assert (tmp_path / "out.dump").read_bytes() == b"dump"


def test_read_pack_refuses_paths_outside_images(tmp_path):
    tar = make_pack(tmp_path / "p.tar", {"../evil": b"x"}, {})
    pack = read_pack(tar, None)
    assert pack.image_hashes == {}
