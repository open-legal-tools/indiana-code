"""Read-only tool functions over the store. Plain functions returning dicts; the MCP server only wires them up."""
import datetime
import json
import re
import sqlite3

from . import asof, case_cites
from .asof import DISCLAIMER
from .caselaw import COURTS, SOURCE as CASE_SOURCE

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


def _has_companion(conn) -> bool:
    row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='companion_page'").fetchone()
    return bool(row) and conn.execute("SELECT 1 FROM companion_page LIMIT 1").fetchone() is not None


def list_companion(conn, kind=None, year=None):
    """Companion documents loaded from the IGA downloads page (Constitution, Non-code, Acts text, archive titles)."""
    out = {"documents": [], **_assurance(conn)}
    if not _has_companion(conn):
        out["flags"] = ["no companion documents loaded; Constitution, Non-code and full Acts PDFs are on the IGA downloads page"]
        return out
    sql = "SELECT doc_id, kind, year, title, source_file, max(page) AS pages FROM companion_page"
    where, args = [], []
    if kind:
        where.append("kind=?"); args.append(kind)
    if year:
        where.append("year=?"); args.append(int(year))
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " GROUP BY doc_id ORDER BY year, kind, doc_id"
    out["documents"] = [dict(r) for r in conn.execute(sql, args)]
    return out


def search_companion(conn, query, kind=None, year=None, limit=10):
    """Full-text search of companion PDFs (Constitution, Non-code, full Acts, archive titles)."""
    limit = max(1, min(int(limit), 25))
    out = {"query": query, "results": [], **_assurance(conn)}
    if not _has_companion(conn):
        out["flags"] = ["no companion documents loaded"]
        return out
    if not _words(query):
        out["flags"] = ["empty query"]
        return out
    fts = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='companion_fts'").fetchone()
    if not fts:
        out["flags"] = ["companion_fts index missing; rebuild with indiana_law.cli ingest-companion"]
        return out
    sql = ("SELECT c.doc_id, c.kind, c.year, c.title, c.page, snippet(companion_fts, 0, '[', ']', '...', 24) AS snip "
           "FROM companion_fts JOIN companion_page c ON c.pid=companion_fts.rowid WHERE companion_fts MATCH ? ")
    args: list = [_fts_query(query, "all")]
    if kind:
        sql += "AND c.kind=? "; args.append(kind)
    if year:
        sql += "AND c.year=? "; args.append(int(year))
    sql += "LIMIT ?"
    args.append(limit)
    try:
        rows = list(conn.execute(sql, args))
    except sqlite3.OperationalError:
        rows = []
    if not rows:
        args[0] = _fts_query(query, "any")
        rows = list(conn.execute(sql, args))
        if rows:
            out.setdefault("flags", []).append("no page contained every word; results match some of the words")
    out["results"] = [{"doc_id": r["doc_id"], "kind": r["kind"], "year": r["year"], "title": r["title"],
                       "page": r["page"], "snippet": r["snip"]} for r in rows]
    if not out["results"]:
        out.setdefault("flags", []).append("no companion matches")
    return out


def get_companion(conn, doc_id, page=1):
    """One page of a companion document. page is 1-based."""
    out = {"doc_id": doc_id, "found": False, **_assurance(conn)}
    if not _has_companion(conn):
        out["flags"] = ["no companion documents loaded"]
        return out
    page = max(1, int(page))
    row = conn.execute("SELECT * FROM companion_page WHERE doc_id=? AND page=?", (doc_id, page)).fetchone()
    total = conn.execute("SELECT max(page) FROM companion_page WHERE doc_id=?", (doc_id,)).fetchone()[0]
    if row:
        out.update(found=True, kind=row["kind"], year=row["year"], title=row["title"],
                   source_file=row["source_file"], page=row["page"], page_count=total, text=row["text"])
        if total and page < total:
            out["flags"] = [f"{total} pages; pass page={page + 1} for the next page"]
    else:
        out["flags"] = ["companion page not found"]
        out["page_count"] = total
    return out


def _has_cases(conn) -> bool:
    row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='case_cluster'").fetchone()
    return bool(row) and conn.execute("SELECT 1 FROM case_cluster LIMIT 1").fetchone() is not None


def _has_case_forms(conn) -> bool:
    row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='case_form'").fetchone()
    return bool(row) and conn.execute("SELECT 1 FROM case_form LIMIT 1").fetchone() is not None


