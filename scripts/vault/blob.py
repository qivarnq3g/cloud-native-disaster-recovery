from __future__ import annotations

import shutil
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path

TIMEOUT_S = 120
API_VERSION = "2023-11-03"


class BlobExists(Exception):
    pass


@dataclass(frozen=True)
class BlobInfo:
    name: str
    last_modified: datetime
    size: int


def _url(container_url: str, sas: str, name: str = "", query: str = "") -> str:
    path = container_url.rstrip("/")
    if name:
        path += "/" + urllib.parse.quote(name)
    return f"{path}?{query + '&' if query else ''}{sas.lstrip('?')}"


def list_blobs(container_url: str, sas: str, prefix: str = "",
               http=urllib.request.urlopen) -> list[BlobInfo]:
    found: list[BlobInfo] = []
    marker = ""
    while True:
        query = "restype=container&comp=list"
        if prefix:
            query += "&prefix=" + urllib.parse.quote(prefix)
        if marker:
            query += "&marker=" + urllib.parse.quote(marker)
        request = urllib.request.Request(_url(container_url, sas, query=query),
                                         headers={"x-ms-version": API_VERSION})
        with http(request, timeout=TIMEOUT_S) as r:
            root = ET.fromstring(r.read())
        for blob in root.iter("Blob"):
            props = blob.find("Properties")
            found.append(BlobInfo(blob.findtext("Name"),
                                  parsedate_to_datetime(props.findtext("Last-Modified")),
                                  int(props.findtext("Content-Length"))))
        marker = root.findtext("NextMarker") or ""
        if not marker:
            return found


def download(container_url: str, sas: str, name: str, dest: Path,
             http=urllib.request.urlopen) -> None:
    request = urllib.request.Request(_url(container_url, sas, name), headers={"x-ms-version": API_VERSION})
    with http(request, timeout=TIMEOUT_S) as r, open(dest, "wb") as out:
        shutil.copyfileobj(r, out, 1 << 20)


def upload_new(container_url: str, sas: str, name: str, src: Path,
               http=urllib.request.urlopen) -> None:
    size = src.stat().st_size
    with open(src, "rb") as body:
        request = urllib.request.Request(
            _url(container_url, sas, name), data=body, method="PUT",
            headers={"x-ms-version": API_VERSION, "x-ms-blob-type": "BlockBlob",
                     "If-None-Match": "*", "Content-Length": str(size),
                     "Content-Type": "application/octet-stream"})
        try:
            with http(request, timeout=TIMEOUT_S):
                pass
        except urllib.error.HTTPError as e:
            if e.code in (409, 412) or (e.code == 403 and e.headers.get("x-ms-error-code") == "UnauthorizedBlobOverwrite"):
                raise BlobExists(name) from e
            raise
