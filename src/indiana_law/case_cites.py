"""Case-to-case citation index. Text matches only; not a citator; not legal advice.

Reporter identifiers for Indiana opinions come from Harvard CAP metadata
(joined by cap id on the CourtListener filepath). Outbound cites are extracted
with a reporter regex shaped by the CC0 Indigo Book 2d ed. (2023-2) tables
T1.1 / T3 / T9 / T12 and rules R11.1 / R12, plus Indiana Rule 22 case numbers.
Federal and sister-state cites are stored as unresolved keys: this store has
Indiana opinion bodies, not those courts. Ambiguous Indiana reporter keys
(several opinions on one table page) are stored but not resolved into edges.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict

from . import store

_REPORTER_DISPLAY = {
    "ne2d": "N.E.2d",
    "ne3d": "N.E.3d",
    "ne": "N.E.",
    "ind": "Ind.",
    "ind-app": "Ind. App.",
    "ind-l-rep": "Ind. L. Rep.",
    "blackf": "Blackf.",
    "wilson": "Wilson",
    "us": "U.S.",
    "sct": "S. Ct.",
    "led": "L. Ed.",
    "led2d": "L. Ed. 2d",
    "f": "F.",
    "f2d": "F.2d",
    "f3d": "F.3d",
    "f4th": "F.4th",
    "fsupp": "F. Supp.",
    "fsupp2d": "F. Supp. 2d",
    "fsupp3d": "F. Supp. 3d",
    "fappx": "F. App'x",
    "nw": "N.W.",
    "nw2d": "N.W.2d",
    "se": "S.E.",
    "se2d": "S.E.2d",
    "sw": "S.W.",
    "sw2d": "S.W.2d",
    "sw3d": "S.W.3d",
    "so": "So.",
    "so2d": "So. 2d",
    "so3d": "So. 3d",
    "a2d": "A.2d",
    "a3d": "A.3d",
    "p2d": "P.2d",
    "p3d": "P.3d",
    "wl": "WL",
}

# Harvard slugs, Indigo T1.1 / T3 abbreviations, and the strings opinions use.
_REPORTER_ALIASES = {
    "ne2d": "ne2d",
    "ne2": "ne2d",
    "ne3d": "ne3d",
    "ne3": "ne3d",
    "ne": "ne",
    "ind": "ind",
    "indapp": "ind-app",
    "indlrep": "ind-l-rep",
    "blackf": "blackf",
    "blackford": "blackf",
    "wilson": "wilson",
    "wilsons": "wilson",
    "us": "us",
    "sct": "sct",
    "led": "led",
    "led2d": "led2d",
    "f": "f",
    "f2d": "f2d",
    "f3d": "f3d",
    "f4th": "f4th",
    "fsupp": "fsupp",
    "fsupp2d": "fsupp2d",
    "fsupp3d": "fsupp3d",
    "fappx": "fappx",
    "fedappx": "fappx",
    "nw": "nw",
    "nw2d": "nw2d",
    "se": "se",
    "se2d": "se2d",
    "sw": "sw",
    "sw2d": "sw2d",
    "sw3d": "sw3d",
    "so": "so",
    "so2d": "so2d",
    "so3d": "so3d",
    "a2d": "a2d",
    "a3d": "a3d",
    "p2d": "p2d",
    "p3d": "p3d",
    "wl": "wl",
}

# Longer names first. U.S. is not U.S.C. Bare A. / P. are omitted (too noisy).
_REPORTER_NAME = r"""
    F\.?\s*Supp\.?\s*3d |
    F\.?\s*Supp\.?\s*2d |
    F\.?\s*Supp\.? |
    F\.?\s*App(?:['’]?x)? |
    Fed\.?\s*Appx\.? |
    F\.?\s*4th |
    F\.?\s*3d |
    F\.?\s*2d |
    L\.?\s*Ed\.?\s*2d |
    L\.?\s*Ed\.? |
    S\.?\s*Ct\.? |
    U\.S\.(?!\s*C\.) |
    N\.?\s*E\.?\s*3d |
    N\.?\s*E\.?\s*2d |
    N\.?\s*E\.? |
    N\.?\s*W\.?\s*2d |
    N\.?\s*W\.? |
    S\.?\s*E\.?\s*2d |
    S\.?\s*E\.? |
    S\.?\s*W\.?\s*3d |
    S\.?\s*W\.?\s*2d |
    S\.?\s*W\.? |
    So\.?\s*3d |
    So\.?\s*2d |
    So\. |
    A\.?\s*3d |
    A\.?\s*2d |
    P\.?\s*3d |
    P\.?\s*2d |
    Ind\.\s*App\. |
    Ind\.\s*L\.\s*Rep\. |
    Blackf(?:ord)?\.? |
    Wilson(?:['’]s)? |
    Ind\. |
    F\.
"""

# R11.1 / R12: volume reporter first-page [, pin] [(court year)].
# Pinpoints stop before the next volume+reporter (parallel U.S. / S. Ct. / L. Ed.).
_REPORTER_CITE = re.compile(
    rf"""
    \b(?P<volume>\d+)\s+
    (?P<reporter>{_REPORTER_NAME})
    \s+(?P<page>\d+)\b
    (?P<pin>(?:\s*,\s*(?!\d+\s+(?:{_REPORTER_NAME}))\d+(?:-\d+)?)*)
    (?:\s*\(\s*(?P<paren>[^)]{{0,80}})\s*\))?
    """,
    re.I | re.X,
)

_WL = re.compile(
    r"""
    \b(?P<year>\d{4})\s+WL\s+(?P<id>\d+)
    (?:\s*,?\s*at\s*\*?\d+)?
    (?:\s*\(\s*(?P<paren>[^)]{0,80})\s*\))?
    """,
    re.I | re.X,
)

_PAREN = re.compile(
    r"""
    \(\s*
    (?P<court>
        (?:Bankr\.\s*)?
        (?:
            \d{1,2}(?:st|nd|rd|th)\s*Cir\.? |
            D\.C\.\s*Cir\.? |
            Fed\.\s*Cir\.? |
            [NSCEMW]\.?D\.?\s*[A-Z][A-Za-z.]{1,16} |
            [A-Z][A-Za-z.]{1,16}
            (?:\s+(?:Ct\.\s*)?App\.? |
                \s+Super\.\s*Ct\.? |
                \s+T\.?C\.?)?
        )
    )
    [,\s]+
    (?:
        (?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?
        \s+\d{1,2},\s+
    )?
    (?P<year>\d{4})
    \s*\)
    """,
    re.I | re.X,
)

_COURT_YEAR_QUERY = re.compile(
    r"""
    ^\s*
    (?P<court>.+?)
    [,\s]+
    (?P<year>\d{4})
    \s*$
    """,
    re.X,
)

_STATE_COURTS = {
    "ala", "alaska", "ariz", "ark", "cal", "colo", "conn", "del", "dc",
    "fla", "ga", "haw", "idaho", "ill", "ind", "iowa", "kan", "ky", "la",
    "me", "md", "mass", "mich", "minn", "miss", "mo", "mont", "neb", "nev",
    "nh", "nj", "nm", "ny", "nc", "nd", "ohio", "okla", "or", "pa", "ri",
    "sc", "sd", "tenn", "tex", "utah", "vt", "va", "wash", "wva", "wv",
    "wis", "wyo",
}

_JUNK_COURTS = {
    "burns", "west", "eff", "effective", "supp", "amended", "citing",
    "quoting", "emphasis", "footnote", "cleaned", "added", "omitted",
}

_COURT_ALIASES = {
    "7thcir": "7th Cir.",
    "7thcircuit": "7th Cir.",
    "seventhcircuit": "7th Cir.",
    "ndind": "N.D. Ind.",
    "ndindiana": "N.D. Ind.",
    "northerndistrictofindiana": "N.D. Ind.",
    "sdind": "S.D. Ind.",
    "sdindiana": "S.D. Ind.",
    "southerndistrictofindiana": "S.D. Ind.",
    "us": "U.S.",
    "scotus": "U.S.",
    "unitedstatessupremecourt": "U.S.",
    "ind": "Ind.",
    "indctapp": "Ind. Ct. App.",
    "indapp": "Ind. Ct. App.",
    "indianacourtofappeals": "Ind. Ct. App.",
    "indtc": "Ind. T.C.",
    "indtaxct": "Ind. T.C.",
    "dccir": "D.C. Cir.",
    "fedcir": "Fed. Cir.",
    "wva": "W.Va.",
    "wv": "W.Va.",
    "ill": "Ill.",
    "ohio": "Ohio",
    "ky": "Ky.",
    "wis": "Wis.",
    "mich": "Mich.",
    "cal": "Cal.",
    "ny": "N.Y.",
    "tex": "Tex.",
    "fla": "Fla.",
}

_DOCKET = re.compile(r"\b(\d{2})([AST])-([A-Z]{2})-0*(\d+)\b", re.I)


def normalize_reporter(reporter: str) -> str:
    """Map 'N.E.2d' / 'Ind. App.' / 'ne2d' to the Harvard slug, or ''."""
    slug = re.sub(r"[^a-z0-9]", "", (reporter or "").lower())
    return _REPORTER_ALIASES.get(slug, "")


def reporter_key(reporter: str, volume: str, page: str) -> str | None:
    slug = normalize_reporter(reporter)
    vol = str(volume or "").strip()
    pg = str(page or "").strip()
    if not slug or not vol.isdigit() or not pg.isdigit():
        return None
    return f"{slug}|{vol}|{pg}"


def normalize_court(text: str) -> str:
    """Map '7th Cir', 'N.D.Ind.', 'seventh circuit' to an Indigo-style court label."""
    raw = re.sub(r"\s+", " ", (text or "").strip().strip(".,"))
    if not raw:
        return ""
    compact = re.sub(r"[^a-z0-9]", "", raw.lower())
    if compact in _COURT_ALIASES:
        return _COURT_ALIASES[compact]
    m = re.fullmatch(r"(\d{1,2})(st|nd|rd|th|d)cir", compact)
    if m:
        ordinal = "d" if m.group(2) == "d" else m.group(2)
        return f"{m.group(1)}{ordinal} Cir."
    m = re.fullmatch(r"(\d{1,2})(st|nd|rd|th|d)\.?\s*cir\.?", raw, re.I)
    if m:
        ordinal = "d" if m.group(2).lower() == "d" else m.group(2).lower()
        return f"{m.group(1)}{ordinal} Cir."
    m = re.fullmatch(r"([nscemw])\.?\s*d\.?\s*([a-z.]+)", raw, re.I)
    if m:
        geo = re.sub(r"\.", "", m.group(2)).title()
        if geo.lower() in {"ind", "indiana"}:
            geo = "Ind"
        return f"{m.group(1).upper()}.D. {geo}."
    m = re.fullmatch(r"([a-z.]+)\s+(?:ct\.?\s*)?app\.?", raw, re.I)
    if m:
        geo = m.group(1).rstrip(".")
        return f"{geo}. Ct. App." if len(geo) <= 4 else f"{geo} Ct. App."
    if re.fullmatch(r"[A-Za-z]{2,5}\.?", raw):
        stem = raw.rstrip(".")
        return f"{stem[0].upper()}{stem[1:].lower()}."
    return raw


def _court_ok(court: str) -> bool:
    compact = re.sub(r"[^a-z0-9]", "", (court or "").lower())
    if not compact or compact in _JUNK_COURTS:
        return False
    if compact in _COURT_ALIASES or compact in _STATE_COURTS:
        return True
    if re.search(r"cir|ctapp|appct|\d+cir|[nscemw]d[a-z]|bankr", compact):
        return True
    return False


def parse_court_year(text: str) -> tuple[str, str] | None:
    """'7th Cir. 2021' or 'N.D. Ind., 2019' → (court, year), or None."""
    cleaned = re.sub(
        r"\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},",
        ",",
        text or "",
        flags=re.I,
    )
    m = _COURT_YEAR_QUERY.match(cleaned)
    if not m:
        return None
    year = m.group("year")
    if not (1789 <= int(year) <= 2100):
        return None
    court = normalize_court(m.group("court"))
    if not court or court.isdigit() or not _court_ok(court):
        return None
    return court, year


def _split_paren(paren: str | None) -> tuple[str, str]:
    if not paren:
        return "", ""
    parsed = parse_court_year(paren)
    if parsed:
        return parsed
    year_m = re.search(r"(\d{4})\s*$", paren.strip())
    year = year_m.group(1) if year_m else ""
    court_part = paren[: year_m.start()].strip(" ,") if year_m else paren
    court = normalize_court(court_part) if court_part and not re.fullmatch(r"\d{4}", court_part.strip()) else ""
    if court == year or not _court_ok(court):
        court = ""
    return court, year


def extract_cites(text: str) -> list[dict]:
    """Reporter and Westlaw cites with optional R12 court/year parentheticals."""
    out: list[dict] = []
    for m in _REPORTER_CITE.finditer(text or ""):
        reporter = m.group("reporter")
        key = reporter_key(reporter, m.group("volume"), m.group("page"))
        if not key:
            continue
        court, year = _split_paren(m.group("paren"))
        slug = key.split("|", 1)[0]
        out.append({
            "kind": "reporter",
            "cite_key": key,
            "volume": m.group("volume"),
            "reporter": _REPORTER_DISPLAY.get(slug, reporter),
            "page": m.group("page"),
            "court": court,
            "year": year,
            "raw": re.sub(r"\s+", " ", m.group(0))[:120],
        })
    for m in _WL.finditer(text or ""):
        key = reporter_key("WL", m.group("year"), m.group("id"))
        if not key:
            continue
        court, year = _split_paren(m.group("paren"))
        out.append({
            "kind": "wl",
            "cite_key": key,
            "volume": m.group("year"),
            "reporter": "WL",
            "page": m.group("id"),
            "court": court,
            "year": year or m.group("year"),
            "raw": re.sub(r"\s+", " ", m.group(0))[:120],
        })
    return out


def extract_parentheticals(text: str) -> list[dict]:
    """Standalone (court year) parentheticals, including those without a reporter."""
    out: list[dict] = []
    for m in _PAREN.finditer(text or ""):
        court = normalize_court(m.group("court"))
        year = m.group("year")
        if not court or not year or not _court_ok(court):
            continue
        slug = re.sub(r"[^a-z0-9]+", "-", court.lower()).strip("-")
        out.append({
            "kind": "paren",
            "cite_key": f"paren|{slug}|{year}",
            "volume": "",
            "reporter": "",
            "page": "",
            "court": court,
            "year": year,
            "raw": re.sub(r"\s+", " ", m.group(0))[:80],
        })
    return out


def normalize_docket(text: str) -> str | None:
    """22A-CT-0925 and No. 22A-CT-925 both become 22A-CT-925."""
    m = _DOCKET.search(text or "")
    if not m:
        return None
    yy, court, kind, seq = m.groups()
    return f"{yy}{court.upper()}-{kind.upper()}-{int(seq)}"


def docket_key(text: str) -> str | None:
    docket = normalize_docket(text)
    return f"docket|{docket}" if docket else None


def parse_reporter_cite(text: str) -> str | None:
    """First Indiana reporter cite in free text → cite_key."""
    m = _REPORTER_CITE.search(text or "")
    if not m:
        return None
    return reporter_key(m.group("reporter"), m.group("volume"), m.group("page"))


def harvard_cap_id_from_filepath(path: str) -> str | None:
    """law.free.cap.ne2d.848/341.8409796.json → 8409796."""
    name = (path or "").strip().partition("/")[2]
    if not name.endswith(".json"):
        return None
    stem = name[:-5]
    if "." not in stem:
        return None
    cap_id = stem.rsplit(".", 1)[-1]
    return cap_id if cap_id.isdigit() else None


def extract_reporter_keys(text: str) -> list[str]:
    """Reporter cite_keys in document order (first page only, not pinpoints)."""
    return [c["cite_key"] for c in extract_cites(text) if c["kind"] == "reporter"]


def extract_docket_keys(text: str) -> list[str]:
    keys = []
    for m in _DOCKET.finditer(text or ""):
        keys.append(f"docket|{m.group(1)}{m.group(2).upper()}-{m.group(3).upper()}-{int(m.group(4))}")
    return keys


def _cluster_cap_ids(clusters_path: str) -> dict[str, str]:
    """Harvard cap_id → CourtListener cluster_id."""
    out: dict[str, str] = {}
    with open(clusters_path, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            row = json.loads(line)
            cap_id = harvard_cap_id_from_filepath(row.get("filepath_json_harvard") or "")
            cid = str(row.get("id") or "")
            if cap_id and cid:
                out[cap_id] = cid
    return out


def _add_cite(rows: list, seen: set, cite_key: str | None, cluster_id: str, kind: str, raw: str) -> None:
    if not cite_key or not cluster_id:
        return
    pair = (cite_key, cluster_id)
    if pair in seen:
        return
    seen.add(pair)
    rows.append((cite_key, cluster_id, kind, (raw or "")[:120]))


def build_case_cite_rows(conn, clusters_path: str, harvard_path: str = "") -> list[tuple]:
    """Identifier rows: reporter keys from Harvard + Rule 22 dockets we already have."""
    known = {r[0] for r in conn.execute("SELECT cluster_id FROM case_cluster")}
    rows: list[tuple] = []
    seen: set[tuple[str, str]] = set()
    cap_to_cluster = _cluster_cap_ids(clusters_path) if clusters_path else {}
    if harvard_path:
        with open(harvard_path, encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                row = json.loads(line)
                cid = cap_to_cluster.get(str(row.get("cap_id") or ""))
                if not cid or cid not in known:
                    continue
                vol = str(row.get("volume") or "")
                page = str(row.get("first_page") or "")
                key = reporter_key(str(row.get("reporter") or ""), vol, page)
                pretty = next(
                    (str(c) for c in (row.get("citations") or []) if parse_reporter_cite(str(c)) == key),
                    f"{vol} {_REPORTER_DISPLAY.get(normalize_reporter(str(row.get('reporter') or '')), row.get('reporter'))} {page}",
                )
                _add_cite(rows, seen, key, cid, "reporter", pretty)
                for cite in row.get("citations") or []:
                    parsed_key = parse_reporter_cite(str(cite))
                    _add_cite(rows, seen, parsed_key, cid, "reporter", str(cite))
                docket = docket_key(str(row.get("docket_number") or ""))
                _add_cite(rows, seen, docket, cid, "docket", str(row.get("docket_number") or ""))
    form_table = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='case_form'"
    ).fetchone()
    if form_table:
        for cluster_id, number in conn.execute(
            "SELECT cluster_id, case_number_in_text FROM case_form "
            "WHERE case_number_in_text IS NOT NULL AND case_number_in_text != ''"
        ):
            if cluster_id in known:
                _add_cite(rows, seen, docket_key(number), cluster_id, "docket", number)
    return rows


def _unique_resolutions(cite_rows: list[tuple]) -> dict[str, str]:
    owners: dict[str, set[str]] = defaultdict(set)
    for cite_key, cluster_id, _kind, _raw in cite_rows:
        owners[cite_key].add(cluster_id)
    return {key: next(iter(ids)) for key, ids in owners.items() if len(ids) == 1}


def ingest_case_citations(conn, clusters_path: str, harvard_path: str = "", batch_size: int = 80) -> dict:
    """Index reporter/docket identifiers, then citing→cited edges. Not treatment."""
    cite_rows = build_case_cite_rows(conn, clusters_path, harvard_path)
    n_cites = store.replace_case_cites(conn, cite_rows)
    unique = _unique_resolutions(cite_rows)
    indexed_keys = {row[0] for row in cite_rows}
    cur = conn.execute(
        "SELECT cluster_id, date_filed, opinion_text FROM case_cluster "
        "WHERE has_opinion_text=1 AND opinion_text IS NOT NULL AND opinion_text != ''"
    )
    edges: dict[tuple[str, str], list] = {}
    outbound: dict[tuple[str, str, str, str], list] = {}
    opinions = 0
    with_cites = 0
    extracted = 0
    resolved = 0
    ambiguous = 0
    unknown = 0
    self_cites = 0
    while True:
        batch = cur.fetchmany(batch_size)
        if not batch:
            break
        for cluster_id, date_filed, text in batch:
            opinions += 1
            cites = extract_cites(text)
            parens = extract_parentheticals(text)
            reporter_keys = [c["cite_key"] for c in cites if c["kind"] == "reporter"]
            docket_keys = extract_docket_keys(text)
            if not cites and not docket_keys and not parens:
                continue
            with_cites += 1
            extracted += len(cites) + len(docket_keys)
            as_of = (date_filed or "")[:10] or None
            for cite in cites + parens:
                slot = outbound.setdefault(
                    (cluster_id, cite["cite_key"], cite["court"], cite["year"]),
                    [0, cite["reporter"], cite["volume"], cite["page"], cite["raw"], as_of],
                )
                slot[0] += 1
            found: dict[str, list[int]] = {}
            for key, bit in ((k, 1) for k in reporter_keys):
                cited = unique.get(key)
                if cited is None:
                    if key in indexed_keys:
                        ambiguous += 1
                    else:
                        unknown += 1
                    continue
                if cited == cluster_id:
                    self_cites += 1
                    continue
                resolved += 1
                slot = found.setdefault(cited, [0, 0])
                slot[0] += 1
                slot[1] |= bit
            for key in docket_keys:
                cited = unique.get(key)
                if cited is None:
                    if key in indexed_keys:
                        ambiguous += 1
                    else:
                        unknown += 1
                    continue
                if cited == cluster_id:
                    self_cites += 1
                    continue
                resolved += 1
                slot = found.setdefault(cited, [0, 0])
                slot[0] += 1
                slot[1] |= 2
            for cited, (count, mask) in found.items():
                kind = {1: "reporter", 2: "docket", 3: "mixed"}[mask]
                edges[(cluster_id, cited)] = [count, kind, as_of]
        if opinions % 2000 == 0:
            print(
                f"case citations: scanned {opinions} opinions, {len(edges)} edges, "
                f"resolved {resolved}",
                flush=True,
            )
    mention_rows = [
        (citing, cited, count, kind, as_of)
        for (citing, cited), (count, kind, as_of) in edges.items()
    ]
    outbound_rows = [
        (citing, key, reporter, volume, page, court, year, raw, count, as_of)
        for (citing, key, court, year), (count, reporter, volume, page, raw, as_of)
        in outbound.items()
    ]
    n_edges = store.replace_case_mentions(conn, mention_rows)
    n_out = store.replace_case_outbound(conn, outbound_rows)
    return {
        "cite_rows": n_cites,
        "unique_cite_keys": len(unique),
        "opinions_scanned": opinions,
        "opinions_with_extracted_cites": with_cites,
        "extracted_cites": extracted,
        "resolved_cites": resolved,
        "ambiguous_cites": ambiguous,
        "unknown_cites": unknown,
        "self_cites": self_cites,
        "mention_pairs": n_edges,
        "outbound_rows": n_out,
    }
