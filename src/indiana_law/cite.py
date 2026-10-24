"""Open Indiana case citations: parse, format, short forms, permanent ids, and jump-to-paragraph links.

A prototype of the citation scheme in the project's idea log. It follows Indiana Appellate Rule 22:
- memorandum decisions after 2023-01-01: `Steele v. Taber, No. 22A-CT-925 (Ind. Ct. App. Jan. 17, 2023) (mem.)`
- pinpoint with a star page: `Martinez v. State, No. 22A-CR-1196, at *4 (Ind. Ct. App. Jan. 26, 2023) (mem.), trans. denied`
and adds an optional paragraph pinpoint (`¶ 23`, from the bracketed paragraph numbers in Court of Appeals opinions), a
permanent id (`ind:25A-CR-1234:p23`) and a permalink (`/opinions/25A-CR-1234#p23`).

Page numbers mean the slip opinion's own "Page N of M" numbering (the cover page is page 1).
"""
from __future__ import annotations

import datetime as dt
import re
import subprocess
from dataclasses import dataclass, replace
from pathlib import Path

COURTS = {"A": "Ind. Ct. App.", "S": "Ind.", "T": "Ind. Tax Ct."}
MONTHS = {m: i for i, m in enumerate(["Jan.", "Feb.", "Mar.", "Apr.", "May", "June", "July", "Aug.", "Sept.", "Oct.", "Nov.", "Dec."], 1)}
MONTH_LOOKUP = {k.rstrip(".").lower(): v for k, v in MONTHS.items()} | {
    "january": 1, "february": 2, "march": 3, "april": 4, "june": 6, "july": 7, "august": 8, "september": 9, "sept": 9,
    "october": 10, "november": 11, "december": 12, "sep": 9}
MONTH_ABBR = {v: k for k, v in MONTHS.items()}

DOCKET = re.compile(r"\b(\d{2})([AST])-([A-Z]{2})-0*(\d+)\b")


@dataclass(frozen=True)
class Pinpoint:
    kind: str  # "page" or "para"
    start: int
    end: int | None = None

    def __str__(self) -> str:
        rng = f"{self.start}–{self.end}" if self.end and self.end != self.start else f"{self.start}"
        return f"*{rng}" if self.kind == "page" else f"¶ {rng}" if not self.end else f"¶¶ {self.start}–{self.end}"


@dataclass(frozen=True)
class Citation:
    docket: str  # canonical, unpadded: 25A-CR-1234
    name: str | None = None
    date: dt.date | None = None
    mem: bool = False
    pin: Pinpoint | None = None
    history: str | None = None  # e.g. "trans. denied"

    @property
    def court(self) -> str:
        return COURTS[self.docket[2]]

    @property
    def short_name(self) -> str | None:
        if not self.name:
            return None
        first = re.split(r"\s+v\.\s+", self.name)[0].strip()
        return first


def normalize_docket(text: str) -> str:
    """25A-CR-01234 and 25A-CR-1234 both become 25A-CR-1234."""
    m = DOCKET.search(text.strip())
    if not m:
        raise ValueError(f"not an Indiana appellate case number: {text!r}")
    yy, court, kind, seq = m.groups()
    return f"{yy}{court}-{kind}-{int(seq)}"


def _date_text(d: dt.date) -> str:
    return f"{MONTH_ABBR[d.month]} {d.day}, {d.year}"


def format_pin(pin: Pinpoint | None, style: str = "page") -> str:
    return "" if pin is None else str(pin)


def format_full(c: Citation) -> str:
    """Indiana Rule 22 form, with the pinpoint after the case number."""
    out = f"{c.name}, " if c.name else ""
    out += f"No. {c.docket}"
    if c.pin:
        out += f", at {c.pin}" if c.pin.kind == "page" else f", {c.pin}"
    paren = c.court + (f" {_date_text(c.date)}" if c.date else "")
    out += f" ({paren})"
    if c.mem:
        out += " (mem.)"
    if c.history:
        out += f", {c.history}"
    return out


def format_short(c: Citation) -> str:
    """Bluebook-style short form; the case number identifies the case, so it stays."""
    name = c.short_name
    out = f"{name}, " if name else ""
    out += f"No. {c.docket}"
    if c.pin:
        out += f", at {c.pin}" if c.pin.kind == "page" else f", {c.pin}"
    return out


def format_id(pin: Pinpoint) -> str:
    return f"Id. at {pin}" if pin.kind == "page" else f"Id. {pin}"


def machine_id(c: Citation) -> str:
    base = f"ind:{c.docket}"
    if c.pin is None:
        return base
    tag = "p" if c.pin.kind == "para" else "page-"
    return f"{base}:{tag}{c.pin.start}" if c.pin.kind == "para" else f"{base}:page-{c.pin.start}"


def permalink(c: Citation, base: str = "") -> str:
    url = f"{base}/opinions/{c.docket}"
    if c.pin is None:
        return url
    return url + (f"#p{c.pin.start}" if c.pin.kind == "para" else f"#page-{c.pin.start}")


