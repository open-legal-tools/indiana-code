"""Ingest the already-extracted Indiana CourtListener slice. Unofficial; not legal advice.

The 2026-09-30 opinions CSV was fully scanned (2.1B rows). Only 1,224 rows join to the
120,100 Indiana clusters, and most of those have HTML rather than plain_text. This module
indexes cluster metadata plus any opinion body that can be recovered from HTML/XML fields
or from extracted Harvard CAP JSON (static.case.law volume zips).
"""
from __future__ import annotations

import gzip
import html
import json
import re
from html.parser import HTMLParser


COURTS = {
    "ind": "Indiana Supreme Court",
    "indctapp": "Indiana Court of Appeals",
    "indtc": "Indiana Tax Court",
}

SOURCE = "https://www.courtlistener.com/"
MEMO_PERSUASIVE_FROM = "2023-01-01"  # App. R. 65(D); memos on or after this date may be cited for persuasive value

_MEMO_HEADING = re.compile(r"MEMORANDUM\s+DECISION", re.I)
_MEMO_65D = re.compile(
    r"this\s+Memorandum\s+Decision\s+is\s+not\s+binding|"
    r"shall\s+not\s+be\s+regarded\s+as\s+precedent|"
    r"cited\s+only\s+for\s+persuasive\s+value",
    re.I,
)
_RULE_65E = re.compile(r"Appellate Rule 65\(E\)", re.I)
_FOR_PUBLICATION = re.compile(r"(?<!NOT )FOR\s+PUBLICATION", re.I)
_NOT_FOR_PUBLICATION = re.compile(r"NOT\s+FOR\s+PUBLICATION", re.I)
_CASE_NO = re.compile(
    r"Case\s+No\.?\s*("
    r"\d{2}[AST]-[A-Z]{2}-\d+|"
    r"\d{2}[AST]\d{2}-\d{4}-[A-Z]{2}-\d+"
    r")",
    re.I,
)


def classify_decision_form(text: str) -> dict:
    """Label memorandum vs opinion from slip-opinion wording. Text classification only."""
    if not (text or "").strip():
        return {"decision_form": "no_text", "signals": [], "case_number_in_text": None}
    head = text[:3000]
    foot = text[-1500:]
    signals = []
    if _MEMO_HEADING.search(head):
        signals.append("memorandum_decision_heading")
    if _MEMO_65D.search(head):
        signals.append("rule_65d_memorandum")
    if _NOT_FOR_PUBLICATION.search(head):
        signals.append("not_for_publication")
    if _FOR_PUBLICATION.search(head):
        signals.append("for_publication")
    if _RULE_65E.search(head):
        signals.append("rule_65e_banner")
    memo = bool({"memorandum_decision_heading", "rule_65d_memorandum", "not_for_publication"} & set(signals))
    opin = bool({"for_publication", "rule_65e_banner"} & set(signals)) and not memo
    if memo:
        form = "memorandum"
    elif opin:
        form = "opinion"
    else:
        form = "unlabeled"
    found = _CASE_NO.search(head) or _CASE_NO.search(foot)
    return {
        "decision_form": form,
        "signals": signals,
        "case_number_in_text": found.group(1) if found else None,
    }


def citability_for(decision_form: str, date_filed: str | None) -> str:
    """Derived from decision_form and App. R. 65(D). Not an official citability ruling."""
    if decision_form == "opinion":
        return "precedent"
    if decision_form == "memorandum":
        if (date_filed or "") >= MEMO_PERSUASIVE_FROM:
            return "persuasive"
        return "limited"
    return "unknown"


def _disagrees_with_source(form: str, precedential_status: str | None) -> bool:
    status = (precedential_status or "").lower()
    if form == "memorandum" and status == "published":
        return True
    if form == "opinion" and status == "unpublished":
        return True
    return False


class _HTMLText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data:
            self.parts.append(data)


def html_to_text(raw: str) -> str:
    if not raw:
        return ""
    parser = _HTMLText()
    try:
        parser.feed(raw)
        parser.close()
    except Exception:
        return html.unescape(re.sub(r"<[^>]+>", " ", raw))
    return html.unescape(re.sub(r"\s+", " ", " ".join(parser.parts))).strip()


def opinion_text(row: dict) -> tuple[str, str]:
    """Return (text, source_field) preferring plain_text, then HTML/XML fields."""
    pt = (row.get("plain_text") or "").strip()
    if pt:
        return pt, "plain_text"
    for key in ("html_with_citations", "xml_harvard", "html", "html_lawbox", "html_columbia"):
        raw = (row.get(key) or "").strip()
        if raw:
            text = html_to_text(raw)
            if text:
                return text, key
    return "", ""


def load_opinions(path: str) -> dict[str, dict]:
    by_cluster: dict[str, dict] = {}
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            row = json.loads(line)
            text, source = opinion_text(row)
            cluster_id = str(row.get("cluster_id") or "")
            if not cluster_id:
                continue
            rec = {
                "opinion_id": str(row.get("id") or ""),
                "cluster_id": cluster_id,
                "type": row.get("type") or "",
                "text": text,
                "text_source": source,
            }
            prev = by_cluster.get(cluster_id)
            if prev is None or len(text) > len(prev["text"]):
                by_cluster[cluster_id] = rec
    return by_cluster


