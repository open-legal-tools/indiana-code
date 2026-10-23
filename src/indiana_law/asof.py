"""Answer "what did section X say on date D" over annual snapshots plus act clauses.

Model (measured on ten years of data; see docs/DESIGN-schema-v1.md): each annual file's undated base text reflects
the law as of July 1 of that year; later effective dates appear as dated versions. For a date before July 1 the
session's act clauses decide whether this year's file or the previous year's is closer.
"""
from __future__ import annotations

import json
import re
import sqlite3

DISCLAIMER = ("Unofficial copy of the Indiana Code from the Indiana General Assembly's annual download. Not legal advice, not an "
              "official publication; it may be incomplete or out of date. Verify against the official source at iga.in.gov.")
_CITE = re.compile(r"(?:I\.?\s?C\.?|Ind\.?\s*Code)?\s*§?\s*(\d+(?:\.\d+)?)[\-‐-―](\d+(?:\.\d+)?)[\-‐-―](\d+(?:\.\d+)?)[\-‐-―](\d+(?:\.\d+)?)", re.I)
_STATUTE_CITE = re.compile(
    r"(?:Ind(?:iana)?\.?\s*Code|I\.?\s*C\.?)\s*§?\s*"
    r"(\d+(?:\.\d+)?)[\-‐-―](\d+(?:\.\d+)?)[\-‐-―](\d+(?:\.\d+)?)[\-‐-―](\d+(?:\.\d+)?)",
    re.I,
)


def normalize_citation(text: str) -> list[str]:
    """Extract section ids from strings such as 'IC 31-16-15-25', 'I.C. § 31-16-15-25' or 'Ind. Code § 31-16-15-25 (2024)'."""
    return ["-".join(m.groups()) for m in _CITE.finditer(text)]


def extract_statute_citations(text: str) -> list[str]:
    """IC mentions that include an Ind. Code / IC prefix. Order preserved; duplicates kept."""
    return ["-".join(m.groups()) for m in _STATUTE_CITE.finditer(text or "")]


def _snapshot_for_year(conn, year: int):
    return conn.execute("SELECT * FROM snapshot WHERE year=?", (year,)).fetchone()


def _versions(conn, snapshot_id: str, base_id: str):
    return conn.execute(
        "SELECT v.*, a.heading, a.history_note, a.history_acts, a.preamble_notes, a.source_file FROM section_version v "
        "JOIN appearance a ON a.vid=v.vid WHERE a.snapshot_id=? AND v.base_id=?", (snapshot_id, base_id)).fetchall()


def _operative(rows, d: str):
    ok = [r for r in rows if (not r["effective_from"] or r["effective_from"] <= d) and (not r["effective_until"] or d < r["effective_until"])]
    return max(ok, key=lambda r: r["effective_from"] or "") if ok else None


def resolve(conn: sqlite3.Connection, section_id: str, as_of: str) -> dict:
    """Return the text of `section_id` as of `as_of` (YYYY-MM-DD) with assurance fields. Never raises for missing data."""
    flags: list[str] = []
    years = [r["year"] for r in conn.execute("SELECT year FROM snapshot ORDER BY year")]
    out = {"section_id": section_id, "as_of": as_of, "found": False, "unofficial": True, "disclaimer": DISCLAIMER, "flags": flags}
    if not years:
        flags.append("no snapshots loaded")
        return out
    y = int(as_of[:4])
    if y < years[0]:
        flags.append(f"date is before the earliest snapshot year ({years[0]}); no answer")
        return out
    beyond = y > years[-1]
    if beyond:
        flags.append(f"date is after the latest snapshot year ({years[-1]}); acts enacted since are not reflected")
        y = years[-1]
    as_of_eff = as_of
    clauses = conn.execute(
        "SELECT c.*, a.year AS act_year FROM act_clause c JOIN act a ON a.act_id=c.act_id WHERE c.target=? AND c.kind IN ('amend','add_section','repeal','other')",
        (section_id,)).fetchall()
    session = [c for c in clauses if c["act_year"] == y and c["effective_date"]]
    has_acts_for_year = conn.execute("SELECT 1 FROM act WHERE year=? LIMIT 1", (y,)).fetchone() is not None
    confidence = "medium"
    if beyond:
        use, confidence = y, "low"
    elif as_of < f"{y}-07-01":
        before = [c for c in session if c["effective_date"] <= as_of]
        after = [c for c in session if c["effective_date"] > as_of]
        if session and before and not after:
            use, confidence = y, "high"
        elif session and after and not before:
            use, confidence = y - 1, "high"
        elif session:
            use, confidence = None, "ambiguous"
            flags.append("partial: some acts from this session were effective on the date and some were not; text cannot be split")
        else:
            use = y if _snapshot_for_year(conn, y) else y - 1
            if not has_acts_for_year:
                flags.append("no act data loaded for this year; date before July 1 may be approximate")
            else:
                confidence = "medium"
    else:
        use = y
        confidence = "high" if _snapshot_for_year(conn, y) else "medium"
    out["confidence"] = confidence
    out["session_acts"] = [{"act": c["act_id"], "effective_date": c["effective_date"], "kind": c["kind"]} for c in session]
    if use is None:
        return out
    snap = _snapshot_for_year(conn, use)
    if snap is None:
        flags.append(f"snapshot for {use} not loaded")
        return out
    rows = _versions(conn, snap["snapshot_id"], section_id)
    row = _operative(rows, as_of_eff)
    if row is None:
        flags.append("section not operative in the chosen snapshot on that date (not yet effective, repealed, or not present)")
        pend = [c for c in clauses if c["effective_date"] and c["effective_date"] > as_of]
        out["pending_acts"] = [{"act": c["act_id"], "effective_date": c["effective_date"], "kind": c["kind"]} for c in pend]
        return out
    out.update(
        found=True, snapshot_id=snap["snapshot_id"], snapshot_year=snap["year"], compiled_on=snap["compile_date"],
        compile_date_certain=bool(snap["compile_date_certain"]), version_id=row["id"], version_suffix=row["version_suffix"],
        effective_from=row["effective_from"] or None, effective_until=row["effective_until"] or None, status=row["status"], heading=row["heading"],
        text=row["text"], amending_acts=json.loads(row["history_acts"] or "[]"), history_note=row["history_note"],
        preamble_notes=json.loads(row["preamble_notes"] or "[]"),
        pending_acts=[{"act": c["act_id"], "effective_date": c["effective_date"], "kind": c["kind"]}
                      for c in clauses if c["effective_date"] and c["effective_date"] > as_of],
        code_edition_year=snap["year"], source_url=f"https://iga.in.gov/laws/ic/{snap['year']}",
    )
    if row["status"] == "repealed":
        flags.append("section is repealed on that date")
    if out["pending_acts"]:
        flags.append("acts effective after this date also amend this section")
    return out


def search(conn: sqlite3.Connection, query: str, snapshot_id: str, limit: int = 10) -> list[dict]:
    """Full-text search within one snapshot. Returns ids, headings and short snippets; fetch full text with `resolve`."""
    rows = conn.execute(
        "SELECT v.base_id, v.id, a.heading, snippet(section_fts, 0, '[', ']', '...', 24) AS snip, bm25(section_fts) AS score "
        "FROM section_fts JOIN section_version v ON v.vid=section_fts.rowid JOIN appearance a ON a.vid=v.vid "
        "WHERE section_fts MATCH ? AND a.snapshot_id=? ORDER BY score LIMIT ?", (query, snapshot_id, limit)).fetchall()
    return [dict(r) for r in rows]
