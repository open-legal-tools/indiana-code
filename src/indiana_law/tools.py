"""Read-only tool functions over the store. Plain functions returning dicts; the MCP server only wires them up."""
import datetime
import json
import re
import sqlite3

from . import asof
from .asof import DISCLAIMER

SOURCE_PAGE = "https://iga.in.gov/laws/ic/downloads"


def _latest(conn):
    return conn.execute("SELECT * FROM snapshot ORDER BY year DESC LIMIT 1").fetchone()


def _assurance(conn, snapshot=None):
    snap = snapshot or _latest(conn)
    return {
        "unofficial": True, "disclaimer": DISCLAIMER, "source_page": SOURCE_PAGE,
        "snapshot_id": snap["snapshot_id"] if snap else None, "snapshot_year": snap["year"] if snap else None,
        "compiled_on": snap["compile_date"] if snap else None,
        "data_years": [r[0] for r in conn.execute("SELECT year FROM snapshot ORDER BY year")],
    }


def _citation(section_id):
    return f"IC {section_id}"


_STOP = {"a", "an", "the", "of", "to", "in", "on", "for", "and", "or", "is", "are", "be", "by", "does", "do", "what", "when", "if", "any", "with", "as", "at", "from", "that", "this", "it", "under", "who", "which", "how"}


def _words(q):
    return [w for w in re.findall(r"[\w.]+", q.replace('"', " ")) if w]


def _fts_query(q, mode="all"):
    """mode 'all' requires every word (stop words dropped); mode 'any' ranks sections that match any of the words."""
    words = [w for w in _words(q) if w.lower() not in _STOP] or _words(q)
    return (" OR " if mode == "any" else " ").join('"%s"' % w for w in words)


def search(conn, query, as_of=None, title=None, limit=10):
    """Full-text search of Code sections in the snapshot that applies to `as_of` (default latest). One hit per section."""
    limit = max(1, min(int(limit), 25))
    flags = []
    snap = _latest(conn)
    if as_of:
        y = int(as_of[:4])
        y_use = y if as_of >= f"{y}-07-01" else y - 1
        row = conn.execute("SELECT * FROM snapshot WHERE year=?", (y_use,)).fetchone()
        if row:
            snap = row
            flags.append("search is run on the whole snapshot for that year; use get_section with as_of for exact text")
        else:
            flags.append("no snapshot for that date; searched the latest snapshot")
    out = {"query": query, "results": [], "flags": flags, **_assurance(conn, snap)}
    if not _words(query):
        flags.append("empty query")
        return out
    sql = ("SELECT v.base_id, v.id, v.version_suffix, a.heading, snippet(section_fts, 0, '[', ']', '...', 24) AS snip, bm25(section_fts) AS score "
           "FROM section_fts JOIN section_version v ON v.vid=section_fts.rowid JOIN appearance a ON a.vid=v.vid "
           "WHERE section_fts MATCH ? AND a.snapshot_id=? ")
    tail = ""
    base_args = [snap["snapshot_id"]]
    if title:
        tail += "AND a.title_id=? "
        base_args.append(str(title))
    tail += "ORDER BY score LIMIT ?"
    for mode in ("all", "any"):
        args = [_fts_query(query, mode)] + base_args + [limit * 3]
        seen = set()
        for r in conn.execute(sql + tail, args):
            if r["base_id"] in seen:
                continue
            seen.add(r["base_id"])
            out["results"].append({"section_id": r["base_id"], "citation": _citation(r["base_id"]), "heading": r["heading"], "snippet": r["snip"]})
            if len(out["results"]) >= limit:
                break
        if out["results"]:
            if mode == "any":
                flags.append("no section contained every word; results match some of the words, ranked by relevance")
            break
    if not out["results"]:
        flags.append("no matches; try other words or browse by title (ic_browse)")
    return out


def resolve_citation(conn, text):
    """Find Code section ids in free text and say whether each exists in the latest snapshot."""
    ids = asof.normalize_citation(text)
    snap = _latest(conn)
    res = []
    for sid in dict.fromkeys(ids):
        row = conn.execute(
            "SELECT a.heading FROM section_version v JOIN appearance a ON a.vid=v.vid WHERE a.snapshot_id=? AND v.base_id=? LIMIT 1",
            (snap["snapshot_id"], sid)).fetchone()
        item = {"section_id": sid, "citation": _citation(sid), "exists_in_latest_snapshot": row is not None, "heading": row["heading"] if row else None}
        if row is None:
            near = conn.execute(
                "SELECT DISTINCT v.base_id FROM section_version v JOIN appearance a ON a.vid=v.vid WHERE a.snapshot_id=? AND v.base_id LIKE ? ORDER BY v.base_id LIMIT 5",
                (snap["snapshot_id"], sid.rsplit("-", 1)[0] + "-%")).fetchall()
            item["nearby_sections"] = [r[0] for r in near]
        res.append(item)
    out = {"input": text, "citations": res, **_assurance(conn)}
    if not res:
        out["flags"] = ["no Indiana Code citation found; expected forms like 'IC 31-16-15-25' or 'Ind. Code § 31-16-15-25'"]
    return out


def get_section(conn, section_id, as_of=None):
    """Text of a section as of a date (default today) with assurance fields."""
    when = as_of or datetime.date.today().isoformat()
    ids = asof.normalize_citation(section_id) or [section_id.strip()]
    r = asof.resolve(conn, ids[0], when)
    r["citation"] = _citation(ids[0])
    if not r.get("found") and not r.get("flags"):
        r["flags"] = ["not found"]
    return r


