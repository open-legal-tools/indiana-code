#!/usr/bin/env python3
"""
One-time bootstrap: load Indiana appellate opinions from CourtListener's
free bulk data (S3 CSV files). Downloads quarterly snapshots covering
Indiana Supreme Court and Court of Appeals from 1885 to present.

Source: Free Law Project bulk data
S3 bucket: s3://com-courtlistener-storage/bulk-data/
License: Public domain

Usage:
    python scripts/bootstrap_opinions.py

No credentials required. Downloads ~500MB of compressed data.
Expect 20–40 minutes for download + import.

After this completes, use sync_opinions.py for daily updates.
"""

import csv
import gzip
import io
import logging
import sqlite3
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from db import db_path, set_meta

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# CourtListener S3 bulk data — no auth required
S3_BASE     = "https://com-courtlistener-storage.s3.amazonaws.com/bulk-data"
USER_AGENT  = "indiana-law-mcp/1.0 (+https://indianacle.com)"

# Indiana court IDs in CourtListener
INDIANA_COURTS = {"ind", "indctapp", "indtc"}

# SALI IRI for opinions
SALI_OPINION_IRI = "http://lmss.sali.org/R8B39DEC1C7714BF6898AC9EC53E8B8D3"


def init_db() -> sqlite3.Connection:
    db = db_path()
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    schema = (Path(__file__).parent.parent / "schema.sql").read_text()
    conn.executescript(schema)
    return conn


def _download_stream(url: str):
    """Stream a URL, decompressing gzip on the fly."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    resp = urllib.request.urlopen(req, timeout=120)
    if url.endswith(".gz"):
        return gzip.open(resp, "rt", encoding="utf-8", errors="replace")
    return io.TextIOWrapper(resp, encoding="utf-8", errors="replace")


def _cl_type_to_sali(cl_type: str) -> tuple[str, str]:
    if cl_type in ("010combined", "020lead", "025concurrence", "030dissent"):
        return "opinion", SALI_OPINION_IRI
    if cl_type in ("040remittitur", "050rehearing"):
        return "order", ""
    return "opinion", SALI_OPINION_IRI


def import_opinions_csv(conn: sqlite3.Connection, stream) -> int:
    """Parse CourtListener opinions CSV and insert Indiana rows."""
    reader = csv.DictReader(stream)
    inserted = 0
    skipped  = 0

    for row in reader:
        # Filter to Indiana courts only
        court_id = row.get("court_id", "")
        if court_id not in INDIANA_COURTS:
            skipped += 1
            continue

        try:
            opinion_id = int(row["id"])
        except (KeyError, ValueError):
            continue

        doc_type, doc_type_iri = _cl_type_to_sali(row.get("type", ""))

        # CourtListener CSV field names may vary by snapshot version
        plain_text = (
            row.get("plain_text") or row.get("text") or ""
        )
        html_url = row.get("absolute_url", "")
        if html_url and not html_url.startswith("http"):
            html_url = f"https://www.courtlistener.com{html_url}"

        conn.execute("""
            INSERT OR IGNORE INTO opinions(
                id, cluster_id, case_name, court_id, date_filed,
                author_str, per_curiam, doc_type, doc_type_iri,
                plain_text, html_url, download_url
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            opinion_id,
            row.get("cluster_id") or None,
            row.get("case_name", ""),
            court_id,
            row.get("date_filed") or None,
            row.get("author_str", ""),
            1 if row.get("per_curiam", "").lower() in ("t", "true", "1") else 0,
            doc_type,
            doc_type_iri,
            plain_text,
            html_url,
            row.get("download_url", ""),
        ))
        inserted += 1

        if inserted % 5000 == 0:
            conn.commit()
            log.info(f"  {inserted:,} opinions inserted…")

    conn.commit()
    log.info(f"Import done: {inserted:,} inserted, {skipped:,} non-Indiana rows skipped")
    return inserted


def main() -> None:
    conn = init_db()

    existing = conn.execute("SELECT COUNT(*) FROM opinions").fetchone()[0]
    if existing > 0:
        log.info(f"Database already has {existing:,} opinions. Use sync_opinions.py for updates.")
        conn.close()
        return

    # The CourtListener bulk data listing changes with each quarterly release.
    # Check the current file at: https://www.courtlistener.com/help/api/bulk-data/
    # The opinions table is typically at:
    #   s3://com-courtlistener-storage/bulk-data/opinions-{date}.csv.gz
    #
    # For now, fetch the manifest to find the current opinions file.
    log.info("Fetching CourtListener bulk data manifest…")
    manifest_url = f"{S3_BASE}/"

    try:
        manifest = urllib.request.urlopen(
            urllib.request.Request(manifest_url, headers={"User-Agent": USER_AGENT}),
            timeout=30,
        ).read().decode()
    except Exception as e:
        log.error(f"Could not fetch manifest: {e}")
        log.info(
            "Manually specify the URL. Go to https://www.courtlistener.com/help/api/bulk-data/ "
            "and find the current opinions CSV URL, then run:\n"
            "  OPINIONS_URL=<url> python scripts/bootstrap_opinions.py"
        )
        sys.exit(1)

    import os
    opinions_url = os.environ.get("OPINIONS_URL")
    if not opinions_url:
        # Try to extract from S3 XML manifest
        import re
        # Find the most recent opinions file
        matches = re.findall(r"<Key>(bulk-data/opinions[^<]*\.gz)</Key>", manifest)
        if not matches:
            log.error(
                "Could not find opinions file in S3 manifest.\n"
                "Set OPINIONS_URL env var to the direct S3 URL of the opinions CSV."
            )
            sys.exit(1)
        opinions_url = f"https://com-courtlistener-storage.s3.amazonaws.com/{sorted(matches)[-1]}"

    log.info(f"Downloading: {opinions_url}")
    log.info("This will take 20–40 minutes on a typical connection.")

    try:
        stream = _download_stream(opinions_url)
        total = import_opinions_csv(conn, stream)
    except Exception as e:
        log.error(f"Download/import failed: {e}")
        conn.close()
        sys.exit(1)

    from datetime import date
    set_meta("opinions_last_sync", date.today().isoformat())
    log.info(f"Bootstrap complete. {total:,} Indiana opinions loaded.")
    conn.close()


if __name__ == "__main__":
    main()