def _form_for(conn, cluster_id):
    if not _has_case_forms(conn):
        return None
    return conn.execute("SELECT * FROM case_form WHERE cluster_id=?", (str(cluster_id),)).fetchone()


def _case_flags(row, form_row=None) -> list[str]:
    flags = ["unofficial CourtListener extract; not a citator; not legal advice"]
    if not row["has_opinion_text"]:
        flags.append("no opinion body in this extract; cluster metadata only")
    if form_row:
        flags.append(
            "decision_form is a text classification of the slip opinion, not official publication status"
        )
        if form_row["disagrees_with_source"]:
            flags.append(
                f"text form is {form_row['decision_form']}; CourtListener precedential_status is {row['precedential_status']}"
            )
        if form_row["citability"] == "persuasive":
            flags.append("App. R. 65(D): memorandum on or after 2023-01-01 may be cited for persuasive value")
        elif form_row["citability"] == "limited":
            flags.append("App. R. 65(D) as then in force: memorandum generally not citable as precedent")
    return flags


def search_cases(conn, query, court=None, after=None, before=None, form=None, limit=10):
    """Search Indiana opinion clusters (Supreme Court, Court of Appeals, Tax Court)."""
    limit = max(1, min(int(limit), 25))
    out = {"query": query, "results": [], "source": CASE_SOURCE, **_assurance(conn)}
    if not _has_cases(conn):
        out["flags"] = ["no caselaw loaded"]
        return out
    if not _words(query):
        out["flags"] = ["empty query"]
        return out
    fts = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='case_fts'").fetchone()
    if not fts:
        out["flags"] = ["case_fts index missing; rebuild with indiana_law.cli ingest-caselaw"]
        return out
    join_form = _has_case_forms(conn)
    sql = (
        "SELECT c.cluster_id, c.court_id, c.court, c.case_name, c.date_filed, c.precedential_status, "
        "c.has_opinion_text, snippet(case_fts, 0, '[', ']', '...', 24) AS snip"
    )
    if join_form:
        sql += ", f.decision_form, f.citability"
    sql += " FROM case_fts JOIN case_cluster c ON c.rowid=case_fts.rowid"
    if join_form:
        sql += " LEFT JOIN case_form f ON f.cluster_id=c.cluster_id"
    sql += " WHERE case_fts MATCH ?"
    args: list = [_fts_query(query, "all")]
    if court:
        sql += " AND c.court_id=?"
        args.append(court if court in COURTS else court)
    if after:
        sql += " AND c.date_filed>=?"
        args.append(after)
    if before:
        sql += " AND c.date_filed<=?"
        args.append(before)
    if form and join_form:
        sql += " AND f.decision_form=?"
        args.append(form)
    sql += " LIMIT ?"
    args.append(limit)
    try:
        rows = list(conn.execute(sql, args))
    except sqlite3.OperationalError:
        rows = []
    if not rows:
        args[0] = _fts_query(query, "any")
        rows = list(conn.execute(sql, args))
        if rows:
            out.setdefault("flags", []).append("no cluster contained every word; results match some of the words")
    out["results"] = [{
        "cluster_id": r["cluster_id"], "court": r["court"], "court_id": r["court_id"],
        "case_name": r["case_name"], "date_filed": r["date_filed"],
        "precedential_status": r["precedential_status"],
        "has_opinion_text": bool(r["has_opinion_text"]), "snippet": r["snip"],
        **({"decision_form": r["decision_form"], "citability": r["citability"]} if join_form else {}),
    } for r in rows]
    if not out["results"]:
        out.setdefault("flags", []).append("no caselaw matches")
    out.setdefault("flags", []).append("opinion bodies from Harvard CAP and official Indiana court PDFs when present; not a complete set")
    return out