def get_versions(conn, section_id):
    """Every distinct version of a section across the loaded snapshots, with dates and the snapshots it appears in."""
    sid = (asof.normalize_citation(section_id) or [section_id.strip()])[0]
    rows = conn.execute(
        "SELECT v.vid, v.id, v.version_suffix, v.effective_from, v.effective_until, v.status, v.text_hash, a.snapshot_id, s.year, a.history_acts "
        "FROM section_version v JOIN appearance a ON a.vid=v.vid JOIN snapshot s ON s.snapshot_id=a.snapshot_id "
        "WHERE v.base_id=? ORDER BY v.effective_from, v.version_suffix, s.year", (sid,)).fetchall()
    versions = {}
    for r in rows:
        v = versions.setdefault(r["vid"], {"version_id": r["id"], "version_suffix": r["version_suffix"], "effective_from": r["effective_from"] or None,
                                           "effective_until": r["effective_until"] or None, "status": r["status"], "snapshot_years": [],
                                           "amending_acts": json.loads(r["history_acts"] or "[]")})
        v["snapshot_years"].append(r["year"])
    clauses = conn.execute(
        "SELECT c.act_id, c.kind, c.effective_date, c.basis FROM act_clause c WHERE c.target=? ORDER BY c.effective_date", (sid,)).fetchall()
    out = {"section_id": sid, "citation": _citation(sid), "versions": list(versions.values()),
           "act_clauses": [dict(c) for c in clauses], **_assurance(conn)}
    if not versions:
        out["flags"] = ["section not found in any loaded snapshot"]
    return out


def browse(conn, node_id=None):
    """Outline of the Code: titles, then the articles, chapters or sections under a node (latest snapshot)."""
    snap = _latest(conn)
    sid = snap["snapshot_id"]
    out = {"node_id": node_id, "children": [], **_assurance(conn, snap)}
    if not node_id:
        rows = conn.execute("SELECT DISTINCT title_id AS id, title_heading AS heading FROM appearance WHERE snapshot_id=?", (sid,)).fetchall()
        kids = sorted(({"node_id": r["id"], "level": "title", "heading": r["heading"]} for r in rows), key=lambda k: float(k["node_id"]))
    else:
        node_id = node_id.strip().replace("IC ", "")
        parts = node_id.split("-")
        if len(parts) == 1:
            rows = conn.execute("SELECT DISTINCT article_id AS id, article_heading AS heading FROM appearance WHERE snapshot_id=? AND title_id=?", (sid, node_id)).fetchall()
            level = "article"
        elif len(parts) == 2:
            rows = conn.execute("SELECT DISTINCT chapter_id AS id, chapter_heading AS heading FROM appearance WHERE snapshot_id=? AND article_id=?", (sid, node_id)).fetchall()
            level = "chapter"
        elif len(parts) == 3:
            rows = conn.execute(
                "SELECT DISTINCT v.base_id AS id, a.heading AS heading FROM appearance a JOIN section_version v ON v.vid=a.vid WHERE a.snapshot_id=? AND a.chapter_id=?",
                (sid, node_id)).fetchall()
            level = "section"
        else:
            out["flags"] = ["a section is a leaf; use get_section"]
            return out
        def key(k):
            return [float(p) if re.fullmatch(r"\d+(\.\d+)?", p) else 0.0 for p in re.split(r"-|(?<=\d)(?=[a-z]$)", k["node_id"]) if p]
        kids = sorted(({"node_id": r["id"], "level": level, "heading": r["heading"]} for r in rows if r["id"]), key=key)
    out["children"] = kids[:500]
    if len(kids) > 500:
        out["flags"] = [f"{len(kids)} children; showing the first 500"]
    if not kids:
        out.setdefault("flags", []).append("no children found for that node id")
    return out


def get_act(conn, act_id, limit=100, offset=0):
    """The Code targets amended, added or repealed by one public law, with effective dates."""
    m = re.search(r"(\d+)\s*[-‐-―]\s*(\d{4})", act_id)
    aid = f"P.L.{m.group(1)}-{m.group(2)}" if m else act_id.strip()
    act = conn.execute("SELECT * FROM act WHERE act_id=?", (aid,)).fetchone()
    rows = conn.execute("SELECT * FROM act_clause WHERE act_id=? ORDER BY section_in_act", (aid,)).fetchall()
    out = {"act_id": aid, "found": act is not None, **_assurance(conn)}
    if act:
        limit, offset = max(1, min(int(limit), 200)), max(0, int(offset))
        out.update(bill=act["bill"], approved_on=act["approved_on"], total_clauses=len(rows), offset=offset, clauses=[
            {"section_in_act": c["section_in_act"], "kind": c["kind"], "target": c["target"], "level": c["level"],
             "effective_date": c["effective_date"], "effective_basis": c["basis"], "retroactive": bool(c["retroactive"])} for c in rows[offset:offset + limit]])
        if offset + limit < len(rows):
            out["flags"] = [f"{len(rows)} clauses; showing {offset + 1} to {offset + limit}; pass offset={offset + limit} for more"]
    else:
        out["flags"] = ["act not found; expected a form like 'P.L.98-2026' (acts are loaded for 2017 and 2019 to 2026)"]
    return out
