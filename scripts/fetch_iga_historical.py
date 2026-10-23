#!/usr/bin/env python3
"""Download official IGA historical statutes as far back as they publish them.

Sources (no contact, browser-shaped UA):
- Sanity catalog on iga.in.gov: yearly Acts 2000–2026, non-code 1807–2026,
  archive constitutions, derivation/disposition tables.
- Acts of Indiana scanned archive 1852–2000 at /publications/act/archive/.

Compiled Indiana Code title zips remain 2005 and 2009–2016; 2006–2008 are
still missing at the official zip path.
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
SANITY = (
    "https://75zw3lpd.apicdn.sanity.io/v1/data/query/production?query="
    + urllib.parse.quote(
        '*[_type in ["act", "historical_table", "indiana_constitution", "noncode_statute"]]'
        ' {"file": manuscript.asset->{fileURL}, _type, year, table_name, title_num, title, current}'
    )
)
ARCHIVE_BASE = "https://iga.in.gov/publications/act/archive/"


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://iga.in.gov/laws/ic/downloads"})
    with urllib.request.urlopen(req, timeout=180) as resp:
        return resp.read()


def download(url: str, dest: str) -> str:
    if os.path.exists(dest) and os.path.getsize(dest) > 1000:
        return "skip"
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = dest + ".part"
    # encode path spaces without breaking already-encoded URLs
    parsed = urllib.parse.urlsplit(url)
    safe = urllib.parse.urlunsplit((
        parsed.scheme, parsed.netloc,
        urllib.parse.quote(urllib.parse.unquote(parsed.path), safe="/"),
        parsed.query, parsed.fragment,
    ))
    req = urllib.request.Request(safe, headers={"User-Agent": UA, "Referer": "https://iga.in.gov/laws/acts/archive"})
    try:
        with urllib.request.urlopen(req, timeout=300) as resp, open(tmp, "wb") as fh:
            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                fh.write(chunk)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    if os.path.getsize(tmp) < 1000:
        os.remove(tmp)
        return "tiny"
    os.replace(tmp, dest)
    return "ok"


def sanity_jobs(dest: str) -> list[tuple[str, str]]:
    rows = json.loads(get(SANITY))["result"]
    jobs = []
    for row in rows:
        url = ((row.get("file") or {}).get("fileURL") or "").strip()
        if not url:
            continue
        kind = row.get("_type") or "unknown"
        name = os.path.basename(urllib.parse.unquote(urllib.parse.urlsplit(url).path))
        jobs.append((url, os.path.join(dest, kind, name)))
    return jobs


def archive_jobs(list_path: str, dest: str) -> list[tuple[str, str]]:
    jobs = []
    with open(list_path, encoding="utf-8") as fh:
        for line in fh:
            name = line.strip()
            if not name:
                continue
            jobs.append((ARCHIVE_BASE + name, os.path.join(dest, "acts_archive", name)))
    return jobs


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dest", default="data/iga-historical")
    p.add_argument("--archive-list", default="data/iga-historical/acts-archive-files.txt")
    p.add_argument("--sleep", type=float, default=0.15)
    p.add_argument("--skip-archive", action="store_true")
    args = p.parse_args(argv)
    jobs = sanity_jobs(args.dest)
    if not args.skip_archive and os.path.exists(args.archive_list):
        jobs.extend(archive_jobs(args.archive_list, args.dest))
    print(f"planned {len(jobs)} files", flush=True)
    ok = skip = fail = 0
    for i, (url, dest) in enumerate(jobs, 1):
        try:
            status = download(url, dest)
        except urllib.error.HTTPError as exc:
            status = f"http-{exc.code}"
        except Exception as exc:
            status = type(exc).__name__
        if status == "ok":
            ok += 1
        elif status == "skip":
            skip += 1
        else:
            fail += 1
        if i % 10 == 0 or status not in {"ok", "skip"}:
            size = os.path.getsize(dest) if os.path.exists(dest) else 0
            print(f"{i}/{len(jobs)} {status} {size} {os.path.basename(dest)} ok={ok} skip={skip} fail={fail}", flush=True)
        if status == "ok":
            time.sleep(args.sleep)
    print(f"done ok={ok} skip={skip} fail={fail}", flush=True)
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
