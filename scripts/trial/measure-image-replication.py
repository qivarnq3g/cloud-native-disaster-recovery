import csv
import os
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from azure.core.exceptions import ResourceNotFoundError
from azure.storage.blob import BlobServiceClient

PRIVATE_DIR = Path.home() / ".dr-trial"
SOURCE = os.environ["IMAGE_ACCOUNT_PRIMARY"]
DEST = os.environ["IMAGE_ACCOUNT_JAPAN"]
COUNT = int(sys.argv[1]) if len(sys.argv) > 1 else 200
SIZE = 200 * 1024
TIMEOUT = 1800
OUT = Path(os.environ["DATA_DIR"]) / "image-replication.csv"


def client(account):
    key = (PRIVATE_DIR / f"key-{account}").read_text().strip()
    return BlobServiceClient(f"https://{account}.blob.core.windows.net", credential=key).get_container_client("images")


def utc(t):
    return datetime.fromtimestamp(t, timezone.utc).isoformat()


def watch(dest, name, sent_at, results, lock):
    while time.time() - sent_at < TIMEOUT:
        try:
            dest.get_blob_client(name).get_blob_properties()
            with lock:
                results.append((name, utc(sent_at), utc(time.time()), round(time.time() - sent_at, 1)))
            return
        except ResourceNotFoundError:
            time.sleep(2)
    with lock:
        results.append((name, utc(sent_at), "", ""))


def main():
    source, dest = client(SOURCE), client(DEST)
    results, lock, threads = [], threading.Lock(), []
    for i in range(COUNT):
        name = f"trial/{int(time.time())}-{i:04d}.bin"
        sent_at = time.time()
        source.upload_blob(name, os.urandom(SIZE))
        t = threading.Thread(target=watch, args=(dest, name, sent_at, results, lock))
        t.start()
        threads.append(t)
        time.sleep(max(0.0, 1.0 - (time.time() - sent_at)))
    for t in threads:
        t.join()
    with OUT.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["blob", "sent_utc", "in_japan_utc", "lag_s"])
        w.writerows(sorted(results))
    lags = sorted(r[3] for r in results if r[3] != "")
    missing = sum(1 for r in results if r[3] == "")
    if lags:
        print(f"n={len(lags)} missing={missing} median={lags[len(lags)//2]} p95={lags[int(len(lags)*0.95)-1]} max={lags[-1]}")
    else:
        print(f"no image reached Japan within {TIMEOUT} seconds")


if __name__ == "__main__":
    main()