def get_case(conn, cluster_id):
    """One Indiana opinion cluster, with opinion text when the extract has it."""
    out = {"cluster_id": cluster_id, "found": False, "source": CASE_SOURCE, **_assurance(conn)}
    if not _has_cases(conn):
        out["flags"] = ["no caselaw loaded"]
        return out
    row = conn.execute("SELECT * FROM case_cluster WHERE cluster_id=?", (str(cluster_id),)).fetchone()
    if not row:
        out["flags"] = ["cluster not found"]
        return out
    form_row = _form_for(conn, cluster_id)
    out.update(
        found=True,
        court=row["court"],
        court_id=row["court_id"],
        case_name=row["case_name"],
        date_filed=row["date_filed"],
        docket_id=row["docket_id"],
        precedential_status=row["precedential_status"],
        slug=row["slug"],
        citation_count=row["citation_count"],
        summary=row["summary"],
        headmatter=row["headmatter"],
        has_opinion_text=bool(row["has_opinion_text"]),
        text_source=row["text_source"],
        text=row["opinion_text"],
        url=f"https://www.courtlistener.com/opinion/{row['cluster_id']}/{row['slug']}/" if row["slug"] else CASE_SOURCE,
        flags=_case_flags(row, form_row),
    )
    if form_row:
        out["decision_form"] = form_row["decision_form"]
        out["citability"] = form_row["citability"]
        out["case_number_in_text"] = form_row["case_number_in_text"]
    if _has_case_cites(conn):
        cited = list(conn.execute(
            "SELECT cite_kind, raw_cite, cite_key FROM case_cite WHERE cluster_id=?",
            (str(cluster_id),),
        ))
        out["reporter_cites"] = [
            (r["raw_cite"] or r["cite_key"]) for r in cited if r["cite_kind"] == "reporter"
        ]
        out["case_numbers"] = [
            (r["raw_cite"] or r["cite_key"]).removeprefix("docket|")
            for r in cited if r["cite_kind"] == "docket"
        ]
    if _has_case_mentions(conn):
        out["citing_this"] = conn.execute(
            "SELECT count(*) FROM case_mention WHERE cited_id=?", (str(cluster_id),)
        ).fetchone()[0]
        out["cited_by_this"] = conn.execute(
            "SELECT count(*) FROM case_mention WHERE citing_id=?", (str(cluster_id),)
        ).fetchone()[0]
    return out


def _has_mentions(conn) -> bool:
    row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='statute_mention'").fetchone()
    return bool(row) and conn.execute("SELECT 1 FROM statute_mention LIMIT 1").fetchone() is not None


def cases_citing(conn, section_id, court=None, after=None, before=None, limit=25):
    """Opinions whose text mentions a Code section. Not treatment, not a citator, not good law."""
    ids = asof.normalize_citation(section_id) or [str(section_id or "").strip()]
    sid = ids[0] if ids else ""
    limit = max(1, min(int(limit), 50))
    out = {
        "section_id": sid,
        "citation": _citation(sid) if sid else "",
        "results": [],
        "source": CASE_SOURCE,
        **_assurance(conn),
    }
    flags = [
        "text mentions of this section id in opinion bodies; not a citator; not treatment; not good law",
        "unofficial CourtListener extract; not legal advice",
    ]
    if not sid:
        out["flags"] = flags + ["empty section id"]
        return out
    if not _has_cases(conn):
        out["flags"] = flags + ["no caselaw loaded"]
        return out
    if not _has_mentions(conn):
        out["flags"] = flags + ["no statute mentions indexed; run indiana_law.cli ingest-statute-mentions"]
        return out
    sql = (
        "SELECT m.mention_count, m.as_of, m.code_resolved, "
        "c.cluster_id, c.court_id, c.court, c.case_name, c.date_filed, "
        "c.docket_id, c.precedential_status, c.has_opinion_text "
        "FROM statute_mention m JOIN case_cluster c ON c.cluster_id=m.cluster_id "
        "WHERE m.section_id=?"
    )
    args: list = [sid]
    if court:
        sql += " AND c.court_id=?"
        args.append(court if court in COURTS else court)
    if after:
        sql += " AND c.date_filed>=?"
        args.append(after)
    if before:
        sql += " AND c.date_filed<=?"
        args.append(before)
    sql += " ORDER BY c.date_filed DESC LIMIT ?"
    args.append(limit)
    rows = list(conn.execute(sql, args))
    out["results"] = [{
        "cluster_id": r["cluster_id"],
        "court": r["court"],
        "court_id": r["court_id"],
        "case_name": r["case_name"],
        "date_filed": r["date_filed"],
        "docket_id": r["docket_id"],
        "precedential_status": r["precedential_status"],
        "has_opinion_text": bool(r["has_opinion_text"]),
        "mention_count": r["mention_count"],
        "as_of": r["as_of"],
        "code_resolved": bool(r["code_resolved"]),
    } for r in rows]
    total = conn.execute("SELECT count(*) FROM statute_mention WHERE section_id=?", (sid,)).fetchone()[0]
    out["match_count"] = len(out["results"])
    out["indexed_mention_count"] = total
    if total > len(out["results"]):
        flags.append(f"{total} opinions mention this id; showing {len(out['results'])}")
    if not out["results"]:
        flags.append("no indexed opinion mentions this section id")
    unresolved = sum(1 for r in out["results"] if not r["code_resolved"])
    if unresolved:
        flags.append(
            f"{unresolved} of these opinions predate the structured Code snapshots or cite an id not in the store"
        )
    out["flags"] = flags
    return out


