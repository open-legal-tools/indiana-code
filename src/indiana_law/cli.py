"""Command line: parse a snapshot directory, parse an Acts text file, build the SQLite store."""
from __future__ import annotations

import argparse
import json
import os
import sys

from . import PARSER_VERSION, acts, caselaw, companion, parse_code, store


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
    d.add_argument("--pdf-dir", action="append", default=[], dest="pdf_dirs", help="Directory of companion or archive-title PDFs")
    d.add_argument("--year", type=int, default=None)
    d.add_argument("--kind", default=None, help="constitution, noncode, acts, archive_title, court_rules, or historical_table")
    d.add_argument("--extract-dir", default="data/companion")
    e = sub.add_parser("ingest-caselaw", help="Index the local CourtListener Indiana extract")
    e.add_argument("db")
    e.add_argument("--clusters", required=True)
    e.add_argument("--opinions", required=True)
    e.add_argument("--harvard", default="", help="Extracted Indiana Harvard CAP JSONL")
    f = sub.add_parser(
        "ingest-statute-mentions",
        help="Index IC / Ind. Code mentions in opinion text (not a citator)",
    )
    f.add_argument("db")
    g = sub.add_parser(
        "ingest-decision-forms",
        help="Classify memorandum vs opinion from opinion text (not official status)",
    )
    g.add_argument("db")
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
        pdfs = list(args.pdfs)
        for d in args.pdf_dirs:
            pdfs.extend(sorted(
                os.path.join(d, name) for name in os.listdir(d)
                if name.lower().endswith(".pdf")
            ))
        for pdf in pdfs:
            pages = companion.pages_from_pdf(pdf, kind=args.kind, year=args.year)
            added = store.add_companion_pages(conn, pages)
            print(pdf, added)
            n += added
        store.finalize_companion(conn)
        print("companion pages:", n)
    elif args.cmd == "ingest-caselaw":
        conn = store.connect(args.db)
        opinions = caselaw.load_opinions(args.opinions)
        harvard = caselaw.load_harvard(args.harvard) if args.harvard else {}
        n = store.add_case_clusters(conn, caselaw.cluster_records(args.clusters, opinions, harvard))
        store.finalize_cases(conn)
        with_text = conn.execute("SELECT count(*) FROM case_cluster WHERE has_opinion_text=1").fetchone()[0]
        print(f"case clusters: {n}; with opinion text: {with_text}")
    elif args.cmd == "ingest-statute-mentions":
        conn = store.connect(args.db)
        stats = caselaw.ingest_statute_mentions(conn)
        print(
            f"statute mentions: scanned {stats['opinions_scanned']} opinions; "
            f"{stats['opinions_with_mentions']} with IC cites; "
            f"{stats['mention_pairs']} section/opinion pairs"
        )
    elif args.cmd == "ingest-decision-forms":
        conn = store.connect(args.db)
        stats = caselaw.ingest_decision_forms(conn)
        print(
            f"decision forms: {stats['clusters']} clusters; "
            f"{stats['counts']}; disagrees_with_source={stats['disagrees_with_source']}"
        )
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