_NAME = r"(?P<name>[A-Z][^,]*?(?:\sv\.\s[^,]+?|\([^)]*\))?)"
_PIN = r"(?:,?\s+(?:at\s+\*(?P<page>\d+)(?:[–-]\*?(?P<page_end>\d+))?|(?:¶¶?|para\.)\s*(?P<para>\d+)(?:\s*[–-]\s*(?P<para_end>\d+))?))"
_PAREN = r"\s*\((?P<court>Ind\. Ct\. App\.|Ind\. Tax Ct\.|Ind\.)(?:\s+(?P<mon>[A-Z][a-z]+\.?)\s+(?P<day>\d{1,2}),\s+(?P<year>\d{4}))?\)"
CITE = re.compile(
    rf"(?:{_NAME},\s+)?No\.\s+(?P<docket>\d{{2}}[AST]-[A-Z]{{2}}-\d+){_PIN}?(?:{_PAREN})?(?P<mem>\s*\(mem\.\))?(?:,\s+(?P<hist>trans\.\s+(?:denied|granted)[^.;]*))?")


def parse(text: str) -> Citation:
    """Parse one citation in full, short or bare form. Raises ValueError if there is no Indiana case number."""
    m = CITE.search(text.strip())
    if not m:
        raise ValueError(f"no Indiana case-number citation in {text!r}")
    g = m.groupdict()
    d = None
    if g["year"]:
        mon = MONTH_LOOKUP.get(g["mon"].rstrip(".").lower())
        if mon is None:
            raise ValueError(f"unknown month {g['mon']!r}")
        d = dt.date(int(g["year"]), mon, int(g["day"]))
    pin = None
    if g["page"]:
        pin = Pinpoint("page", int(g["page"]), int(g["page_end"]) if g["page_end"] else None)
    elif g["para"]:
        pin = Pinpoint("para", int(g["para"]), int(g["para_end"]) if g["para_end"] else None)
    return Citation(docket=normalize_docket(g["docket"]), name=(g["name"] or "").strip() or None, date=d,
                    mem=bool(g["mem"]), pin=pin, history=g["hist"].strip() if g["hist"] else None)


def find_citations(text: str) -> list[Citation]:
    """Every docket-number citation in a longer text (the detector the project needs next to eyecite)."""
    out = []
    for m in CITE.finditer(text):
        try:
            out.append(parse(m.group(0)))
        except ValueError:
            continue
    return out


# ---------------------------------------------------------------- paragraph and page index of an official opinion PDF

PARA = re.compile(r"^\s*\[(\d+)\]\s+(\S.*)$", re.M)
PAGE_OF = re.compile(r"Page\s+(\d+)\s+of\s+(\d+)")


def index_text(pages: list[str]) -> dict:
    """Index pdftotext output split into pages: which page each bracketed paragraph starts on, plus a snippet."""
    paragraphs: dict[int, dict] = {}
    labelled = []
    for number, page in enumerate(pages, 1):
        found = PAGE_OF.findall(page)
        if found:
            labelled.append(number == int(found[-1][0]))
        for m in PARA.finditer(page):
            n = int(m.group(1))
            if n not in paragraphs:  # the first occurrence is the paragraph itself, not a cross-reference
                paragraphs[n] = {"page": number, "snippet": m.group(2).strip()[:140]}
    consecutive = sorted(paragraphs) == list(range(1, len(paragraphs) + 1)) if paragraphs else False
    return {"pages": len(pages), "has_paragraphs": bool(paragraphs), "paragraphs_consecutive": consecutive,
            "page_labels_match_pdf_pages": all(labelled) if labelled else None, "paragraphs": paragraphs}


def index_pdf(path: str | Path) -> dict:
    text = subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True, text=True, check=True).stdout
    pages = text.split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    return index_text(pages)


def jump(c: Citation, official_url: str, index: dict | None) -> dict:
    """Where to send a reader for this pinpoint: the official PDF opened at the right page, with the paragraph's opening words."""
    result = {"docket": c.docket, "official_url": official_url, "page": None, "snippet": None, "url": official_url, "note": None}
    if c.pin is None or index is None:
        return result
    if c.pin.kind == "page":
        page = c.pin.start if 1 <= c.pin.start <= index["pages"] else None
        result["page"] = page
        result["note"] = None if page else f"the opinion has {index['pages']} pages"
    else:
        entry = index["paragraphs"].get(c.pin.start) or index["paragraphs"].get(str(c.pin.start))
        if entry:
            result["page"], result["snippet"] = entry["page"], entry["snippet"]
        else:
            result["note"] = "this opinion has no such numbered paragraph" if index["has_paragraphs"] else "this opinion's paragraphs are not numbered; cite a page instead"
    if result["page"]:
        result["url"] = f"{official_url}#page={result['page']}"
    return result


def to_page_pin(c: Citation, index: dict) -> Citation:
    """Turn a paragraph pinpoint into the page pinpoint Rule 22 asks for (when the paragraph is found)."""
    if c.pin and c.pin.kind == "para":
        entry = index["paragraphs"].get(c.pin.start)
        if entry:
            return replace(c, pin=Pinpoint("page", entry["page"]))
    return c


def paragraph_markers(text: str) -> list[tuple[int, int]]:
    """Bracketed paragraph numbers in an opinion's plain text as (number, offset), keeping only the ascending run 1, 2, 3, ...

    A cross-reference such as "[27]" in the middle of paragraph 2 is not the next paragraph, so it is skipped.
    """
    marks: list[tuple[int, int]] = []
    expected = 1
    for m in re.finditer(r"\[(\d{1,3})\]", text):
        if int(m.group(1)) == expected:
            marks.append((expected, m.start()))
            expected += 1
    return marks