def _has_case_cites(conn) -> bool:
    row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='case_cite'").fetchone()
    return bool(row) and conn.execute("SELECT 1 FROM case_cite LIMIT 1").fetchone() is not None


def _has_case_mentions(conn) -> bool:
    row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='case_mention'").fetchone()
    return bool(row) and conn.execute("SELECT 1 FROM case_mention LIMIT 1").fetchone() is not None


def resolve_case_query(conn, query: str) -> dict:
    """cluster_id, '848 N.E.2d 341', or '22A-CT-925' → cluster ids. Ambiguous keys stay listed."""
    q = (query or "").strip()
    out = {"query": q, "cluster_ids": [], "cite_key": None, "ambiguous": False}
    if not q:
        return out
    row = conn.execute("SELECT cluster_id FROM case_cluster WHERE cluster_id=?", (q,)).fetchone()
    if row:
        out["cluster_ids"] = [row["cluster_id"]]
        return out
    key = case_cites.parse_reporter_cite(q) or case_cites.docket_key(q)
    out["cite_key"] = key
    if not key or not _has_case_cites(conn):
        return out
    ids = [r[0] for r in conn.execute("SELECT cluster_id FROM case_cite WHERE cite_key=?", (key,))]
    out["cluster_ids"] = ids
    out["ambiguous"] = len(ids) > 1
    return out


def _case_card(r) -> dict:
    return {
        "cluster_id": r["cluster_id"],
        "court": r["court"],
        "court_id": r["court_id"],
        "case_name": r["case_name"],
        "date_filed": r["date_filed"],
        "docket_id": r["docket_id"],
        "precedential_status": r["precedential_status"],
        "has_opinion_text": bool(r["has_opinion_text"]),
        "mention_count": r["mention_count"],
        "cite_kind": r["cite_kind"],
        "as_of": r["as_of"],
    }


def cases_citing_case(conn, query, court=None, after=None, before=None, limit=25):
    """Opinions whose text cites this case. Not treatment, not a citator, not good law."""
    limit = max(1, min(int(limit), 50))
    resolved = resolve_case_query(conn, query)
    out = {
        "query": resolved["query"],
        "cite_key": resolved["cite_key"],
        "cluster_id": resolved["cluster_ids"][0] if len(resolved["cluster_ids"]) == 1 else None,
        "results": [],
        "source": CASE_SOURCE,
        **_assurance(conn),
    }
    flags = [
        "text mentions of a reporter or Rule 22 case number; not a citator; not treatment; not good law",
        "unofficial CourtListener extract plus Harvard CAP identifiers; not legal advice",
        "Id. / supra / Westlaw-only cites are not resolved; table-page reporter cites stay unresolved when several opinions share a page",
    ]
    if not resolved["query"]:
        out["flags"] = flags + ["empty query"]
        return out
    if not _has_cases(conn):
        out["flags"] = flags + ["no caselaw loaded"]
        return out
    if resolved["ambiguous"]:
        out["candidates"] = resolved["cluster_ids"]
        out["flags"] = flags + ["citation matches more than one cluster in this extract; not resolved"]
        return out
    if not resolved["cluster_ids"]:
        out["flags"] = flags + ["no cluster matches this id, reporter cite, or case number"]
        return out
    if not _has_case_mentions(conn):
        out["flags"] = flags + ["no case-to-case mentions indexed; run indiana_law.cli ingest-case-citations"]
        return out
    cid = resolved["cluster_ids"][0]
    out["cluster_id"] = cid
    target = conn.execute(
        "SELECT case_name, date_filed, court FROM case_cluster WHERE cluster_id=?", (cid,)
    ).fetchone()
    if target:
        out["case_name"] = target["case_name"]
        out["date_filed"] = target["date_filed"]
        out["court"] = target["court"]
    sql = (
        "SELECT m.mention_count, m.cite_kind, m.as_of, "
        "c.cluster_id, c.court_id, c.court, c.case_name, c.date_filed, "
        "c.docket_id, c.precedential_status, c.has_opinion_text "
        "FROM case_mention m JOIN case_cluster c ON c.cluster_id=m.citing_id "
        "WHERE m.cited_id=?"
    )
    args: list = [cid]
    if court:
        sql += " AND c.court_id=?"
        args.append(court if court in COURTS else court)
    if after:
        sql += " AND c.date_filed>=?"
        args.append(after)
    if before:
        sql += " AND c.date_filed<=?"
        args.append(before)
    sql += " ORDER BY c.date_filed DESC LIMIT ?"
    args.append(limit)
    rows = list(conn.execute(sql, args))
    out["results"] = [_case_card(r) for r in rows]
    total = conn.execute("SELECT count(*) FROM case_mention WHERE cited_id=?", (cid,)).fetchone()[0]
    out["match_count"] = len(out["results"])
    out["indexed_mention_count"] = total
    if total > len(out["results"]):
        flags.append(f"{total} opinions cite this cluster; showing {len(out['results'])}")
    if not out["results"]:
        flags.append("no indexed opinion cites this cluster")
    out["flags"] = flags
    return out


