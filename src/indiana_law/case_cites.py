"""Case-to-case citation index. Text matches only; not a citator; not legal advice.

Reporter identifiers come from Harvard CAP metadata (joined by cap id on the
CourtListener filepath). Outbound cites are extracted from opinion bodies with
eyecite when installed, plus a small Indiana-reporter / Rule 22 fallback.
Ambiguous reporter keys (several opinions on one table page) are stored but
not resolved into edges.
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict

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
}

# Harvard slugs and the reporter strings eyecite / opinions actually use.
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
}

# Longer reporter names first so "Ind. App." wins over "Ind.".
_REPORTER_CITE = re.compile(
    r"""
    \b(?P<volume>\d+)\s+
    (?P<reporter>
        N\.?\s*E\.?\s*3d|
        N\.?\s*E\.?\s*2d|
        N\.?\s*E\.|
        Ind\.\s*App\.|
        Ind\.\s*L\.\s*Rep\.|
        Ind\.|
        Blackf(?:ord)?\.?|
        Wilson(?:['’]s)?
    )
    \s+(?P<page>\d+)\b
    """,
    re.I | re.X,
)

_DOCKET = re.compile(r"\b(\d{2})([AST])-([A-Z]{2})-0*(\d+)\b", re.I)

_EYECITE_TYPES = None


def _eyecite_types():
    """Load eyecite once. Missing extra is fine; regex still runs."""
    global _EYECITE_TYPES
    if _EYECITE_TYPES is not None:
        return _EYECITE_TYPES
    try:
        from eyecite import get_citations
        from eyecite.models import FullCaseCitation, ShortCaseCitation
    except ImportError:
        _EYECITE_TYPES = False
        return False
    _EYECITE_TYPES = (get_citations, FullCaseCitation, ShortCaseCitation)
    return _EYECITE_TYPES


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


def extract_reporter_keys(text: str, use_eyecite: bool = False) -> list[str]:
    """Reporter cite_keys in document order. Regex is the ingest path; eyecite is opt-in."""
    keys = []
    for m in _REPORTER_CITE.finditer(text or ""):
        key = reporter_key(m.group("reporter"), m.group("volume"), m.group("page"))
        if key:
            keys.append(key)
    if not use_eyecite:
        return keys
    have = set(keys)
    loaded = _eyecite_types()
    if not loaded:
        return keys
    get_citations, FullCaseCitation, ShortCaseCitation = loaded
    try:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            found = get_citations(text or "")
    except Exception:
        return keys
    for cite in found:
        if not isinstance(cite, (FullCaseCitation, ShortCaseCitation)):
            continue
        groups = cite.groups or {}
        reporter = ""
        try:
            reporter = cite.corrected_reporter() or ""
        except Exception:
            reporter = ""
        reporter = reporter or groups.get("reporter") or ""
        key = reporter_key(reporter, groups.get("volume"), groups.get("page"))
        if key and key not in have:
            keys.append(key)
            have.add(key)
    return keys


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


def ingest_case_citations(
    conn, clusters_path: str, harvard_path: str = "", batch_size: int = 80, use_eyecite: bool = False
) -> dict:
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
            reporter_keys = extract_reporter_keys(text, use_eyecite=use_eyecite)
            docket_keys = extract_docket_keys(text)
            if not reporter_keys and not docket_keys:
                continue
            with_cites += 1
            extracted += len(reporter_keys) + len(docket_keys)
            as_of = (date_filed or "")[:10] or None
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
    n_edges = store.replace_case_mentions(conn, mention_rows)
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
        "used_eyecite": bool(use_eyecite and _eyecite_types()),
    }
