"""SQLite store for section versions and act clauses. The JSONL files remain canonical; this store is derived and rebuildable."""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from typing import Iterable

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS snapshot(
  snapshot_id TEXT PRIMARY KEY, year INTEGER NOT NULL, compile_date TEXT, compile_date_certain INTEGER NOT NULL DEFAULT 1,
  source_zip_sha256 TEXT, parser_version TEXT);
CREATE TABLE IF NOT EXISTS section_version(
  vid INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL, base_id TEXT NOT NULL, version_suffix TEXT,
  text TEXT NOT NULL, text_hash TEXT NOT NULL, effective_from TEXT NOT NULL DEFAULT '', effective_until TEXT NOT NULL DEFAULT '', status TEXT NOT NULL,
  UNIQUE(id, text_hash, effective_from, effective_until));
CREATE INDEX IF NOT EXISTS ix_sv_base ON section_version(base_id);
CREATE TABLE IF NOT EXISTS appearance(
  snapshot_id TEXT NOT NULL REFERENCES snapshot(snapshot_id), vid INTEGER NOT NULL REFERENCES section_version(vid),
  heading TEXT, history_note TEXT, history_acts TEXT, preamble_notes TEXT,
  title_id TEXT, article_id TEXT, chapter_id TEXT, title_heading TEXT, article_heading TEXT, chapter_heading TEXT, source_file TEXT,
  PRIMARY KEY(snapshot_id, vid));
CREATE TABLE IF NOT EXISTS act(act_id TEXT PRIMARY KEY, year INTEGER, number INTEGER, bill TEXT, approved_on TEXT);
CREATE TABLE IF NOT EXISTS act_clause(
  act_id TEXT NOT NULL, section_in_act INTEGER, kind TEXT, target TEXT, level TEXT,
  effective_date TEXT, basis TEXT, retroactive INTEGER);
CREATE INDEX IF NOT EXISTS ix_clause_target ON act_clause(target);
"""
FTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS section_fts USING fts5(text, content='section_version', content_rowid='vid', tokenize='porter unicode61');
"""


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def text_hash(text: str) -> str:
    return hashlib.sha256(re.sub(r"\s+", " ", text).strip().encode("utf-8")).hexdigest()[:32]


def add_snapshot(conn, snapshot_id: str, year: int, compile_date: str | None = None, certain: bool = True,
                 zip_sha256: str = "", parser_version: str = "") -> None:
    conn.execute("INSERT OR REPLACE INTO snapshot VALUES (?,?,?,?,?,?)",
                 (snapshot_id, year, compile_date, 1 if certain else 0, zip_sha256, parser_version))


def add_records(conn, records: Iterable[dict]) -> int:
    """Insert section records (each carries snapshot_id). Identical versions across snapshots share one row."""
    n = 0
    for r in records:
        h = text_hash(r["text"])
        ef, eu = r["effective_from"] or "", r["effective_until"] or ""  # '' means unbounded (NULLs would defeat the UNIQUE key)
        conn.execute(
            "INSERT OR IGNORE INTO section_version(id,base_id,version_suffix,text,text_hash,effective_from,effective_until,status) VALUES (?,?,?,?,?,?,?,?)",
            (r["id"], r["base_id"], r["version_suffix"], r["text"], h, ef, eu, r["status"]))
        vid = conn.execute("SELECT vid FROM section_version WHERE id=? AND text_hash=? AND effective_from=? AND effective_until=?",
                           (r["id"], h, ef, eu)).fetchone()[0]
        conn.execute(
            "INSERT OR REPLACE INTO appearance VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (r["snapshot_id"], vid, r["section_heading"], r["history_note"], json.dumps(r["history_acts"]), json.dumps(r["preamble_notes"]),
             r["title_id"], r["article_id"], r["chapter_id"], r.get("title_heading"), r.get("article_heading"), r.get("chapter_heading"), r.get("source_file")))
        n += 1
    return n


def add_clauses(conn, clauses: Iterable[dict]) -> int:
    n = 0
    for c in clauses:
        conn.execute("INSERT OR IGNORE INTO act VALUES (?,?,?,?,?)", (c["act"], c["year"], c["act_number"], c["bill"], c["approved"]))
        conn.execute("INSERT INTO act_clause VALUES (?,?,?,?,?,?,?,?)",
                     (c["act"], c["section_in_act"], c["kind"], c["target"], c["level"], c["effective_date"], c["effective_basis"], 1 if c["retroactive"] else 0))
        n += 1
    return n


def finalize(conn) -> None:
    """Build the full-text index. Call after loading."""
    conn.executescript(FTS)
    conn.execute("INSERT INTO section_fts(section_fts) VALUES('rebuild')")
    conn.commit()


def read_jsonl(path: str):
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                yield json.loads(line)
