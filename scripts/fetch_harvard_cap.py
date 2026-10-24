#!/usr/bin/env python3
"""Download Harvard Caselaw Access Project JSON volume zips for Indiana.

Official bulk: https://static.case.law/  (browser-shaped UA required).
Indiana-only reporters are fetched in full. Regional N.E.2d / N.E.3d volumes
are fetched when the CourtListener cluster slice points at them.

Does not scrape CourtListener. Unpublished / NFP memorandum decisions are
almost never in CAP; those need the official Indiana courts archive.
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
import zipfile

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
BASE = "https://static.case.law"
IN_ONLY = ("blackf", "ind", "ind-app", "ind-l-rep", "wilson")
REGIONAL = ("ne2d", "ne3d")


def get(url: str, dest: str | None = None) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://static.case.law/"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        if dest is None:
            return resp.read()
        tmp = dest + ".part"
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(tmp, "wb") as fh:
            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                fh.write(chunk)
        os.replace(tmp, dest)
        return b""


def volumes_for_reporter(slug: str) -> list[str]:
    raw = get(f"{BASE}/{slug}/VolumesMetadata.json")
    meta = json.loads(raw)
    vols = []
    for row in meta:
        vol = str(row.get("volume_number") or "").strip()
        if vol.isdigit():
            vols.append(vol)
    return sorted(vols, key=lambda x: int(x))


def cluster_regional_volumes(clusters_path: str) -> dict[str, set[str]]:
    wanted = {slug: set() for slug in REGIONAL}
    with open(clusters_path, encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            path = (row.get("filepath_json_harvard") or "").strip()
            if not path.startswith("law.free.cap."):
                continue
            prefix = path.split("/", 1)[0][len("law.free.cap."):]
            if "." not in prefix:
                continue
            reporter, vol = prefix.rsplit(".", 1)
            if reporter in wanted and vol.isdigit():
                wanted[reporter].add(vol)
    return wanted


def valid_zip(path: str) -> bool:
    if not os.path.exists(path) or os.path.getsize(path) < 100:
        return False
    try:
        with zipfile.ZipFile(path) as zf:
            return zf.testzip() is None
    except zipfile.BadZipFile:
        return False


def download_volume(slug: str, vol: str, dest_dir: str) -> tuple[str, str]:
    dest = os.path.join(dest_dir, slug, f"{vol}.zip")
    if valid_zip(dest):
        return dest, "skip"
    url = f"{BASE}/{slug}/{vol}.zip"
    last = "error"
    for attempt in range(3):
        try:
            get(url, dest)
            if valid_zip(dest):
                return dest, "ok"
            last = "bad-zip"
        except urllib.error.HTTPError as exc:
            last = f"http-{exc.code}"
            if exc.code in {404, 403}:
                break
        except Exception as exc:
            last = type(exc).__name__
        if os.path.exists(dest + ".part"):
            os.remove(dest + ".part")
        if os.path.exists(dest) and not valid_zip(dest):
            os.remove(dest)
        time.sleep(1.5 * (attempt + 1))
    return dest, last


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dest", default="data/harvard-cap/inbox")
    p.add_argument("--clusters", default="data/courtlistener/2026-09-30/indiana/clusters.jsonl")
    p.add_argument("--sleep", type=float, default=0.15)
    p.add_argument("--probe-only", action="store_true")
    args = p.parse_args(argv)

    plan: list[tuple[str, str]] = []
    for slug in IN_ONLY:
        try:
            vols = volumes_for_reporter(slug)
        except Exception as exc:
            print(f"{slug} metadata error: {exc}", flush=True)
            continue
        print(f"{slug} all {len(vols)} volumes", flush=True)
        plan.extend((slug, vol) for vol in vols)

    wanted = cluster_regional_volumes(args.clusters)
    for slug in REGIONAL:
        vols = sorted(wanted[slug], key=int)
        print(f"{slug} cluster-pointed {len(vols)} volumes", flush=True)
        plan.extend((slug, vol) for vol in vols)

    print(f"planned {len(plan)} volume zips", flush=True)
    if args.probe_only:
        return 0

    ok = skip = fail = 0
    for i, (slug, vol) in enumerate(plan, 1):
        path, status = download_volume(slug, vol, args.dest)
        if status == "ok":
            ok += 1
        elif status == "skip":
            skip += 1
        else:
            fail += 1
        if i % 25 == 0 or status not in {"ok", "skip"}:
            size = os.path.getsize(path) if os.path.exists(path) else 0
            print(f"{i}/{len(plan)} {slug}/{vol}.zip {status} {size} ok={ok} skip={skip} fail={fail}", flush=True)
        if status == "ok":
            time.sleep(args.sleep)
    print(f"done planned={len(plan)} ok={ok} skip={skip} fail={fail}", flush=True)
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
