"""Extract Indiana opinions from CourtListener bulk files, in resumable stages. Streams .bz2 files; nothing is unpacked in full.

usage: python scripts/extract_indiana_opinions.py <bulk_dir> <out_dir> [stage ...]   (stages: dockets clusters opinions; default all)
Indiana court ids: ind, indctapp, indtc. Outputs (JSON Lines): dockets.jsonl, clusters.jsonl, opinions.jsonl.gz.
"""
import bz2
import csv
import gzip
import json
import os
import sys
import time

csv.field_size_limit(10**9)
COURTS = {"ind", "indctapp", "indtc"}
OP_KEEP = ("id", "cluster_id", "type", "author_str", "per_curiam", "joined_by_str", "sha1", "page_count", "download_url",
           "plain_text", "html_with_citations", "xml_harvard", "html", "html_lawbox", "html_columbia", "date_modified")


def rows(path):
    with bz2.open(path, "rt", encoding="utf-8", newline="") as fh:
        yield from csv.DictReader(fh)


def stage_dockets(bulk, out):
    n = 0
    with open(os.path.join(out, "dockets.jsonl"), "w", encoding="utf-8") as fo:
        for r in rows(os.path.join(bulk, "dockets-2026-09-30.csv.bz2")):
            n += 1
            if r["court_id"] in COURTS:
                fo.write(json.dumps({k: r[k] for k in ("id", "court_id", "case_name", "case_name_full", "docket_number", "date_filed", "date_argued", "date_terminated", "source", "appeal_from_str", "cause", "nature_of_suit", "jurisdiction_type", "slug") if k in r}) + "\n")
            if n % 5_000_000 == 0:
                print(f"dockets {n:,} {time.strftime('%H:%M:%S')}", flush=True)
    print("dockets done", n, flush=True)


def stage_clusters(bulk, out):
    dock = {}
    with open(os.path.join(out, "dockets.jsonl"), encoding="utf-8") as fh:
        for line in fh:
            d = json.loads(line)
            dock[d["id"]] = d["court_id"]
    n = kept = 0
    with open(os.path.join(out, "clusters.jsonl"), "w", encoding="utf-8") as fo:
        for r in rows(os.path.join(bulk, "opinion-clusters-2026-09-30.csv.bz2")):
            n += 1
            c = dock.get(r["docket_id"])
            if c:
                r["court_id"] = c
                fo.write(json.dumps(r) + "\n")
                kept += 1
            if n % 10_000_000 == 0:
                print(f"clusters {n:,} kept {kept:,} {time.strftime('%H:%M:%S')}", flush=True)
    print("clusters done", n, "kept", kept, flush=True)


def stage_opinions(bulk, out):
    ids = set()
    with open(os.path.join(out, "clusters.jsonl"), encoding="utf-8") as fh:
        for line in fh:
            ids.add(json.loads(line)["id"])
    print("indiana clusters", len(ids), flush=True)
    n = kept = 0
    with gzip.open(os.path.join(out, "opinions.jsonl.gz"), "wt", encoding="utf-8") as fo:
        for r in rows(os.path.join(bulk, "opinions-2026-09-30.csv.bz2")):
            n += 1
            if r["cluster_id"] in ids:
                fo.write(json.dumps({k: r.get(k, "") for k in OP_KEEP}) + "\n")
                kept += 1
            if n % 1_000_000 == 0:
                print(f"opinions {n:,} kept {kept:,} {time.strftime('%H:%M:%S')}", flush=True)
    print("opinions done", n, "kept", kept, flush=True)


if __name__ == "__main__":
    bulk, out = sys.argv[1:3]
    os.makedirs(out, exist_ok=True)
    stages = sys.argv[3:] or ["dockets", "clusters", "opinions"]
    for s in stages:
        {"dockets": stage_dockets, "clusters": stage_clusters, "opinions": stage_opinions}[s](bulk, out)
