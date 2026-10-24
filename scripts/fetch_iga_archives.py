#!/usr/bin/env python3
"""Download IGA archive title-PDF zips (pre-2017) with a browser-shaped UA.

Official page: https://iga.in.gov/laws/ic/downloads
URL form (from the site JS): https://iga.in.gov/ic/{year}/{year}-Indiana-Code.zip

Does not contact anyone. Skip years whose HEAD is not application/zip.
"""
from __future__ import annotations

import argparse
import os
import sys
import urllib.request

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
REFERER = "https://iga.in.gov/laws/ic/downloads"
DEFAULT_YEARS = list(range(2005, 2017))


def zip_url(year: int) -> str:
    return f"https://iga.in.gov/ic/{year}/{year}-Indiana-Code.zip"


def head_zip(year: int) -> tuple[bool, int, str]:
    req = urllib.request.Request(zip_url(year), method="HEAD", headers={"User-Agent": UA, "Referer": REFERER})
    with urllib.request.urlopen(req, timeout=30) as resp:
        ctype = resp.headers.get("Content-Type", "")
        clen = int(resp.headers.get("Content-Length") or 0)
        return ctype.startswith("application/zip") and clen > 1000, clen, ctype


def download(year: int, dest: str) -> str:
    path = os.path.join(dest, f"{year}-Indiana-Code.zip")
    if os.path.exists(path) and os.path.getsize(path) > 1000:
        print(f"skip existing {path} ({os.path.getsize(path)} bytes)", flush=True)
        return path
    os.makedirs(dest, exist_ok=True)
    tmp = path + ".part"
    req = urllib.request.Request(zip_url(year), headers={"User-Agent": UA, "Referer": REFERER})
    print(f"GET {zip_url(year)} -> {path}", flush=True)
    with urllib.request.urlopen(req, timeout=120) as resp, open(tmp, "wb") as fh:
        while True:
            chunk = resp.read(1024 * 1024)
            if not chunk:
                break
            fh.write(chunk)
    os.replace(tmp, path)
    print(f"wrote {path} ({os.path.getsize(path)} bytes)", flush=True)
    return path


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dest", default="data/iga-archives")
    p.add_argument("--year", type=int, action="append", dest="years")
    p.add_argument("--probe-only", action="store_true")
    p.add_argument("--extract", action="store_true")
    args = p.parse_args(argv)
    years = args.years or DEFAULT_YEARS
    available: list[int] = []
    for year in years:
        try:
            ok, clen, ctype = head_zip(year)
        except Exception as exc:
            print(f"{year} HEAD error: {exc}", flush=True)
            continue
        print(f"{year} {'zip' if ok else 'skip'} {clen} {ctype}", flush=True)
        if ok:
            available.append(year)
    if args.probe_only:
        print("available:", ",".join(str(y) for y in available))
        return 0
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
    from indiana_law.companion import extract_archive_titles_from_zip

    for year in available:
        path = download(year, args.dest)
        if args.extract:
            dest = os.path.join(args.dest, str(year))
            written = extract_archive_titles_from_zip(path, dest)
            print(f"{year} extracted {len(written)} pdfs -> {dest}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
