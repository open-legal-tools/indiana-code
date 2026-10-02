#!/usr/bin/env python3
"""
Daily sync: pull new Indiana appellate opinions from CourtListener REST API v4.

Data source: CourtListener (courtlistener.com)
Coverage: Indiana Supreme Court (ind), Court of Appeals (indctapp), Tax Court (indtc)
License: Public domain opinions, no copyright restriction

Run once manually after bootstrap_opinions.py to catch up, then via daily cron.

Usage:
    python scripts/sync_opinions.py

Optional env vars:
    COURTLISTENER_API_KEY  — CourtListener API token (increases rate limit to 600/day at $10/mo)
                             Free tier (no key): 125 calls/day — sufficient for daily Indiana sync
"""

import json
import logging
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from db import db_path, get_meta, set_meta

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

CL_BASE     = "https://www.courtlistener.com/api/rest/v4"
COURTS      = ["ind", "indctapp", "indtc"]
USER_AGENT  = "indiana-law-mcp/1.0 (+https://indianacle.com; contact@indianacle.com)"
RATE_DELAY  = 1.2   # seconds between API calls (free tier: 5/min)

# SALI LMSS IRI base for opinion type
SALI_OPINION_IRI = "http://lmss.sali.org/R8B39DEC1C7714BF6898AC9EC53E8B8D3"


def _request(url: str, api_key: str | None) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    if api_key:
        req.add_header("Authorization", f"Token {api_key}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def _cl_type_to_sali(cl_type: str) -> tuple[str, str]:
    """Map CourtListener opinion type to SALI doc_type and IRI."""
    mapping = {
        "010combined":  ("opinion", SALI_OPINION_IRI),
        "020lead":      ("opinion", SALI_OPINION_IRI),
        "025concurrence": ("opinion", SALI_OPINION_IRI),
        "030dissent":   ("opinion", SALI_OPINION_IRI),
        "040remittitur": ("order",  ""),
        "050rehearing": ("order",   ""),
        "060on-motion-to-strike": ("motion", ""),
    }
    return mapping.get(cl_type, ("opinion", SALI_OPINION_IRI))


def fetch_since(last_date: str, token: str | None) -> list[dict]:
    """Fetch all Indiana opinions filed on or after last_date."""
    opinions = []

    for court in COURTS:
        params = {
            "court":          court,
            "date_filed__gte": last_date,
            "order_by":       "date_filed",
            "format":         "json",
            "page_size":      100,
        }
        url = f"{CL_BASE}/opinions/?{urllib.parse.urlencode(params)}"
        page = 1

        while url:
            time.sleep(RATE_DELAY)
            try:
                data = _request(url, token)
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    log.warning("Rate limited — sleeping 60s")
                    time.sleep(60)
                    data = _request(url, api_key)
                else:
                    log.error(f"HTTP {e.code} fetching {url}")
                    break
            except Exception as e:
                log.error(f"Error fetching {url}: {e}")
                break

            results = data.get("results", [])
            log.info(f"{court} page {page}: {len(results)} opinions")

            for item in results:
                doc_type, doc_type_iri = _cl_type_to_sali(item.get("type", ""))
                opinions.append({
                    "id":           item["id"],
                    "cluster_id":   item.get("cluster"),
                    "case_name":    item.get("case_name", ""),
                    "court_id":     court,
                    "date_filed":   item.get("date_filed"),
                    "author_str":   item.get("author_str", ""),
                    "per_curiam":   1 if item.get("per_curiam") else 0,
                    "doc_type":     doc_type,
                    "doc_type_iri": doc_type_iri,
                    "plain_text":   item.get("plain_text", ""),
                    "html_url":     (
                        f"https://www.courtlistener.com{item['absolute_url']}"
                        if item.get("absolute_url") else ""
                    ),
                    "download_url": item.get("download_url", ""),
                })

            url = data.get("next")
            page += 1

    return opinions


def upsert(opinions: list[dict]) -> tuple[int, int]:
    """Upsert into local SQLite. Returns (new, updated)."""
    if not opinions:
        return 0, 0

    db = db_path()
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    new_count = updated_count = 0

    for op in opinions:
        existing = conn.execute(
            "SELECT id FROM opinions WHERE id = ?", (op["id"],)
        ).fetchone()

        if existing:
            conn.execute("""
                UPDATE opinions SET
                    case_name=?, court_id=?, date_filed=?, author_str=?,
                    per_curiam=?, doc_type=?, doc_type_iri=?,
                    plain_text=?, html_url=?, download_url=?,
                    updated_at=datetime('now')
                WHERE id=?
            """, (
                op["case_name"], op["court_id"], op["date_filed"],
                op["author_str"], op["per_curiam"],
                op["doc_type"], op["doc_type_iri"],
                op["plain_text"], op["html_url"], op["download_url"],
                op["id"],
            ))
            updated_count += 1
        else:
            conn.execute("""
                INSERT INTO opinions(
                    id, cluster_id, case_name, court_id, date_filed,
                    author_str, per_curiam, doc_type, doc_type_iri,
                    plain_text, html_url, download_url
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                op["id"], op["cluster_id"], op["case_name"],
                op["court_id"], op["date_filed"], op["author_str"],
                op["per_curiam"], op["doc_type"], op["doc_type_iri"],
                op["plain_text"], op["html_url"], op["download_url"],
            ))
            new_count += 1

    conn.commit()
    conn.close()
    return new_count, updated_count


def main() -> None:
    token = os.environ.get("COURTLISTENER_API_KEY")

    last_sync = get_meta("opinions_last_sync")
    if not last_sync:
        last_sync = (date.today() - timedelta(days=30)).isoformat()
        log.info(f"First run — fetching opinions since {last_sync}")
    else:
        log.info(f"Last sync: {last_sync}")

    opinions = fetch_since(last_sync, token)
    log.info(f"Fetched {len(opinions)} opinions across {len(COURTS)} courts")

    new, updated = upsert(opinions)
    log.info(f"Sync complete — {new} new, {updated} updated")

    today = date.today().isoformat()
    set_meta("opinions_last_sync", today)
    set_meta("opinions_last_run", datetime.now().isoformat())
    log.info(f"Next run will fetch from {today}")


if __name__ == "__main__":
    main()