def cases_cited_in(conn, query, limit=25):
    """Cases this opinion's text cites. Not treatment, not a citator, not good law."""
    limit = max(1, min(int(limit), 50))
    resolved = resolve_case_query(conn, query)
    out = {
        "query": resolved["query"],
        "cite_key": resolved["cite_key"],
        "cluster_id": resolved["cluster_ids"][0] if len(resolved["cluster_ids"]) == 1 else None,
        "results": [],
        "source": CASE_SOURCE,
        **_assurance(conn),
    }
    flags = [
        "reporter and Rule 22 citations extracted from this opinion; not a citator; not treatment; not good law",
        "unofficial CourtListener extract plus Harvard CAP identifiers; not legal advice",
    ]
    if not resolved["query"]:
        out["flags"] = flags + ["empty query"]
        return out
    if not _has_cases(conn):
        out["flags"] = flags + ["no caselaw loaded"]
        return out
    if resolved["ambiguous"]:
        out["candidates"] = resolved["cluster_ids"]
        out["flags"] = flags + ["citation matches more than one cluster in this extract; not resolved"]
        return out
    if not resolved["cluster_ids"]:
        out["flags"] = flags + ["no cluster matches this id, reporter cite, or case number"]
        return out
    if not _has_case_mentions(conn):
        out["flags"] = flags + ["no case-to-case mentions indexed; run indiana_law.cli ingest-case-citations"]
        return out
    cid = resolved["cluster_ids"][0]
    out["cluster_id"] = cid
    target = conn.execute(
        "SELECT case_name, date_filed, court FROM case_cluster WHERE cluster_id=?", (cid,)
    ).fetchone()
    if target:
        out["case_name"] = target["case_name"]
        out["date_filed"] = target["date_filed"]
        out["court"] = target["court"]
    sql = (
        "SELECT m.mention_count, m.cite_kind, m.as_of, "
        "c.cluster_id, c.court_id, c.court, c.case_name, c.date_filed, "
        "c.docket_id, c.precedential_status, c.has_opinion_text "
        "FROM case_mention m JOIN case_cluster c ON c.cluster_id=m.cited_id "
        "WHERE m.citing_id=? ORDER BY c.date_filed DESC LIMIT ?"
    )
    rows = list(conn.execute(sql, (cid, limit)))
    out["results"] = [_case_card(r) for r in rows]
    total = conn.execute("SELECT count(*) FROM case_mention WHERE citing_id=?", (cid,)).fetchone()[0]
    out["match_count"] = len(out["results"])
    out["indexed_mention_count"] = total
    if total > len(out["results"]):
        flags.append(f"{total} cited clusters indexed; showing {len(out['results'])}")
    if not out["results"]:
        flags.append("no indexed case citations in this opinion")
    out["flags"] = flags
    return out
