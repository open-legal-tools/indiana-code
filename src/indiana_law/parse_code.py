"""Parse official Indiana Code HTML (one file per title) into section-version records.

Input is the HTML published by the Indiana General Assembly in its annual "Indiana Code" download.
Output records keep statutory text verbatim apart from whitespace normalization; notes that precede the
statutory text (version notes, recodification citations) are kept apart in `preamble_notes`.
"""
from __future__ import annotations

import json
import os
import re
from html.parser import HTMLParser
from typing import Iterator

from . import PARSER_VERSION

KINDS = ("title", "article", "chapter", "section", "derivation")
HIST = re.compile(r"\b(As added by|Amended by|Formerly|Repealed by|As amended by|Added by)\b")
ACT = re.compile(r"P\.L\.\s*(\d+)-(\d{4})")
IDRE = re.compile(r"(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)(?:-([a-z]))?")
BODY = re.compile(r"^(?:(Effective\s+\d+-\d+-\d{4})\.\s*)?(Sec\.\s*\d[0-9.]*\.?\s.*)$", re.S)


def iso_date(mdy: str) -> str:
    """'7-1-2027' -> '2027-07-01'."""
    m, d, y = mdy.split("-")
    return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"


_D = r"(\d+-\d+-\d{4})"


def dates_from_note(note: str) -> tuple[str | None, str | None]:
    """Effective-from and effective-until (ISO) stated by a version note, or (None, None).

    Handles "This version of section effective until D. See also following version ..., effective D2." (until D),
    "This version of section effective D. See also preceding version ..., effective until D0." (from D), the
    repeal variants, "... amended by P.L.x, SEC.n, effective D." pairs, and a leading "Effective D."
    Revisor's notes that only re-date a section are left alone.
    """
    if note.startswith("Revisor"):
        return None, None
    first, _, rest = note.partition("See also")
    eff_from = eff_until = None
    m = re.search(r"effective until " + _D, first)
    if m:
        eff_until = iso_date(m.group(1))
    else:
        m = re.search(r"effective " + _D, first) or re.match(r"Effective " + _D, first)
        if m:
            eff_from = iso_date(m.group(1))
    if rest:
        m = re.search(r"following (?:version|repeal).*?effective " + _D, rest)
        if m and eff_until is None:
            eff_until = iso_date(m.group(1))
        m = re.search(r"preceding version.*?effective until " + _D, rest)
        if m and eff_from is None:
            eff_from = iso_date(m.group(1))
    return eff_from, eff_until


class _Blocks(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.items: list[dict] = []
        self.cur: dict | None = None
        self.in_p = False
        self.buf: list[str] = []
        self.span_id: str | None = None
        self.sbuf: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "div" and a.get("class") in KINDS:
            self.cur = {"kind": a["class"], "id": a.get("id"), "ic": "", "short": "", "paras": []}
            self.items.append(self.cur)
        elif tag == "span" and a.get("id") in ("ic_number", "shortdescription"):
            self.span_id, self.sbuf = a["id"], []
        elif tag == "p":
            self.in_p, self.buf = True, []

    def handle_endtag(self, tag):
        if tag == "span" and self.span_id and self.cur is not None:
            key = "ic" if self.span_id == "ic_number" else "short"
            self.cur[key] = " ".join("".join(self.sbuf).split())
            self.span_id = None
        elif tag == "p" and self.in_p:
            self.in_p = False
            txt = " ".join("".join(self.buf).split())
            if txt and self.cur is not None:
                self.cur["paras"].append(txt)

    def handle_data(self, data):
        if self.span_id:
            self.sbuf.append(data)
        if self.in_p:
            self.buf.append(data)


def parse_title_html(html: str, source_file: str = "") -> Iterator[dict]:
    """Yield one record per section (including dated versions) found in one title's HTML."""
    p = _Blocks()
    p.feed(html)
    ctx: dict[str, dict] = {}
    for it in p.items:
        if it["kind"] in ("title", "article", "chapter"):
            ctx[it["kind"]] = it
        if it["kind"] != "section":
            continue
        paras = list(it["paras"])
        note = paras.pop() if paras and HIST.search(paras[-1]) else None
        lead: list[str] = []
        body: list[str] = []
        started = False
        for q in paras:
            if not started:
                m = BODY.match(q)
                if m:
                    started = True
                    if m.group(1):
                        lead.append(m.group(1) + ".")
                    body.append(m.group(2))
                else:
                    lead.append(q)
            else:
                body.append(q)
        eff_from = eff_until = None
        for q in lead:
            f, u = dates_from_note(q)
            eff_from = f or eff_from
            eff_until = u or eff_until
        m = IDRE.fullmatch(it["id"] or "")
        heading = it["short"]
        yield {
            "citation": it["ic"],
            "id": it["id"],
            "base_id": "-".join(m.group(i) for i in range(1, 5)) if m else None,
            "version_suffix": m.group(5) if m else None,
            "title_id": ctx.get("title", {}).get("id"),
            "article_id": ctx.get("article", {}).get("id"),
            "chapter_id": ctx.get("chapter", {}).get("id"),
            "title_heading": ctx.get("title", {}).get("short"),
            "article_heading": ctx.get("article", {}).get("short"),
            "chapter_heading": ctx.get("chapter", {}).get("short"),
            "section_heading": heading,
            "preamble_notes": lead,
            "text": "\n".join(body),
            "history_note": note,
            "history_acts": [f"P.L.{a}-{b}" for a, b in ACT.findall(note or "")],
            "effective_from": eff_from,
            "effective_until": eff_until,
            "status": "repealed" if (not body and re.match(r"Repealed", heading or "")) else ("no_body" if not body else "active"),
            "source_file": source_file,
            "unofficial": True,
            "parser_version": PARSER_VERSION,
        }


def parse_snapshot_dir(src_dir: str, snapshot_id: str, zip_sha256: str = "") -> Iterator[dict]:
    """Parse every `<n>.html` title file in a directory extracted from an official ZIP."""
    names = sorted((f for f in os.listdir(src_dir) if re.fullmatch(r"\d+\.html", f)), key=lambda f: int(f.split(".")[0]))
    for fn in names:
        with open(os.path.join(src_dir, fn), "rb") as fh:
            html = fh.read().decode("utf-8", errors="replace")
        for rec in parse_title_html(html, fn):
            rec["snapshot_id"] = snapshot_id
            rec["source_zip_sha256"] = zip_sha256
            yield rec


def write_jsonl(records: Iterator[dict], out_path: str) -> int:
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    n = 0
    with open(out_path, "w", encoding="utf-8") as fo:
        for r in records:
            fo.write(json.dumps(r, ensure_ascii=False) + "\n")
            n += 1
    return n
