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


_ABBREV_KEYS = {
    "ne", "ne2d", "ne3d", "ic", "id", "ind", "no", "nos", "app", "ct", "jr", "sr",
    "mr", "mrs", "ms", "dr", "inc", "co", "corp", "vol", "jan", "feb", "mar", "apr",
    "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec", "us", "sct", "ie", "eg",
    "cf", "fig", "ed", "rev", "cert", "supp", "stat", "ann", "gen", "prof", "al",
    "art", "ch", "sec", "para", "dept", "gov", "sen", "rep", "op", "mem", "super",
    "dist", "div", "ltd", "llc", "pc", "vs", "vs", "f", "f2d", "f3d", "f4th",
}
_CONSTRUE_SIGNAL = re.compile(
    r"\b(?:constru(?:e|es|ed|ing|al)|construction|interpret\w*|unambiguous|ambiguous|plain meaning|plain language)\b",
    re.I,
)
_APPLY_SIGNAL = re.compile(
    r"(?:\b(?:statute|section|subsection|code)\b[^.]{0,60}\bappl\w+\b|"
    r"\bappl\w+\b[^.]{0,60}\b(?:statute|section|subsection|ind(?:iana)?\.?\s*code|i\.?\s*c\.?)\b|"
    r"\bin violation of\b)",
    re.I,
)


def _sentence_boundary(text: str, dot: int) -> bool:
    """True when this period ends a sentence rather than an abbreviation or reporter."""
    i = dot - 1
    chars: list[str] = []
    while i >= 0 and (text[i].isalpha() or text[i] == "."):
        chars.append(text[i])
        i -= 1
    key = "".join(reversed(chars)).replace(".", "").lower()
    if key and (len(key) == 1 or key in _ABBREV_KEYS):
        return False
    j = dot + 1
    while j < len(text) and text[j] in " \t\"'”’)]":
        j += 1
    if j >= len(text):
        return True
    return text[j].isupper() or text[j] == "["


def _sentence_bounds(text: str, start: int, end: int) -> tuple[int, int]:
    left = start
    while left > 0 and start - left < 600:
        if text[left - 1] == "." and _sentence_boundary(text, left - 1):
            break
        left -= 1
    right = end
    limit = min(len(text), end + 600)
    while right < limit:
        if text[right] == "." and _sentence_boundary(text, right):
            right += 1
            break
        right += 1
    return left, right


def _apply_signal(sentence: str) -> bool:
    """An application phrase that is not negated ('not applicable', 'inapplicable')."""
    for match in _APPLY_SIGNAL.finditer(sentence):
        appl = re.search(r"\bappl\w+\b", match.group(0), re.I)
        if appl:
            at = match.start() + appl.start()
            prefix = sentence[max(0, at - 24):at].lower()
            if sentence[at:at + 6].lower() == "inappl":
                continue
            if re.search(r"\bnot\s+$", prefix):
                continue
        return True
    return False


def _signal_relations(sentence: str) -> list[str]:
    relations = []
    if _CONSTRUE_SIGNAL.search(sentence):
        relations.append("construes")
    if _apply_signal(sentence):
        relations.append("applies")
    return relations


def _previous_sentence(text: str, left: int) -> tuple[int, int] | None:
    """The sentence that ended just before `left`, when `left` starts a new sentence."""
    i = left - 1
    while i >= 0 and text[i] in " \t\n":
        i -= 1
    if i < 0 or text[i] != ".":
        return None
    prev_left, prev_right = _sentence_bounds(text, max(0, i - 1), i)
    prev_right = min(prev_right, left)
    if prev_right <= prev_left:
        return None
    return prev_left, prev_right


