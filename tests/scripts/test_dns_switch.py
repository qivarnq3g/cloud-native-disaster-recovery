import json

import pytest

from scripts.dr.dns_switch import CloudflareDns, HealthCheckFailed, switch

NAME = "api.dr.qivarn.id.vn"
TOKEN = "cf-token-must-never-leak"


def ok(name, ip):
    return True


class FakeCloudflare:

    def __init__(self, records):
        self.records = records
        self.patches = []

    def __call__(self, req):
        assert req.get_header("Authorization") == f"Bearer {TOKEN}"
        if req.get_method() == "GET":
            return 200, {"success": True, "result": self.records}
        if req.get_method() == "PATCH":
            body = json.loads(req.data)
            self.patches.append(body)
            record_id = req.full_url.rsplit("/", 1)[1]
            for r in self.records:
                if r["id"] == record_id:
                    r.update(body)
            return 200, {"success": True, "result": {}}
        raise AssertionError(req.get_method())


def record(record_id, ip):
    return {"id": record_id, "type": "A", "name": NAME, "content": ip, "ttl": 60, "proxied": False}


@pytest.fixture
def fake_dns():
    api = FakeCloudflare([record("r1", "20.0.0.1")])
    dns = CloudflareDns(TOKEN, "zone1", http=api)
    dns.patches = api.patches
    return dns


@pytest.fixture
def fake_dns_two_records():
    return CloudflareDns(TOKEN, "zone1", http=FakeCloudflare([record("r1", "20.0.0.1"), record("r2", "20.0.0.2")]))


def test_refuses_when_target_not_healthy(fake_dns):
    with pytest.raises(HealthCheckFailed):
        switch(fake_dns, NAME, "20.0.0.2", health=lambda n, ip: False, resolve=lambda n: set())
    assert fake_dns.patches == []


def test_noop_when_record_already_points_to_ip(fake_dns):
    r = switch(fake_dns, NAME, "20.0.0.1", health=ok, resolve=lambda n: {"20.0.0.1"})
    assert r.changed is False and fake_dns.patches == []


def test_patches_content_ttl_and_proxy_off(fake_dns):
    switch(fake_dns, NAME, "20.0.0.2", health=ok, resolve=lambda n: {"20.0.0.2"})
    assert fake_dns.patches == [{"content": "20.0.0.2", "ttl": 60, "proxied": False}]


def test_times_out_if_resolvers_never_agree(fake_dns):
    r = switch(fake_dns, NAME, "20.0.0.2", health=ok, resolve=lambda n: {"20.0.0.1"}, timeout_s=0)
    assert r.changed is True and r.resolved_at is None


def test_rejects_non_ipv4(fake_dns):
    with pytest.raises(ValueError):
        switch(fake_dns, NAME, "dr-primary.koreacentral.cloudapp.azure.com", health=ok, resolve=lambda n: set())


def test_two_a_records_is_an_error(fake_dns_two_records):
    with pytest.raises(LookupError):
        fake_dns_two_records.get_a_record(NAME)


def test_token_never_printed(capsys, fake_dns):
    switch(fake_dns, NAME, "20.0.0.2", health=ok, resolve=lambda n: {"20.0.0.2"})
    out = capsys.readouterr()
    assert TOKEN not in out.out and TOKEN not in out.err


def test_waits_until_resolvers_agree(fake_dns):
    answers = iter([{"20.0.0.1"}, {"20.0.0.1", "20.0.0.2"}, {"20.0.0.2"}])
    r = switch(fake_dns, NAME, "20.0.0.2", health=ok, resolve=lambda n: next(answers),
               timeout_s=60, sleep=lambda s: None)
    assert r.resolved_at is not None and r.record_updated_at <= r.resolved_at
