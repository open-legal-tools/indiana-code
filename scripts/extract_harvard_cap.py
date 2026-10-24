#!/usr/bin/env python3
"""Extract Indiana opinion text from downloaded Harvard CAP volume zips.

Keeps only cases whose jurisdiction is Indiana. Writes JSONL keyed so the
CourtListener cluster filepath_json_harvard (reporter / first_page) can join.
"""
from __future__ import annotations

import argparse
import json
import os
import zipfile


def opinion_text(case: dict) -> str:
    body = case.get("casebody") or {}
    parts = []
    head = (body.get("head_matter") or "").strip()
    if head:
        parts.append(head)
    for op in body.get("opinions") or []:
        text = (op.get("text") or "").strip()
        if text:
            author = (op.get("author") or "").strip()
            kind = (op.get("type") or "").strip()
            prefix = " ".join(x for x in (kind, author) if x)
            parts.append(f"{prefix}\n{text}" if prefix else text)
    return "\n\n".join(parts).strip()


def is_indiana(case: dict) -> bool:
    jur = case.get("jurisdiction") or {}
    name = (jur.get("name_long") or jur.get("name") or "").lower()
    if "indiana" in name or name == "ind.":
        return True
    court = (case.get("court") or {}).get("name") or ""
    return "indiana" in court.lower()


def cites(case: dict) -> list[str]:
    out = []
    for row in case.get("citations") or []:
        cite = (row.get("cite") or "").strip()
        if cite:
            out.append(cite)
    return out


def extract_zip(path: str, reporter: str, volume: str):
    with zipfile.ZipFile(path) as zf:
        for name in zf.namelist():
            if not name.startswith("json/") or not name.endswith(".json"):
                continue
            raw = zf.read(name)
            if not raw.strip():
                continue
            case = json.loads(raw)
            if not isinstance(case, dict) or not is_indiana(case):
                continue
            text = opinion_text(case)
            if not text:
                continue
            yield {
                "cap_id": case.get("id"),
                "reporter": reporter,
                "volume": str(volume),
                "first_page": str(case.get("first_page") or ""),
                "file_name": case.get("file_name") or "",
                "name": case.get("name") or "",
                "name_abbreviation": case.get("name_abbreviation") or "",
                "decision_date": (case.get("decision_date") or "")[:10],
                "docket_number": case.get("docket_number") or "",
                "citations": cites(case),
                "court": (case.get("court") or {}).get("name") or "",
                "text": text,
                "source_zip": path,
            }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--inbox", default="data/harvard-cap/inbox")
    p.add_argument("--out", default="data/harvard-cap/indiana.jsonl")
    args = p.parse_args(argv)
    n = 0
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fo:
        for slug in sorted(os.listdir(args.inbox)):
            d = os.path.join(args.inbox, slug)
            if not os.path.isdir(d):
                continue
            for name in sorted(os.listdir(d), key=lambda x: (len(x), x)):
                if not name.endswith(".zip"):
                    continue
                vol = name[:-4]
                path = os.path.join(d, name)
                kept = 0
                try:
                    for rec in extract_zip(path, slug, vol):
                        fo.write(json.dumps(rec, ensure_ascii=False) + "\n")
                        n += 1
                        kept += 1
                except Exception as exc:
                    print(f"FAIL {slug}/{name}: {exc}", flush=True)
                    continue
                print(f"{slug}/{name} indiana={kept}", flush=True)
    print(f"wrote {n} indiana harvard cases -> {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
