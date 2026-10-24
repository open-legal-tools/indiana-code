#!/usr/bin/env python3
"""Ingest downloaded official IGA historical statute PDFs. Resume-safe."""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from indiana_law import companion, store  # noqa: E402

KIND_BY_DIR = {
    "act": companion.KIND_ACTS,
    "acts_archive": companion.KIND_ACTS,
    "noncode_statute": companion.KIND_NONCODE,
    "indiana_constitution": companion.KIND_CONSTITUTION,
    "historical_table": companion.KIND_HISTORICAL_TABLE,
}

# Already ingested from the 2023–2026 HTML zips under the older doc_id scheme.
SKIP_DOC_PREFIXES = (
    "acts-2023",
    "acts-2024",
    "acts-2025",
    "acts-2026",
    "noncode-2023",
    "noncode-2024",
    "noncode-2025",
    "noncode-2026",
    "constitution-2023",
    "constitution-2024",
    "constitution-2025",
    "constitution-2026",
)


def main() -> int:
    db = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "data/store/indiana-code.db")
    src = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "data/iga-historical")
    conn = store.connect(db)
    have = {r[0] for r in conn.execute("SELECT DISTINCT doc_id FROM companion_page")}
    pdfs = []
    for dirpath, _, names in os.walk(src):
        folder = os.path.basename(dirpath)
        kind = KIND_BY_DIR.get(folder)
        if not kind:
            continue
        for name in names:
            if name.lower().endswith(".pdf"):
                pdfs.append((os.path.join(dirpath, name), kind))
    pdfs.sort()
    added = skipped = 0
    for i, (path, kind) in enumerate(pdfs, start=1):
        year = companion.year_from_path(path)
        did = companion.doc_id(kind, year, os.path.basename(path))
        folder = os.path.basename(os.path.dirname(path))
        already = did in have or any(did == p or did.startswith(p + "-") for p in SKIP_DOC_PREFIXES)
        current_year_dup = (
            folder != "acts_archive"
            and kind in {companion.KIND_ACTS, companion.KIND_NONCODE, companion.KIND_CONSTITUTION}
            and year in {2023, 2024, 2025, 2026}
        )
        if already or current_year_dup:
            skipped += 1
            continue
        pages = companion.pages_from_pdf(path, kind=kind, year=year)
        n = store.add_companion_pages(conn, pages)
        have.add(did)
        added += n
        if i % 10 == 0 or n:
            conn.commit()
            print(f"{i}/{len(pdfs)} {os.path.basename(path)} +{n} (pages {added}, skipped {skipped})", flush=True)
    store.finalize_companion(conn)
    print(f"done pages={added} skipped_docs={skipped} of {len(pdfs)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
