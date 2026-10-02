"""
Database access layer for the Indiana Law MCP server.

All queries run against local SQLite. The MCP server never touches the
internet at query time — that's the sync scripts' job.
"""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

_DEFAULT_DB = Path(__file__).parent.parent / "data" / "indiana_law.db"


def db_path() -> Path:
    p = os.environ.get("INDIANA_LAW_DB")
    return Path(p) if p else _DEFAULT_DB


@contextmanager
def conn() -> Iterator[sqlite3.Connection]:
    c = sqlite3.connect(db_path())
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA query_only=ON")   # read-only at query time
    try:
        yield c
    finally:
        c.close()


@contextmanager
def writable_conn() -> Iterator[sqlite3.Connection]:
    c = sqlite3.connect(db_path())
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=ON")
    try:
        yield c
    finally:
        c.close()


# ─────────────────────────────────────────────
# INDIANA CODE
# ─────────────────────────────────────────────

def search_code(query: str, title_num: int | None = None, limit: int = 10) -> list[dict]:
    """FTS5 search over the Indiana Code. Returns sections ranked by BM25."""
    limit = min(limit, 50)
    with conn() as c:
        if title_num is not None:
            rows = c.execute("""
                SELECT s.citation, s.title_num, s.title_name,
                       s.chapter_name, s.section_name,
                       s.text, s.official_url,
                       bm25(ic_fts) AS score
                FROM ic_fts
                JOIN ic_sections s ON s.id = ic_fts.rowid
                WHERE ic_fts MATCH ? AND s.title_num = ?
                ORDER BY score
                LIMIT ?
            """, (query, title_num, limit)).fetchall()
        else:
            rows = c.execute("""
                SELECT s.citation, s.title_num, s.title_name,
                       s.chapter_name, s.section_name,
                       s.text, s.official_url,
                       bm25(ic_fts) AS score
                FROM ic_fts
                JOIN ic_sections s ON s.id = ic_fts.rowid
                WHERE ic_fts MATCH ?
                ORDER BY score
                LIMIT ?
            """, (query, limit)).fetchall()
        return [dict(r) for r in rows]


def get_section(citation: str) -> dict | None:
    """Exact lookup by IC citation string, e.g. 'IC 31-14-5-3'."""
    normalized = citation.upper().strip()
    # Accept "IC 31-14-5-3" or "31-14-5-3"
    if not normalized.startswith("IC "):
        normalized = "IC " + normalized
    with conn() as c:
        row = c.execute(
            "SELECT * FROM ic_sections WHERE citation = ?", (normalized,)
        ).fetchone()
        return dict(row) if row else None


def list_titles() -> list[dict]:
    """Return all IC titles with names and section counts."""
    with conn() as c:
        rows = c.execute("""
            SELECT title_num, title_name, COUNT(*) AS section_count
            FROM ic_sections
            GROUP BY title_num
            ORDER BY title_num
        """).fetchall()
        return [dict(r) for r in rows]


def browse_chapter(title_num: int, article_num: int, chapter_num: int) -> list[dict]:
    """Return all sections in a chapter in order."""
    with conn() as c:
        rows = c.execute("""
            SELECT citation, section_num, section_name, text, official_url
            FROM ic_sections
            WHERE title_num = ? AND article_num = ? AND chapter_num = ?
            ORDER BY section_num
        """, (title_num, article_num, chapter_num)).fetchall()
        return [dict(r) for r in rows]


# ─────────────────────────────────────────────
# OPINIONS
# ─────────────────────────────────────────────

COURT_NAMES = {
    "ind":     "Indiana Supreme Court",
    "indctapp": "Indiana Court of Appeals",
    "indtc":   "Indiana Tax Court",
}


def search_opinions(
    query: str,
    court: str | None = None,
    date_after: str | None = None,
    date_before: str | None = None,
    limit: int = 10,
) -> list[dict]:
    """FTS5 search over Indiana appellate opinions."""
    limit = min(limit, 50)
    with conn() as c:
        params: list = [query]
        filters = ""
        if court:
            filters += " AND o.court_id = ?"
            params.append(court)
        if date_after:
            filters += " AND o.date_filed >= ?"
            params.append(date_after)
        if date_before:
            filters += " AND o.date_filed <= ?"
            params.append(date_before)
        params.append(limit)

        rows = c.execute(f"""
            SELECT o.id, o.case_name, o.court_id, o.date_filed,
                   o.author_str, o.per_curiam, o.doc_type,
                   substr(o.plain_text, 1, 600) AS excerpt,
                   o.html_url,
                   bm25(opinions_fts) AS score
            FROM opinions_fts
            JOIN opinions o ON o.id = opinions_fts.rowid
            WHERE opinions_fts MATCH ?{filters}
            ORDER BY score
            LIMIT ?
        """, params).fetchall()
        return [dict(r) for r in rows]


def get_opinion(opinion_id: int) -> dict | None:
    """Full opinion by CourtListener ID."""
    with conn() as c:
        row = c.execute(
            "SELECT * FROM opinions WHERE id = ?", (opinion_id,)
        ).fetchone()
        return dict(row) if row else None


def recent_opinions(court: str | None = None, days: int = 30) -> list[dict]:
    """Opinions filed in the last N days, newest first."""
    with conn() as c:
        if court:
            rows = c.execute("""
                SELECT id, case_name, court_id, date_filed, author_str,
                       per_curiam, doc_type, html_url
                FROM opinions
                WHERE court_id = ?
                  AND date_filed >= date('now', '-' || ? || ' days')
                ORDER BY date_filed DESC
                LIMIT 100
            """, (court, days)).fetchall()
        else:
            rows = c.execute("""
                SELECT id, case_name, court_id, date_filed, author_str,
                       per_curiam, doc_type, html_url
                FROM opinions
                WHERE date_filed >= date('now', '-' || ? || ' days')
                ORDER BY date_filed DESC
                LIMIT 100
            """, (days,)).fetchall()
        return [dict(r) for r in rows]


# ─────────────────────────────────────────────
# SYNC META
# ─────────────────────────────────────────────

def get_meta(key: str) -> str | None:
    with conn() as c:
        row = c.execute(
            "SELECT value FROM sync_meta WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else None


def set_meta(key: str, value: str) -> None:
    with writable_conn() as c:
        c.execute("""
            INSERT INTO sync_meta(key, value, updated_at)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(key) DO UPDATE
            SET value = excluded.value, updated_at = excluded.updated_at
        """, (key, value))
        c.commit()


def db_stats() -> dict:
    """Quick health check — counts for the dashboard."""
    with conn() as c:
        ic_count = c.execute("SELECT COUNT(*) FROM ic_sections").fetchone()[0]
        op_count = c.execute("SELECT COUNT(*) FROM opinions").fetchone()[0]
        last_sync = get_meta("opinions_last_sync") or "never"
        ic_year   = get_meta("ic_year") or "unknown"
        return {
            "ic_sections": ic_count,
            "opinions":    op_count,
            "ic_year":     ic_year,
            "last_opinion_sync": last_sync,
        }
