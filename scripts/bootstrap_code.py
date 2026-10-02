#!/usr/bin/env python3
"""
Bootstrap Indiana Code from the official IGA MyIGA API v2.0.

Requires a free API token from: apitoken.request@iga.in.gov
Set it in your environment: export IGA_API_TOKEN=<your_token>

Usage:
    python scripts/bootstrap_code.py [--year 2026]

The script walks the full IC hierarchy:
  /titles → /titles/{t}/articles → /titles/{t}/articles/{a}/chapters → chapter text

Rate limit: 1 request per 5 seconds (robots.txt hint). The script
respects this automatically. A full bootstrap takes roughly 3-4 hours
at this rate. Run it once and let it finish; it is resumable.
"""

import argparse
import json
import logging
import sqlite3
import sys
import time
import urllib.request
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from db import db_path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

IGA_BASE    = "https://api.iga.in.gov"
RATE_LIMIT  = 5.1   # seconds between requests
USER_AGENT  = "indiana-law-mcp/1.0 (https://github.com/danielle-teagarden/indiana-law)"


def init_db(year: int) -> sqlite3.Connection:
    db = db_path()
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    schema = (Path(__file__).parent.parent / "schema.sql").read_text()
    conn.executescript(schema)
    conn.execute(
        "INSERT OR REPLACE INTO sync_meta(key, value) VALUES ('ic_year', ?)",
        (str(year),)
    )
    conn.commit()
    return conn


def _get(path: str, token: str) -> dict:
    url = f"{IGA_BASE}{path}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Token {token}",
        "Accept":        "application/json",
        "User-Agent":    USER_AGENT,
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def _official_url(year: int, title: int, article: int, chapter: int) -> str:
    return (
        f"https://iga.in.gov/laws/ic/{year}/title{title}"
        f"/article{article}/chapter{chapter}"
    )


def section_exists(conn: sqlite3.Connection, citation: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM ic_sections WHERE citation = ?", (citation,)
    ).fetchone() is not None


def ingest_chapter(
    conn: sqlite3.Connection,
    data: dict,
    title_num: int,
    title_name: str,
    article_num: int,
    article_name: str,
    chapter_num: int,
    chapter_name: str,
    year: int,
) -> int:
    """Parse a chapter response and insert sections. Returns count inserted."""
    inserted = 0
    sections = data.get("sections") or data.get("data", {}).get("sections", [])

    for s in sections:
        # The IGA API returns section numbers as strings like "3" or "3.5"
        raw_sec = s.get("sectionNumber") or s.get("section_number", "")
        try:
            section_num = int(float(raw_sec))
        except (ValueError, TypeError):
            section_num = 0

        citation = f"IC {title_num}-{article_num}-{chapter_num}-{raw_sec}".upper()

        if section_exists(conn, citation):
            continue

        text = (
            s.get("content")
            or s.get("text")
            or s.get("sectionText")
            or ""
        ).strip()

        section_name = (
            s.get("sectionName")
            or s.get("name")
            or ""
        )

        official_url = _official_url(year, title_num, article_num, chapter_num)

        conn.execute("""
            INSERT OR IGNORE INTO ic_sections(
                citation, title_num, article_num, chapter_num, section_num,
                title_name, article_name, chapter_name, section_name,
                text, official_url, year
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            citation, title_num, article_num, chapter_num, section_num,
            title_name, article_name, chapter_name, section_name,
            text, official_url, year,
        ))
        inserted += 1

    conn.commit()
    return inserted


def bootstrap(token: str, year: int) -> None:
    conn = init_db(year)
    total = 0

    log.info(f"Fetching IC titles for year {year}…")
    titles_data = _get(f"/{year}/ic/titles", token)
    titles = titles_data.get("items") or titles_data.get("titles", [])
    log.info(f"Found {len(titles)} titles")

    for t in titles:
        title_num  = int(t.get("titleNumber") or t.get("number", 0))
        title_name = t.get("title") or t.get("name", f"Title {title_num}")

        time.sleep(RATE_LIMIT)
        try:
            articles_data = _get(f"/{year}/ic/titles/{title_num}/articles", token)
        except Exception as e:
            log.warning(f"Title {title_num}: failed to fetch articles — {e}")
            continue

        articles = articles_data.get("items") or articles_data.get("articles", [])

        for a in articles:
            article_num  = int(a.get("articleNumber") or a.get("number", 0))
            article_name = a.get("article") or a.get("name", f"Article {article_num}")

            time.sleep(RATE_LIMIT)
            try:
                chapters_data = _get(
                    f"/{year}/ic/titles/{title_num}/articles/{article_num}/chapters",
                    token,
                )
            except Exception as e:
                log.warning(f"IC {title_num}-{article_num}: failed to fetch chapters — {e}")
                continue

            chapters = chapters_data.get("items") or chapters_data.get("chapters", [])

            for ch in chapters:
                chapter_num  = int(ch.get("chapterNumber") or ch.get("number", 0))
                chapter_name = ch.get("chapter") or ch.get("name", f"Chapter {chapter_num}")

                time.sleep(RATE_LIMIT)
                try:
                    chapter_data = _get(
                        f"/{year}/ic/titles/{title_num}/articles/{article_num}/chapters/{chapter_num}",
                        token,
                    )
                except Exception as e:
                    log.warning(f"IC {title_num}-{article_num}-{chapter_num}: failed — {e}")
                    continue

                n = ingest_chapter(
                    conn, chapter_data,
                    title_num, title_name,
                    article_num, article_name,
                    chapter_num, chapter_name,
                    year,
                )
                total += n
                if n:
                    log.info(f"IC {title_num}-{article_num}-{chapter_num}: {n} sections  (total: {total})")

    count = conn.execute("SELECT COUNT(*) FROM ic_sections").fetchone()[0]
    log.info(f"Bootstrap complete. {count:,} sections in database.")
    conn.close()


def main() -> None:
    import os
    parser = argparse.ArgumentParser(description="Bootstrap Indiana Code from IGA API")
    parser.add_argument("--year", type=int, default=2026, help="IC year (default: 2026)")
    args = parser.parse_args()

    token = os.environ.get("IGA_API_TOKEN")
    if not token:
        print(
            "Error: IGA_API_TOKEN not set.\n"
            "Request a free token at: apitoken.request@iga.in.gov\n"
            "Then: export IGA_API_TOKEN=<your_token>",
            file=sys.stderr,
        )
        sys.exit(1)

    bootstrap(token, args.year)


if __name__ == "__main__":
    main()
