import hashlib
import json

import pytest

from scripts.dr.session_state import Session
from scripts.dr.verify_restore import ImageCheck, compare, check_images, fetch_posts, store_unchanged


def session(state="stopped", post_count=1000, digest="d1"):
    return Session(state=state, cluster="primary", server_name="primary-202610290522",
                   started_at="2026-10-29T05:22:23Z", stopped_at="2026-10-29T06:07:00Z" if state == "stopped" else None,
                   full_backup="20261029T060730" if state == "stopped" else None,
                   velero_backup="stop-202610290607" if state == "stopped" else None,
                   post_count=post_count, content_digest=digest)


def test_all_match_is_ok():
    r = compare(session(post_count=1000, digest="d1"), 1000, "d1", [ImageCheck("p1", "aa", "aa")])
    assert r.ok and r.missing_posts == 0


def test_missing_posts_counted():
    r = compare(session(post_count=1000, digest="d1"), 998, "d2", [])
    assert not r.ok and r.missing_posts == 2 and not r.digest_match


def test_more_posts_than_recorded_is_not_ok():
    r = compare(session(post_count=10, digest="d1"), 11, "d3", [])
    assert not r.ok and r.extra_posts == 1


def test_missing_image_is_bad():
    r = compare(session(post_count=1, digest="d1"), 1, "d1", [ImageCheck("p1", "aa", None)])
    assert not r.ok and r.bad_images == ["p1"]


def test_running_session_checks_images_only():
    r = compare(session(state="running", post_count=None, digest=None), 5, "dx", [ImageCheck("p1", "aa", "aa")])
    assert r.ok


def test_running_session_with_no_posts_is_not_ok():
    r = compare(session(state="running", post_count=None, digest=None), 0, "", [])
    assert not r.ok


class FakeApi:
    def __init__(self, posts, images, page=2):
        self.posts, self.images, self.page, self.urls = posts, images, page, []

    def __call__(self, url):
        self.urls.append(url)
        if url.endswith("/image"):
            body = self.images.get(url.split("/")[-2])
            if body is None:
                raise OSError("404")
            return body
        before = url.split("before=")[1] if "before=" in url else None
        start = 0 if before is None else [p["id"] for p in self.posts].index(before) + 1
        chunk = self.posts[start:start + self.page]
        more = start + self.page < len(self.posts)
        return json.dumps({"posts": chunk, "next": chunk[-1]["id"] if more else None}).encode()


def _post(i, body):
    return {"id": f"p{i}", "image_sha256": hashlib.sha256(body).hexdigest()}


def test_fetch_posts_follows_pages():
    api = FakeApi([_post(i, b"x") for i in range(5)], {})
    assert [p["id"] for p in fetch_posts("http://api", api)] == ["p0", "p1", "p2", "p3", "p4"]


def test_check_images_hashes_downloads_and_marks_missing():
    posts = [_post(1, b"one"), _post(2, b"two")]
    api = FakeApi(posts, {"p1": b"one"})
    checks = {c.post_id: c for c in check_images("http://api", posts, sample=10, get=api)}
    assert checks["p1"].actual_sha256 == checks["p1"].expected_sha256
    assert checks["p2"].actual_sha256 is None


def test_check_images_samples_at_most_n():
    posts = [_post(i, b"x") for i in range(20)]
    api = FakeApi(posts, {p["id"]: b"x" for p in posts})
    assert len(check_images("http://api", posts, sample=7, get=api)) == 7


@pytest.mark.parametrize("before,after,ok", [({"a", "b"}, {"a", "b"}, True), ({"a"}, {"a", "b"}, False)])
def test_store_must_not_gain_files(before, after, ok):
    assert store_unchanged(before, after) is ok
