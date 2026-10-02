-- Indiana Law Database Schema
-- Source: IGA MyIGA API v2.0 (code), CourtListener S3 + API (opinions)
-- SALI doc_type taxonomy from github.com/sali-legal/LMSS

PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- ─────────────────────────────────────────────
-- INDIANA CODE
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS ic_sections (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    citation     TEXT    NOT NULL UNIQUE,   -- "IC 31-14-5-3"
    title_num    INTEGER NOT NULL,
    article_num  INTEGER NOT NULL,
    chapter_num  INTEGER NOT NULL,
    section_num  INTEGER NOT NULL,
    title_name   TEXT,
    article_name TEXT,
    chapter_name TEXT,
    section_name TEXT,
    text         TEXT    NOT NULL,
    official_url TEXT,
    year         INTEGER NOT NULL DEFAULT 2026,
    created_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_ic_title   ON ic_sections(title_num);
CREATE INDEX IF NOT EXISTS idx_ic_chapter ON ic_sections(title_num, article_num, chapter_num);

CREATE VIRTUAL TABLE IF NOT EXISTS ic_fts USING fts5(
    citation     UNINDEXED,
    title_name,
    chapter_name,
    section_name,
    text,
    content      = ic_sections,
    content_rowid= id,
    tokenize     = 'porter ascii'
);

CREATE TRIGGER IF NOT EXISTS ic_ai AFTER INSERT ON ic_sections BEGIN
    INSERT INTO ic_fts(rowid, citation, title_name, chapter_name, section_name, text)
    VALUES (new.id, new.citation, new.title_name, new.chapter_name, new.section_name, new.text);
END;

CREATE TRIGGER IF NOT EXISTS ic_au AFTER UPDATE ON ic_sections BEGIN
    INSERT INTO ic_fts(ic_fts, rowid, citation, title_name, chapter_name, section_name, text)
    VALUES ('delete', old.id, old.citation, old.title_name, old.chapter_name, old.section_name, old.text);
    INSERT INTO ic_fts(rowid, citation, title_name, chapter_name, section_name, text)
    VALUES (new.id, new.citation, new.title_name, new.chapter_name, new.section_name, new.text);
END;

CREATE TRIGGER IF NOT EXISTS ic_ad AFTER DELETE ON ic_sections BEGIN
    INSERT INTO ic_fts(ic_fts, rowid, citation, title_name, chapter_name, section_name, text)
    VALUES ('delete', old.id, old.citation, old.title_name, old.chapter_name, old.section_name, old.text);
END;

-- ─────────────────────────────────────────────
-- COURT OPINIONS
-- SALI doc_type from LMSS appellate taxonomy
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS opinions (
    id           INTEGER PRIMARY KEY,   -- CourtListener opinion ID
    cluster_id   INTEGER,               -- CourtListener cluster ID
    case_name    TEXT    NOT NULL,
    court_id     TEXT    NOT NULL CHECK(court_id IN ('ind', 'indctapp', 'indtc')),
    date_filed   TEXT,                  -- ISO date YYYY-MM-DD
    author_str   TEXT,
    per_curiam   INTEGER NOT NULL DEFAULT 0,
    -- SALI LMSS appellate taxonomy — same enum as case-reader rail_entries.doc_type
    doc_type     TEXT    CHECK(doc_type IN (
                     'opinion', 'order', 'petition', 'brief',
                     'motion', 'exhibit', 'transcript', 'docket', 'other'
                 )) DEFAULT 'opinion',
    doc_type_iri TEXT,                  -- full LMSS IRI when known
    plain_text   TEXT,
    html_url     TEXT,                  -- CourtListener canonical URL
    download_url TEXT,                  -- PDF source
    created_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_opinions_court ON opinions(court_id);
CREATE INDEX IF NOT EXISTS idx_opinions_date  ON opinions(date_filed DESC);
CREATE INDEX IF NOT EXISTS idx_opinions_cluster ON opinions(cluster_id);

CREATE VIRTUAL TABLE IF NOT EXISTS opinions_fts USING fts5(
    case_name,
    plain_text,
    content      = opinions,
    content_rowid= id,
    tokenize     = 'porter ascii'
);

CREATE TRIGGER IF NOT EXISTS op_ai AFTER INSERT ON opinions BEGIN
    INSERT INTO opinions_fts(rowid, case_name, plain_text)
    VALUES (new.id, new.case_name, new.plain_text);
END;

CREATE TRIGGER IF NOT EXISTS op_au AFTER UPDATE ON opinions BEGIN
    INSERT INTO opinions_fts(opinions_fts, rowid, case_name, plain_text)
    VALUES ('delete', old.id, old.case_name, old.plain_text);
    INSERT INTO opinions_fts(rowid, case_name, plain_text)
    VALUES (new.id, new.case_name, new.plain_text);
END;

CREATE TRIGGER IF NOT EXISTS op_ad AFTER DELETE ON opinions BEGIN
    INSERT INTO opinions_fts(opinions_fts, rowid, case_name, plain_text)
    VALUES ('delete', old.id, old.case_name, old.plain_text);
END;

-- ─────────────────────────────────────────────
-- SYNC STATE
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS sync_meta (
    key        TEXT NOT NULL PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Seed defaults
INSERT OR IGNORE INTO sync_meta(key, value) VALUES
    ('ic_year',             '2026'),
    ('opinions_last_sync',  ''),
    ('schema_version',      '1');