def classify_statute_signals(text: str) -> list[dict]:
    """Construction or application words in the citation sentence, or in the sentence the citation supports.

    A citation that sits in its own short sentence can borrow the previous sentence. The following
    sentence is not borrowed. Not a holding and not a model judgment.
    """
    from .asof import _STATUTE_CITE

    if not (text or "").strip():
        return []
    found: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for match in _STATUTE_CITE.finditer(text):
        section_id = "-".join(match.groups())
        left, right = _sentence_bounds(text, match.start(), match.end())
        if right - left > 700:
            left = max(0, match.start() - 240)
            right = min(len(text), match.end() + 240)
        sentence = text[left:right]
        relations = _signal_relations(sentence)
        if not relations and len(sentence) <= 220:
            previous = _previous_sentence(text, left)
            if previous:
                prev_left, prev_right = previous
                prev = text[prev_left:prev_right]
                relations = _signal_relations(prev)
                if relations:
                    left = prev_left
                    sentence = text[left:right]
        for relation in relations:
            key = (section_id, relation)
            if key in seen:
                continue
            seen.add(key)
            found.append({
                "section_id": section_id,
                "relation": relation,
                "quote": sentence,
                "quote_start": left,
                "quote_end": right,
                "status": "rule_unreviewed",
            })
    found.sort(key=lambda row: (row["quote_start"], row["section_id"], row["relation"]))
    return found


