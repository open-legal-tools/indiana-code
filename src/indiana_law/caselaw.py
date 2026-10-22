"""Ingest the already-extracted Indiana CourtListener slice. Unofficial; not legal advice.

The 2026-09-30 opinions CSV was fully scanned (2.1B rows). Only 1,224 rows join to the
120,100 Indiana clusters, and most of those have HTML rather than plain_text. This module
indexes cluster metadata plus any opinion body that can be recovered from HTML/XML fields.
It does not download Harvard JSON or PDFs.
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


def cluster_records(clusters_path: str, opinions: dict[str, dict]):
    with open(clusters_path, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            row = json.loads(line)
            cid = str(row.get("id") or "")
            op = opinions.get(cid, {})
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
                "opinion_text": op.get("text") or "",
                "text_source": op.get("text_source") or "",
                "has_opinion_text": 1 if op.get("text") else 0,
                "search_text": " ".join(
                    x for x in (row.get("case_name") or "", summary, headmatter, op.get("text") or "") if x
                ),
            }
