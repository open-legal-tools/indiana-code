#!/usr/bin/env python3
"""Download official Indiana appellate decisions from public.courts.in.gov.

Uses the published Search and Document APIs (same files the courts website
serves). Walks date windows so the 251-result cap does not hide cases.
Includes memorandum / NFP when showMemorandum=true.

The digital archive begins around 2005 for published opinions and 2006 for
NFP memos (the year the Supreme Court allowed posting). Earlier memorandum
decisions were not posted.
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
SEARCH = "https://public.courts.in.gov/Decisions/api/Search"
DOC = "https://public.courts.in.gov/Decisions/"
CAP = 251


def get_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def search(from_date: date, to_date: date) -> list[dict]:
    params = {
        "fromDate": from_date.strftime("%m/%d/%Y"),
        "toDate": to_date.strftime("%m/%d/%Y"),
        "showMemorandum": "true",
    }
    return get_json(SEARCH + "?" + urllib.parse.urlencode(params))


def daterange_windows(start: date, end: date, days: int):
    cur = start
    while cur <= end:
        nxt = min(cur + timedelta(days=days - 1), end)
        yield cur, nxt
        cur = nxt + timedelta(days=1)


def harvest(start: date, end: date, out_jsonl: str, sleep: float) -> int:
    seen: set[int] = set()
    if os.path.exists(out_jsonl):
        with open(out_jsonl, encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    seen.add(json.loads(line)["id"])
    os.makedirs(os.path.dirname(out_jsonl) or ".", exist_ok=True)
    added = 0
    windows = list(daterange_windows(start, end, 7))
    i = 0
    while i < len(windows):
        a, b = windows[i]
        try:
            rows = search(a, b)
        except Exception as exc:
            print(f"search fail {a}..{b}: {exc}", flush=True)
            time.sleep(2)
            i += 1
            continue
        if len(rows) >= CAP and a < b:
            mid = a + (b - a) / 2
            windows[i:i + 1] = [(a, mid), (mid + timedelta(days=1), b)]
            print(f"split {a}..{b} cap={len(rows)}", flush=True)
            continue
        new = 0
        with open(out_jsonl, "a", encoding="utf-8") as fo:
            for row in rows:
                rid = row.get("id")
                if rid in seen:
                    continue
                seen.add(rid)
                fo.write(json.dumps(row, ensure_ascii=False) + "\n")
                added += 1
                new += 1
        memo = sum(1 for r in rows if r.get("isMemorandum"))
        print(f"{a}..{b} got={len(rows)} new={new} memo={memo} total={len(seen)}", flush=True)
        i += 1
        time.sleep(sleep)
    return added


def download_pdfs(jsonl: str, dest: str, sleep: float) -> tuple[int, int]:
    os.makedirs(dest, exist_ok=True)
    ok = skip = fail = 0
    with open(jsonl, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            row = json.loads(line)
            rid = str(row.get("id"))
            url = row.get("opinionUrl") or ""
            if not url:
                fail += 1
                continue
            path = os.path.join(dest, f"{rid}.pdf")
            if os.path.exists(path) and os.path.getsize(path) > 1000:
                skip += 1
                continue
            full = url if url.startswith("http") else DOC + url
            tmp = path + ".part"
            try:
                req = urllib.request.Request(full, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=90) as resp, open(tmp, "wb") as out:
                    while True:
                        chunk = resp.read(1024 * 1024)
                        if not chunk:
                            break
                        out.write(chunk)
                if os.path.getsize(tmp) < 100:
                    os.remove(tmp)
                    fail += 1
                    continue
                os.replace(tmp, path)
                ok += 1
            except Exception as exc:
                if os.path.exists(tmp):
                    os.remove(tmp)
                fail += 1
                print(f"pdf fail {rid}: {exc}", flush=True)
            if (ok + skip + fail) % 50 == 0:
                print(f"pdfs ok={ok} skip={skip} fail={fail}", flush=True)
            time.sleep(sleep)
    print(f"pdfs done ok={ok} skip={skip} fail={fail}", flush=True)
    return ok, fail


def parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dest", default="data/official-decisions")
    p.add_argument("--start", default="2005-01-01")
    p.add_argument("--end", default=date.today().isoformat())
    p.add_argument("--sleep", type=float, default=0.2)
    p.add_argument("--pdf-sleep", type=float, default=0.15)
    p.add_argument("--metadata-only", action="store_true")
    args = p.parse_args(argv)
    jsonl = os.path.join(args.dest, "search.jsonl")
    added = harvest(parse_date(args.start), parse_date(args.end), jsonl, args.sleep)
    print(f"harvest added {added} -> {jsonl}", flush=True)
    if args.metadata_only:
        return 0
    download_pdfs(jsonl, os.path.join(args.dest, "pdf"), args.pdf_sleep)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