def _as_int(value, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def harvard_key(reporter: str, volume: str, first_page: str) -> str:
    return f"{reporter}|{volume}|{first_page}"


def parse_harvard_filepath(path: str) -> tuple[str, str, str] | None:
    """law.free.cap.ne2d.848/341.8409796.json -> (ne2d, 848, 341)."""
    path = (path or "").strip()
    if not path.startswith("law.free.cap."):
        return None
    prefix, _, name = path.partition("/")
    rest = prefix[len("law.free.cap."):]
    if "." not in rest:
        return None
    reporter, volume = rest.rsplit(".", 1)
    first_page = name.split(".", 1)[0] if name else ""
    if not reporter or not volume.isdigit() or not first_page:
        return None
    return reporter, volume, first_page


def load_harvard(path: str) -> dict[str, dict]:
    """Index extracted CAP JSONL by reporter|volume|first_page."""
    by_key: dict[str, dict] = {}
    if not path:
        return by_key
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            row = json.loads(line)
            key = harvard_key(str(row.get("reporter") or ""), str(row.get("volume") or ""), str(row.get("first_page") or ""))
            if not key.endswith("|") and (not by_key.get(key) or len(row.get("text") or "") > len(by_key[key].get("text") or "")):
                by_key[key] = row
    return by_key


def cluster_records(clusters_path: str, opinions: dict[str, dict], harvard: dict[str, dict] | None = None):
    harvard = harvard or {}
    with open(clusters_path, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            row = json.loads(line)
            cid = str(row.get("id") or "")
            op = opinions.get(cid, {})
            text = op.get("text") or ""
            source = op.get("text_source") or ""
            parsed = parse_harvard_filepath(row.get("filepath_json_harvard") or "")
            if parsed and not text:
                hv = harvard.get(harvard_key(*parsed))
                if hv and hv.get("text"):
                    text = hv["text"]
                    source = "harvard_cap"
            summary = (row.get("summary") or "").strip()
            headmatter = (row.get("headmatter") or "").strip()
            court_id = row.get("court_id") or ""
            if court_id not in COURTS:
                court_id = ""
            yield {
                "cluster_id": cid,
                "court_id": court_id,
                "court": COURTS.get(court_id, ""),
                "case_name": row.get("case_name") or "",
                "date_filed": (row.get("date_filed") or "")[:10] if re.match(r"\d{4}-\d{2}-\d{2}", (row.get("date_filed") or "")) else "",
                "docket_id": str(row.get("docket_id") or ""),
                "precedential_status": (row.get("precedential_status") or "")[:40],
                "slug": row.get("slug") or "",
                "citation_count": _as_int(row.get("citation_count")),
                "summary": summary,
                "headmatter": headmatter,
                "opinion_id": op.get("opinion_id") or "",
                "opinion_text": text,
                "text_source": source,
                "has_opinion_text": 1 if text else 0,
                "search_text": " ".join(
                    x for x in (row.get("case_name") or "", summary, headmatter, text) if x
                ),
            }


def ingest_statute_mentions(conn, batch_size: int = 200) -> dict:
    """Scan opinion bodies for IC / Ind. Code citations. Text mentions only; not treatment."""
    from collections import Counter

    from . import asof, store

    known = {r[0] for r in conn.execute("SELECT DISTINCT base_id FROM section_version")}
    years = [r[0] for r in conn.execute("SELECT year FROM snapshot ORDER BY year")]
    first_year = years[0] if years else None
    cur = conn.execute(
        "SELECT cluster_id, date_filed, opinion_text FROM case_cluster "
        "WHERE has_opinion_text=1 AND opinion_text IS NOT NULL AND opinion_text != ''"
    )
    rows_out: list[tuple] = []
    opinions = 0
    with_mentions = 0
    while True:
        batch = cur.fetchmany(batch_size)
        if not batch:
            break
        for cluster_id, date_filed, text in batch:
            opinions += 1
            ids = asof.extract_statute_citations(text)
            if not ids:
                continue
            with_mentions += 1
            as_of = (date_filed or "")[:10]
            year = int(as_of[:4]) if len(as_of) >= 4 and as_of[:4].isdigit() else None
            resolved_ok = bool(known and first_year and year and year >= first_year)
            for sid, cnt in Counter(ids).items():
                rows_out.append((cluster_id, sid, cnt, as_of or None, 1 if resolved_ok and sid in known else 0))
        if opinions % 5000 == 0:
            print(f"statute mentions: scanned {opinions} opinions, {len(rows_out)} pairs", flush=True)
    n = store.replace_statute_mentions(conn, rows_out)
    return {
        "opinions_scanned": opinions,
        "opinions_with_mentions": with_mentions,
        "mention_pairs": n,
    }


def ingest_decision_forms(conn, batch_size: int = 200) -> dict:
    """Classify memorandum vs opinion from opinion_text. Not official publication status."""
    from . import store

    cur = conn.execute(
        "SELECT cluster_id, date_filed, precedential_status, opinion_text, has_opinion_text "
        "FROM case_cluster"
    )
    rows_out: list[tuple] = []
    counts = {"memorandum": 0, "opinion": 0, "both": 0, "unlabeled": 0, "no_text": 0}
    disagree = 0
    n = 0
    while True:
        batch = cur.fetchmany(batch_size)
        if not batch:
            break
        for cluster_id, date_filed, status, text, has_text in batch:
            n += 1
            classified = classify_decision_form(text if has_text else "")
            form = classified["decision_form"]
            counts[form] = counts.get(form, 0) + 1
            disagrees = 1 if _disagrees_with_source(form, status) else 0
            disagree += disagrees
            rows_out.append((
                cluster_id,
                form,
                citability_for(form, date_filed),
                classified["case_number_in_text"],
                disagrees,
            ))
        if n % 10000 == 0:
            print(f"decision forms: scanned {n}", flush=True)
    stored = store.replace_case_forms(conn, rows_out)
    return {"clusters": stored, "counts": counts, "disagrees_with_source": disagree}