def ingest_statute_signals(conn, batch_size: int = 40) -> dict:
    """Index same-sentence statute signals. Status stays rule_unreviewed. Not a citator."""
    from . import store

    cur = conn.execute(
        "SELECT cluster_id, opinion_text FROM case_cluster "
        "WHERE has_opinion_text=1 AND opinion_text IS NOT NULL AND opinion_text != ''"
    )
    rows_out: list[tuple] = []
    counts = {"construes": 0, "applies": 0}
    opinions = 0
    with_any = 0
    while True:
        batch = cur.fetchmany(batch_size)
        if not batch:
            break
        for cluster_id, text in batch:
            opinions += 1
            hits = classify_statute_signals(text or "")
            if hits:
                with_any += 1
            for hit in hits:
                counts[hit["relation"]] = counts.get(hit["relation"], 0) + 1
                rows_out.append((
                    cluster_id,
                    hit["section_id"],
                    hit["relation"],
                    hit["quote"],
                    hit["quote_start"],
                    hit["quote_end"],
                    hit["status"],
                ))
        if opinions % 10000 == 0:
            print(f"statute signals: scanned {opinions} opinions, {len(rows_out)} rows", flush=True)
    stored = store.replace_statute_signals(conn, rows_out)
    return {
        "opinions_scanned": opinions,
        "opinions_with_signals": with_any,
        "rows": stored,
        "counts": counts,
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


_FOOTER = re.compile(
    r"(?:Court of Appeals of Indiana|Indiana Supreme Court|Indiana Tax Court)\s*\|[^|]{0,160}",
    re.I,
)
_CLOSING = re.compile(
    r"(?:\[\d+\]\s*)?"
    r"(?P<body>"
    r"(?:Affirmed|Reversed|Remanded|Vacated|Dismissed)"
    r"(?:\s+in\s+part)?"
    r"(?:(?:\s*,\s*and|\s*,|\s+and)\s+"
    r"(?:affirmed|reversed|remanded|vacated|dismissed)(?:\s+in\s+part)?)*"
    r"(?:\s+with\s+instructions)?"
    r")\s*\.",
    re.I,
)
_PROSE = re.compile(
    r"(?P<body>"
    r"(?:Accordingly,\s+we|Therefore,\s+we|Thus,\s+we|For the foregoing reasons,\s+we|We therefore|We)"
    r"\s+[^.]{0,200})"
    r"\.",
    re.I,
)
_PROSE_REJECT = re.compile(r"\b(?:do not|don't|cannot|can't|decline to)\b", re.I)
_LABEL_WORD = re.compile(r"affirm\w*|revers\w*|remand\w*|vacat\w*|dismiss\w*", re.I)
_DISP_STEMS = (
    ("affirm", "affirmed"),
    ("revers", "reversed"),
    ("remand", "remanded"),
    ("vacat", "vacated"),
    ("dismiss", "dismissed"),
)


def _labels_in(body: str) -> list[str]:
    labels: list[str] = []
    for match in _LABEL_WORD.finditer(body):
        word = match.group(0).lower()
        for stem, label in _DISP_STEMS:
            if word.startswith(stem) and label not in labels:
                labels.append(label)
                break
    return labels


def _quote_in(window: str, body: str):
    parts = [re.escape(part) for part in re.split(r"\s+", body.strip()) if part]
    if not parts:
        return None
    pattern = re.compile(r"\s+".join(parts))
    found = None
    for match in pattern.finditer(window):
        found = match
    return found


def classify_disposition(text: str) -> dict:
    """Read the closing disposition line. A rule over the slip text, not an official judgment."""
    empty = {
        "disposition": "unlabeled",
        "labels": [],
        "in_part": False,
        "method": "none",
        "quote": None,
        "quote_start": None,
        "quote_end": None,
    }
    if not (text or "").strip():
        empty["method"] = "no_text"
        return empty
    window_start = max(0, len(text) - 4000)
    window = text[window_start:]
    stripped = _FOOTER.sub(" ", window)
    zone_start = max(0, len(stripped) - 1800)

    def last_body(pattern, method: str, max_len: int) -> str | None:
        chosen = None
        for match in pattern.finditer(stripped):
            if match.start() < zone_start:
                continue
            body = re.sub(r"\s+", " ", match.group("body")).strip(" \t.")
            if not body or len(body) > max_len:
                continue
            if method == "prose":
                if _PROSE_REJECT.search(body) or not _labels_in(body):
                    continue
            chosen = body
        return chosen

    body = last_body(_CLOSING, "closing_line", 180)
    method = "closing_line" if body else None
    if body is None:
        body = last_body(_PROSE, "prose", 220)
        method = "prose" if body else None
    if not body:
        return empty
    labels = _labels_in(body)
    if not labels:
        return empty
    found = _quote_in(window, body)
    if found is None:
        return empty
    quote = window[found.start():found.end()]
    if len(labels) == 1:
        disposition = labels[0]
    else:
        disposition = "mixed"
    return {
        "disposition": disposition,
        "labels": labels,
        "in_part": "in part" in body.lower(),
        "method": method,
        "quote": quote,
        "quote_start": window_start + found.start(),
        "quote_end": window_start + found.end(),
    }


_STANDARD_PATTERNS = (
    ("de_novo", re.compile(
        r"(?:our review is de novo|reviewed de novo|"
        r"reviews?[^.]{0,70}\bde novo\b|"
        r"de novo standard(?: of review)?|"
        r"standard of review[^.]{0,50}\bde novo\b)",
        re.I,
    )),
    ("abuse_of_discretion", re.compile(
        r"(?:reviewed for (?:an )?abuse of discretion|"
        r"reviews?[^.]{0,90}\bfor (?:an )?abuse of discretion|"
        r"abuse of discretion standard(?: of review)?|"
        r"standard of review[^.]{0,60}abuse of discretion)",
        re.I,
    )),
    ("clearly_erroneous", re.compile(
        r"(?:clearly erroneous standard(?: of review)?|"
        r"reviewed for clear error|"
        r"reviews?[^.]{0,40}\bfor clear error\b|"
        r"standard of review[^.]{0,50}clearly erroneous|"
        r"set aside[^.]{0,90}clearly erroneous)",
        re.I,
    )),
    ("sufficiency", re.compile(r"we neither reweigh the evidence nor judge", re.I)),
    ("prima_facie_error", re.compile(r"prima facie error", re.I)),
    ("arbitrary_or_capricious", re.compile(
        r"(?:arbitrary (?:and|or) capricious standard|"
        r"standard of review[^.]{0,80}arbitrary (?:and|or) capricious)",
        re.I,
    )),
    ("substantial_evidence", re.compile(
        r"(?:substantial[- ]evidence standard|"
        r"standard of review[^.]{0,60}substantial evidence)",
        re.I,
    )),
)
_STANDARD_ARGUMENT = re.compile(r"\b(?:argues|contends|asserts|claims)\b", re.I)
_PRIMA_FACIE_NEAR = ("standard", "appellee", "reverse", "brief")


def _standard_quote(text: str, start: int, end: int) -> tuple[str, int, int]:
    """A short window around the match, snapped out to word boundaries."""
    left = max(0, start - 110)
    right = min(len(text), end + 90)
    if left > 0 and text[left - 1] not in " \n":
        space = text.rfind(" ", 0, left)
        if space != -1:
            left = space + 1
    if right < len(text) and text[right:right + 1] not in " \n":
        space = text.find(" ", right)
        if space != -1 and space - left <= 360:
            right = space
    if right - left > 360:
        left = max(0, start - 80)
        right = min(len(text), end + 80)
    return text[left:right], left, right


def classify_standards(text: str) -> list[dict]:
    """Sentences that state a standard of review. A rule over the slip text, not a ruling."""
    if not (text or "").strip():
        return []
    found: list[dict] = []
    seen: set[str] = set()
    for label, pattern in _STANDARD_PATTERNS:
        for match in pattern.finditer(text):
            if label in seen:
                break
            before = text[max(0, match.start() - 60):match.start()]
            if _STANDARD_ARGUMENT.search(before):
                continue
            if label == "prima_facie_error":
                window = text[max(0, match.start() - 120):match.end() + 80].lower()
                if not any(word in window for word in _PRIMA_FACIE_NEAR):
                    continue
            quote, start, end = _standard_quote(text, match.start(), match.end())
            if not quote.strip():
                continue
            seen.add(label)
            found.append({
                "label": label,
                "quote": quote,
                "quote_start": start,
                "quote_end": end,
            })
            break
    found.sort(key=lambda row: row["quote_start"])
    return found


def ingest_standards(conn, batch_size: int = 40) -> dict:
    """Index stated standards of review. Not a ruling on which standard governs."""
    from . import store

    cur = conn.execute(
        "SELECT cluster_id, opinion_text FROM case_cluster "
        "WHERE has_opinion_text=1 AND opinion_text IS NOT NULL AND opinion_text != ''"
    )
    rows_out: list[tuple] = []
    counts: dict[str, int] = {}
    opinions = 0
    with_any = 0
    while True:
        batch = cur.fetchmany(batch_size)
        if not batch:
            break
        for cluster_id, text in batch:
            opinions += 1
            hits = classify_standards(text or "")
            if hits:
                with_any += 1
            for hit in hits:
                counts[hit["label"]] = counts.get(hit["label"], 0) + 1
                rows_out.append((
                    cluster_id,
                    hit["label"],
                    hit["quote"],
                    hit["quote_start"],
                    hit["quote_end"],
                ))
        if opinions % 10000 == 0:
            print(f"standards: scanned {opinions} opinions, {len(rows_out)} rows", flush=True)
    stored = store.replace_standards(conn, rows_out)
    return {
        "opinions_scanned": opinions,
        "opinions_with_standards": with_any,
        "rows": stored,
        "counts": counts,
    }


_WITH_SEPARATE = re.compile(r"\bwith(?: a)? separate opinion\b", re.I)


def _vote_edge(text: str, dot: int) -> bool:
    """True when this period or newline ends the vote line, rather than 'J.' or 'C.J.'."""
    if text[dot] == "\n":
        return True
    if text[dot] != ".":
        return False
    k = dot - 1
    while k >= 0 and text[k].isalpha():
        k -= 1
    token = text[k + 1:dot]
    return not (len(token) == 1 or token.lower() in {"jr", "sr", "dr"})


def _vote_before(text: str, at: int) -> tuple[int, str]:
    start = max(0, at - 160)
    i = at
    while i > start:
        i -= 1
        if _vote_edge(text, i):
            start = i + 1
            break
    return start, text[start:at]


def _vote_after(text: str, at: int) -> tuple[int, str]:
    end = min(len(text), at + 140)
    i = at
    while i < end:
        if _vote_edge(text, i):
            end = i + 1
            break
        i += 1
    return end, text[at:end]


def _separate_labels(before: str, after: str) -> list[str]:
    """Vote words in the slip's own 'with separate opinion' line. Not another case's writing."""
    labels: list[str] = []
    if re.search(r"\bdissents?\b", before, re.I) and re.search(r"denial of transfer", before, re.I):
        labels.append("transfer_dissent")
    elif re.search(r"\bdissents?\s+in\s+part\b", before, re.I):
        labels.append("dissents_in_part")
    elif re.search(r"\bdissents?\b", before, re.I):
        labels.append("dissents")
    if re.search(r"\bconcurs?\s+in\s+result\b", before, re.I):
        labels.append("concurs_in_result")
    elif re.search(r"\bconcurs?\s+in\s+part\b", before, re.I):
        labels.append("concurs_in_part")
    elif re.search(r"\bconcurs?\b", before, re.I):
        labels.append("concurs")
    if re.search(r"\bin which\b", after, re.I) and re.search(r"\b(?:concurs?|joins?)\b", after, re.I):
        labels.append("joins")
    return labels


def classify_separate_writings(text: str) -> list[dict]:
    """The slip's own vote line that says someone concurs or dissents with a separate opinion.

    Narrative about another case's separate opinion is not a hit. 'Without separate opinion' is not a hit.
    """
    if not (text or "").strip() or "separate opinion" not in text.lower():
        return []
    found: list[dict] = []
    seen: set[str] = set()
    for match in _WITH_SEPARATE.finditer(text):
        start, before = _vote_before(text, match.start())
        end, after = _vote_after(text, match.end())
        labels = _separate_labels(before, after)
        if not labels:
            continue
        quote = text[start:end]
        for label in labels:
            if label in seen:
                continue
            seen.add(label)
            found.append({
                "label": label,
                "quote": quote,
                "quote_start": start,
                "quote_end": end,
            })
    found.sort(key=lambda row: (row["quote_start"], row["label"]))
    return found


def ingest_separate_writings(conn, batch_size: int = 80) -> dict:
    """Index slip vote lines that announce a separate opinion. Not a holding."""
    from . import store

    cur = conn.execute(
        "SELECT cluster_id, opinion_text FROM case_cluster "
        "WHERE has_opinion_text=1 AND opinion_text IS NOT NULL AND opinion_text != ''"
    )
    rows_out: list[tuple] = []
    counts: dict[str, int] = {}
    opinions = 0
    with_any = 0
    while True:
        batch = cur.fetchmany(batch_size)
        if not batch:
            break
        for cluster_id, text in batch:
            opinions += 1
            hits = classify_separate_writings(text or "")
            if hits:
                with_any += 1
            for hit in hits:
                counts[hit["label"]] = counts.get(hit["label"], 0) + 1
                rows_out.append((
                    cluster_id,
                    hit["label"],
                    hit["quote"],
                    hit["quote_start"],
                    hit["quote_end"],
                ))
        if opinions % 20000 == 0:
            print(f"separate writings: scanned {opinions} opinions, {len(rows_out)} rows", flush=True)
    stored = store.replace_separate_writings(conn, rows_out)
    return {
        "opinions_scanned": opinions,
        "opinions_with_separate": with_any,
        "rows": stored,
        "counts": counts,
    }


def ingest_dispositions(conn, batch_size: int = 200) -> dict:
    """Index closing-line dispositions. Not an official judgment and not treatment."""
    from . import store

    cur = conn.execute(
        "SELECT cluster_id, "
        "CASE WHEN has_opinion_text=1 AND opinion_text IS NOT NULL "
        "THEN substr(opinion_text, max(1, length(opinion_text) - 3999)) ELSE '' END, "
        "CASE WHEN has_opinion_text=1 AND opinion_text IS NOT NULL "
        "THEN length(opinion_text) ELSE 0 END "
        "FROM case_cluster"
    )
    rows_out: list[tuple] = []
    counts: dict[str, int] = {}
    labeled = 0
    n = 0
    while True:
        batch = cur.fetchmany(batch_size)
        if not batch:
            break
        for cluster_id, tail, full_len in batch:
            n += 1
            classified = classify_disposition(tail or "")
            counts[classified["disposition"]] = counts.get(classified["disposition"], 0) + 1
            if classified["disposition"] != "unlabeled":
                labeled += 1
            prefix = max(0, int(full_len or 0) - len(tail or ""))
            start = classified["quote_start"]
            end = classified["quote_end"]
            rows_out.append((
                cluster_id,
                classified["disposition"],
                ",".join(classified["labels"]),
                1 if classified["in_part"] else 0,
                classified["method"],
                classified["quote"],
                None if start is None else prefix + start,
                None if end is None else prefix + end,
            ))
        if n % 10000 == 0:
            print(f"dispositions: scanned {n}", flush=True)
    stored = store.replace_dispositions(conn, rows_out)
    return {"clusters": stored, "counts": counts, "labeled": labeled}


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
