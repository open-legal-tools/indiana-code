#!/usr/bin/env python3
"""Extract and ingest official Indiana appellate PDFs into the caselaw store.

Fills empty CourtListener clusters when the official case number matches a
docket. Unmatched decisions are stored as incourts-{id}. Does not replace
Harvard CAP bodies. Resume-safe text extract.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from indiana_law import store  # noqa: E402

COURT = {
    "Supreme Court": ("ind", "Indiana Supreme Court"),
    "Court of Appeals": ("indctapp", "Indiana Court of Appeals"),
    "Tax Court": ("indtc", "Indiana Tax Court"),
}


def norm_docket(value: str) -> str:
    s = re.sub(r"\s+", "", (value or "").upper().strip())
    parts = s.split("-")
    if parts:
        parts[-1] = parts[-1].lstrip("0") or "0"
    return "-".join(parts)


def parse_date(value: str) -> str:
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value.strip(), fmt).date().isoformat()
        except ValueError:
            continue
    return ""


def extract_one(pdf_path: str, dest: str) -> tuple[str, str]:
    if os.path.exists(dest) and os.path.getsize(dest) > 20:
        return dest, "skip"
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "out.txt")
        try:
            subprocess.run(["pdftotext", "-layout", pdf_path, out], check=True, capture_output=True)
            text = Path(out).read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            return dest, f"fail:{exc}"
    text = re.sub(r"\s+", " ", text).strip()
    Path(dest).write_text(text, encoding="utf-8")
    return dest, "ok" if text else "empty"


def extract_all(pdf_dir: str, text_dir: str, workers: int) -> tuple[int, int, int]:
    jobs = []
    for name in os.listdir(pdf_dir):
        if not name.lower().endswith(".pdf"):
            continue
        rid = name[:-4]
        jobs.append((os.path.join(pdf_dir, name), os.path.join(text_dir, f"{rid}.txt")))
    ok = skip = fail = 0
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futs = [pool.submit(extract_one, pdf, dest) for pdf, dest in jobs]
        for i, fut in enumerate(as_completed(futs), 1):
            _, status = fut.result()
            if status == "ok":
                ok += 1
            elif status == "skip":
                skip += 1
            else:
                fail += 1
            if i % 500 == 0 or status not in {"ok", "skip"}:
                print(f"extract {i}/{len(jobs)} {status} ok={ok} skip={skip} fail={fail}", flush=True)
    print(f"extract done ok={ok} skip={skip} fail={fail}", flush=True)
    return ok, skip, fail


def docket_to_clusters(clusters_path: str, dockets_path: str) -> dict[str, list[tuple[str, str]]]:
    dock_num = {}
    with open(dockets_path, encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            num = norm_docket(row.get("docket_number") or "")
            if num:
                dock_num[str(row["id"])] = num
    by_num: dict[str, list[tuple[str, str]]] = {}
    with open(clusters_path, encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            num = dock_num.get(str(row.get("docket_id") or ""))
            if not num:
                continue
            date = (row.get("date_filed") or "")[:10]
            by_num.setdefault(num, []).append((str(row["id"]), date))
    return by_num


def pick_cluster(candidates: list[tuple[str, str]], date: str) -> str | None:
    if not candidates:
        return None
    exact = [cid for cid, d in candidates if d == date]
    if exact:
        return exact[0]
    return candidates[0][0]


def ingest(db: str, jsonl: str, text_dir: str, clusters_path: str, dockets_path: str) -> None:
    by_num = docket_to_clusters(clusters_path, dockets_path)
    conn = store.connect(db)
    existing = {
        r[0]: (r[1], r[2] or "")
        for r in conn.execute("SELECT cluster_id, has_opinion_text, text_source FROM case_cluster")
    }
    updated = inserted = skipped = empty = 0
    with open(jsonl, encoding="utf-8") as fh:
        for i, line in enumerate(fh, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            rid = str(row["id"])
            text_path = os.path.join(text_dir, f"{rid}.txt")
            text = Path(text_path).read_text(encoding="utf-8") if os.path.exists(text_path) else ""
            if not text:
                empty += 1
                continue
            date = parse_date(row.get("date") or "")
            nums = [norm_docket(row.get("caseNumber") or "")]
            for c in row.get("courts") or []:
                nums.append(norm_docket(c.get("number") or ""))
            cid = None
            for num in nums:
                if num and num in by_num:
                    cid = pick_cluster(by_num[num], date)
                    if cid:
                        break
            court_id, court = COURT.get((row.get("courtName") or "").strip(), ("", row.get("courtName") or ""))
            status = "Unpublished" if row.get("isMemorandum") else "Published"
            name = re.sub(r"\s+", " ", (row.get("style") or "").replace("\n", " ")).strip()
            if cid and cid in existing:
                has_text, source = existing[cid]
                if has_text and source == "harvard_cap":
                    skipped += 1
                    continue
                conn.execute(
                    "UPDATE case_cluster SET opinion_text=?, text_source=?, has_opinion_text=1, "
                    "search_text=?, precedential_status=? WHERE cluster_id=?",
                    (text, "official_incourts", " ".join(x for x in (name, text) if x), status, cid),
                )
                existing[cid] = (1, "official_incourts")
                updated += 1
            else:
                new_id = f"incourts-{rid}"
                if new_id in existing and existing[new_id][0]:
                    skipped += 1
                    continue
                conn.execute(
                    "INSERT OR REPLACE INTO case_cluster VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        new_id, court_id, court, name, date, row.get("caseNumber") or "",
                        status, "", 0, (row.get("decision") or "").strip(), "", rid, text,
                        "official_incourts", 1,
                        " ".join(x for x in (name, row.get("decision") or "", text) if x),
                    ),
                )
                existing[new_id] = (1, "official_incourts")
                inserted += 1
            if i % 1000 == 0:
                conn.commit()
                print(f"ingest {i} updated={updated} inserted={inserted} skipped={skipped} empty={empty}", flush=True)
    conn.commit()
    store.finalize_cases(conn)
    with_text = conn.execute("SELECT count(*) FROM case_cluster WHERE has_opinion_text=1").fetchone()[0]
    total = conn.execute("SELECT count(*) FROM case_cluster").fetchone()[0]
    print(f"done updated={updated} inserted={inserted} skipped={skipped} empty={empty} clusters={total} with_text={with_text}", flush=True)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", default=os.path.join(ROOT, "data/store/indiana-code.db"))
    p.add_argument("--jsonl", default=os.path.join(ROOT, "data/official-decisions/search.jsonl"))
    p.add_argument("--pdf-dir", default=os.path.join(ROOT, "data/official-decisions/pdf"))
    p.add_argument("--text-dir", default=os.path.join(ROOT, "data/official-decisions/text"))
    p.add_argument("--clusters", default=os.path.join(ROOT, "data/courtlistener/2026-09-30/indiana/clusters.jsonl"))
    p.add_argument("--dockets", default=os.path.join(ROOT, "data/courtlistener/2026-09-30/indiana/dockets.jsonl"))
    p.add_argument("--workers", type=int, default=6)
    p.add_argument("--extract-only", action="store_true")
    p.add_argument("--ingest-only", action="store_true")
    args = p.parse_args(argv)
    if not args.ingest_only:
        extract_all(args.pdf_dir, args.text_dir, args.workers)
    if not args.extract_only:
        ingest(args.db, args.jsonl, args.text_dir, args.clusters, args.dockets)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
