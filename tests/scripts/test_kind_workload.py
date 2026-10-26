import email.parser
import struct
import zlib

from scripts.kind.workload import Ledger, LedgerEntry, make_png, multipart, read_ledger


def test_png_is_valid_and_about_200_kb():
    png = make_png(7)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    width, height = struct.unpack(">II", png[16:24])
    assert (width, height) == (256, 256)
    assert 190_000 < len(png) < 1_048_576
    pos = 8
    while pos < len(png):
        (length,) = struct.unpack(">I", png[pos:pos + 4])
        kind_data = png[pos + 4:pos + 8 + length]
        assert struct.unpack(">I", png[pos + 8 + length:pos + 12 + length])[0] == zlib.crc32(kind_data)
        pos += 12 + length


def test_png_differs_by_seed_and_is_deterministic():
    assert make_png(1) == make_png(1)
    assert make_png(1) != make_png(2)


def test_multipart_round_trips():
    body, ctype = multipart({"title": "Ảnh 1", "idempotency_key": "k"}, "image", "a.png", b"\x00\x01", "image/png")
    msg = email.parser.BytesParser().parsebytes(f"Content-Type: {ctype}\r\n\r\n".encode() + body)
    parts = {p.get_param("name", header="content-disposition"): p for p in msg.get_payload()}
    assert parts["title"].get_payload(decode=True).decode() == "Ảnh 1"
    assert parts["image"].get_payload(decode=True) == b"\x00\x01"
    assert parts["image"].get_content_type() == "image/png"


def test_ledger_appends_and_numbers(tmp_path):
    path = tmp_path / "ledger.csv"
    ledger = Ledger(path)
    assert ledger.next_seq() == 1
    ledger.append(LedgerEntry(1, "id-1", "2026-10-26T12:00:00.000000Z", "aa", "seed"))
    ledger.append(LedgerEntry(2, "id-2", "2026-10-26T12:00:01.000000Z", "bb", "writer"))
    assert Ledger(path).next_seq() == 3
    assert [e.post_id for e in read_ledger(path)] == ["id-1", "id-2"]
