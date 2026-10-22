#!/usr/bin/env python3
"""Resume-safe ingest of the 2005 IGA chapter PDFs. Unofficial; not legal advice."""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from indiana_law import companion, store  # noqa: E402

YEAR = 2005
KIND = companion.KIND_ARCHIVE


def main() -> int:
    db = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "data/store/indiana-code.db")
    src = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "data/iga-archives/2005")
    conn = store.connect(db)
    have = {r[0] for r in conn.execute("SELECT DISTINCT doc_id FROM companion_page")}
    pdfs = sorted(
        os.path.join(src, name) for name in os.listdir(src) if name.lower().endswith(".pdf")
    )
    added = skipped = 0
    for i, path in enumerate(pdfs, start=1):
        did = companion.doc_id(KIND, YEAR, os.path.basename(path))
        if did in have:
            skipped += 1
            continue
        pages = companion.pages_from_pdf(path, kind=KIND, year=YEAR)
        n = store.add_companion_pages(conn, pages)
        have.add(did)
        added += n
        if i % 50 == 0 or n:
            conn.commit()
            print(f"{i}/{len(pdfs)} {os.path.basename(path)} +{n} pages (added {added}, skipped {skipped})", flush=True)
    store.finalize_companion(conn)
    print(f"done 2005 chapters pages={added} skipped_docs={skipped} of {len(pdfs)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
