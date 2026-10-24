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
CREATE INDEX IF NOT EXISTS ix_app_title ON appearance(snapshot_id, title_id);
CREATE INDEX IF NOT EXISTS ix_app_article ON appearance(snapshot_id, article_id);
CREATE INDEX IF NOT EXISTS ix_app_chapter ON appearance(snapshot_id, chapter_id);
CREATE INDEX IF NOT EXISTS ix_app_vid ON appearance(vid);
CREATE TABLE IF NOT EXISTS companion_page(
  pid INTEGER PRIMARY KEY AUTOINCREMENT,
  doc_id TEXT NOT NULL, kind TEXT NOT NULL, year INTEGER, title TEXT, source_file TEXT,
  page INTEGER NOT NULL, text TEXT NOT NULL,
  UNIQUE(doc_id, page));
CREATE INDEX IF NOT EXISTS ix_comp_kind ON companion_page(kind, year);
CREATE TABLE IF NOT EXISTS case_cluster(
  cluster_id TEXT PRIMARY KEY,
  court_id TEXT, court TEXT, case_name TEXT, date_filed TEXT, docket_id TEXT,
  precedential_status TEXT, slug TEXT, citation_count INTEGER,
  summary TEXT, headmatter TEXT, opinion_id TEXT, opinion_text TEXT,
  text_source TEXT, has_opinion_text INTEGER NOT NULL DEFAULT 0,
  search_text TEXT);
CREATE INDEX IF NOT EXISTS ix_case_court ON case_cluster(court_id, date_filed);
CREATE TABLE IF NOT EXISTS statute_mention(
  cluster_id TEXT NOT NULL,
  section_id TEXT NOT NULL,
  mention_count INTEGER NOT NULL,
  as_of TEXT,
  code_resolved INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY(cluster_id, section_id));
