"""Command line: parse a snapshot directory, parse an Acts text file, build the SQLite store."""
from __future__ import annotations

import argparse
import json
import os
import sys

from . import PARSER_VERSION, acts, companion, parse_code, store


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="indiana-law")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("parse-snapshot", help="HTML directory -> JSONL")
    a.add_argument("src_dir"); a.add_argument("out_jsonl"); a.add_argument("--snapshot-id", required=True); a.add_argument("--zip-sha256", default="")
    b = sub.add_parser("parse-acts", help="Acts text -> JSONL of clauses")
    b.add_argument("acts_txt"); b.add_argument("out_jsonl"); b.add_argument("--year", type=int, required=True)
    c = sub.add_parser("build-store", help="JSONL files -> SQLite store")
    c.add_argument("db"); c.add_argument("--snapshot", action="append", default=[], metavar="ID:YEAR:COMPILE_DATE:CERTAIN:JSONL")
    c.add_argument("--acts", action="append", default=[], metavar="JSONL")
    d = sub.add_parser("ingest-companion", help="Extract and index Constitution / Non-code / Acts PDFs from official HTML zips")
    d.add_argument("db")
    d.add_argument("--zip", action="append", default=[], dest="zips", help="Official HTML zip containing Additional_Documents_PDF")
    d.add_argument("--pdf", action="append", default=[], dest="pdfs", help="A single companion or archive-title PDF")
    d.add_argument("--year", type=int, default=None)
    d.add_argument("--kind", default=None, help="constitution, noncode, acts, or archive_title")
    d.add_argument("--extract-dir", default="data/companion")
    args = p.parse_args(argv)
    if args.cmd == "parse-snapshot":
        n = parse_code.write_jsonl(parse_code.parse_snapshot_dir(args.src_dir, args.snapshot_id, args.zip_sha256), args.out_jsonl)
        print(f"{n} section records -> {args.out_jsonl}")
    elif args.cmd == "parse-acts":
        with open(args.acts_txt, encoding="utf-8", errors="replace") as fh:
            recs = acts.parse_acts_text(fh.read(), args.year)
        with open(args.out_jsonl, "w", encoding="utf-8") as fo:
            for r in recs:
                fo.write(json.dumps(r) + "\n")
        print(f"{len(recs)} clause records -> {args.out_jsonl}")
    elif args.cmd == "ingest-companion":
        conn = store.connect(args.db)
        n = 0
        for zp in args.zips:
            year = companion.year_from_path(zp, args.year)
            dest = os.path.join(args.extract_dir, str(year or "unknown"))
            for pdf in companion.extract_additional_from_zip(zp, dest):
                pages = companion.pages_from_pdf(pdf, year=year)
                added = store.add_companion_pages(conn, pages)
                print(pdf, added)
                n += added
        for pdf in args.pdfs:
            pages = companion.pages_from_pdf(pdf, kind=args.kind, year=args.year)
            added = store.add_companion_pages(conn, pages)
            print(pdf, added)
            n += added
        store.finalize_companion(conn)
        print("companion pages:", n)
    else:
        conn = store.connect(args.db)
        for spec in args.snapshot:
            sid, year, cdate, certain, path = spec.split(":", 4)
            store.add_snapshot(conn, sid, int(year), cdate or None, certain == "1", "", PARSER_VERSION)
            print(sid, store.add_records(conn, store.read_jsonl(path)))
        for path in args.acts:
            print(path, store.add_clauses(conn, store.read_jsonl(path)))
        store.finalize(conn)
        print("distinct section versions:", conn.execute("SELECT count(*) FROM section_version").fetchone()[0])
    return 0


if __name__ == "__main__":
    sys.exit(main())