CREATE INDEX IF NOT EXISTS ix_mention_section ON statute_mention(section_id, as_of);
CREATE TABLE IF NOT EXISTS case_form(
  cluster_id TEXT PRIMARY KEY,
  decision_form TEXT NOT NULL,
  citability TEXT,
  case_number_in_text TEXT,
  disagrees_with_source INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS ix_case_form ON case_form(decision_form, citability);
CREATE TABLE IF NOT EXISTS case_cite(
  cite_key TEXT NOT NULL,
  cluster_id TEXT NOT NULL,
  cite_kind TEXT NOT NULL,
  raw_cite TEXT,
  PRIMARY KEY(cite_key, cluster_id));
CREATE INDEX IF NOT EXISTS ix_case_cite_cluster ON case_cite(cluster_id);
CREATE TABLE IF NOT EXISTS case_mention(
  citing_id TEXT NOT NULL,
  cited_id TEXT NOT NULL,
  mention_count INTEGER NOT NULL,
  cite_kind TEXT NOT NULL,
  as_of TEXT,
  PRIMARY KEY(citing_id, cited_id));
CREATE INDEX IF NOT EXISTS ix_case_mention_cited ON case_mention(cited_id, as_of);
CREATE INDEX IF NOT EXISTS ix_case_mention_citing ON case_mention(citing_id);
CREATE TABLE IF NOT EXISTS case_outbound (
  citing_id TEXT NOT NULL,
  cite_key TEXT NOT NULL,
  reporter TEXT,
  volume TEXT,
  page TEXT,
  court TEXT NOT NULL DEFAULT '',
  year TEXT NOT NULL DEFAULT '',
  raw_cite TEXT,
  mention_count INTEGER NOT NULL,
  as_of TEXT,
  PRIMARY KEY (citing_id, cite_key, court, year));
CREATE INDEX IF NOT EXISTS ix_outbound_court_year ON case_outbound(court, year);
CREATE INDEX IF NOT EXISTS ix_outbound_key ON case_outbound(cite_key);
"""
FTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS section_fts USING fts5(text, content='section_version', content_rowid='vid', tokenize='porter unicode61');
"""
COMPANION_FTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS companion_fts USING fts5(text, content='companion_page', content_rowid='pid', tokenize='porter unicode61');
"""
CASE_FTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS case_fts USING fts5(search_text, content='case_cluster', content_rowid='rowid', tokenize='porter unicode61');
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


def add_companion_pages(conn, pages: Iterable[dict]) -> int:
    n = 0
    for p in pages:
        conn.execute(
            "INSERT OR REPLACE INTO companion_page(doc_id,kind,year,title,source_file,page,text) VALUES (?,?,?,?,?,?,?)",
            (p["doc_id"], p["kind"], p.get("year"), p.get("title"), p.get("source_file"), p["page"], p["text"]))
        n += 1
    return n


def finalize(conn) -> None:
    """Build the full-text index. Call after loading."""
    conn.executescript(FTS)
    conn.execute("INSERT INTO section_fts(section_fts) VALUES('rebuild')")
    conn.commit()


def finalize_companion(conn) -> None:
    conn.executescript(COMPANION_FTS)
    conn.execute("INSERT INTO companion_fts(companion_fts) VALUES('rebuild')")
    conn.commit()


def add_case_clusters(conn, records) -> int:
    n = 0
    conn.executemany(
        "INSERT OR REPLACE INTO case_cluster VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            (
                r["cluster_id"], r["court_id"], r["court"], r["case_name"], r["date_filed"],
                r["docket_id"], r["precedential_status"], r["slug"], r["citation_count"],
                r["summary"], r["headmatter"], r["opinion_id"], r["opinion_text"],
                r["text_source"], r["has_opinion_text"], r["search_text"],
            )
            for r in records
        ),
    )
    n = conn.execute("SELECT count(*) FROM case_cluster").fetchone()[0]
    return n


def replace_case_forms(conn, rows) -> int:
    conn.execute("DELETE FROM case_form")
    conn.executemany(
        "INSERT OR REPLACE INTO case_form(cluster_id, decision_form, citability, case_number_in_text, disagrees_with_source) "
        "VALUES (?,?,?,?,?)",
        rows,
    )
    conn.commit()
    return conn.execute("SELECT count(*) FROM case_form").fetchone()[0]


def replace_statute_mentions(conn, rows) -> int:
    conn.execute("DELETE FROM statute_mention")
    conn.executemany(
        "INSERT OR REPLACE INTO statute_mention(cluster_id, section_id, mention_count, as_of, code_resolved) "
        "VALUES (?,?,?,?,?)",
        rows,
    )
    conn.commit()
    return conn.execute("SELECT count(*) FROM statute_mention").fetchone()[0]


def replace_case_cites(conn, rows) -> int:
    conn.execute("DELETE FROM case_cite")
    conn.executemany(
        "INSERT OR REPLACE INTO case_cite(cite_key, cluster_id, cite_kind, raw_cite) VALUES (?,?,?,?)",
        rows,
    )
    conn.commit()
    return conn.execute("SELECT count(*) FROM case_cite").fetchone()[0]


def replace_case_mentions(conn, rows) -> int:
    conn.execute("DELETE FROM case_mention")
    conn.executemany(
        "INSERT OR REPLACE INTO case_mention(citing_id, cited_id, mention_count, cite_kind, as_of) "
        "VALUES (?,?,?,?,?)",
        rows,
    )
    conn.commit()
    return conn.execute("SELECT count(*) FROM case_mention").fetchone()[0]


def replace_case_outbound(conn, rows) -> int:
    conn.execute("DELETE FROM case_outbound")
    conn.executemany(
        "INSERT OR REPLACE INTO case_outbound("
        "citing_id, cite_key, reporter, volume, page, court, year, raw_cite, mention_count, as_of) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        rows,
    )
    conn.commit()
    return conn.execute("SELECT count(*) FROM case_outbound").fetchone()[0]


def finalize_cases(conn) -> None:
    conn.executescript(CASE_FTS)
    conn.execute("INSERT INTO case_fts(case_fts) VALUES('rebuild')")
    conn.commit()


def read_jsonl(path: str):
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                yield json.loads(line)
