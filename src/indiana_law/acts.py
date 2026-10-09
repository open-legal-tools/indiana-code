"""Parse the text of an annual Acts PDF into act-clause records (one per Code target)."""
from __future__ import annotations

import datetime
import re

MONTHS = "JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER"
_CLAUSE = re.compile(r"SECTION (\d+)\.((?:(?!SECTION \d+\.).){0,900}?)\[EFFECTIVE\s+([^\]]+)\]", re.S)
_ICREF = re.compile(r"IC (\d+(?:\.\d+)?(?:-\d+(?:\.\d+)?){1,3})")
_PAGE_HDR = re.compile(r"^\s*(\d+\s+)?P\.L\.\d+[—–]\d{4}(\s+\d+)?\s*$")
_BARE_NUM = re.compile(r"^\s*\d+\s*$")
_LEVELS = {4: "section", 3: "chapter", 2: "article"}


def _effective(raw: str, approved: str | None):
    e = re.sub(r"\s+", " ", raw).strip().upper()
    retro = "RETROACTIVE" in e
    m = re.match(r"(%s) (\d+), (\d{4})" % MONTHS, e)
    if m:
        d = datetime.datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%B %d %Y").strftime("%Y-%m-%d")
        return d, "stated", retro, e
    if e.startswith("UPON PASSAGE"):
        return approved, "upon_passage", retro, e
    return None, "unparsed", retro, e


def _kind(pre: str, refs: list[str]) -> str:
    if re.search(r"(IS|ARE) REPEALED", pre):
        return "repeal"
    if "NEW SECTION" in pre:
        return "add_section"
    if "NEW CHAPTER" in pre:
        return "add_chapter"
    if "NEW ARTICLE" in pre:
        return "add_article"
    if re.search(r"(IS|ARE) AMENDED", pre):
        return "amend"
    return "uncodified" if not refs else "other"


def parse_acts_text(text: str, year: int) -> list[dict]:
    """Return clause records for the given Acts text. `year` is the session year (e.g. 2026)."""
    lines = text.split("\n")
    segs: list[dict] = []
    cur = None
    for i, line in enumerate(lines):
        m = re.match(r"^\s*P\.L\.(\d+)-%d\s*$" % year, line)
        if m:
            hdr = " ".join(lines[i + 1 : i + 3])
            a = re.search(r"\[([HS])\.(\d+)\. Approved (\w+) (\d+), (\d{4})", hdr)
            bill = approved = None
            if a:
                bill = f"{a.group(1)}.{a.group(2)}"
                try:
                    approved = datetime.datetime.strptime(f"{a.group(3)} {a.group(4)} {a.group(5)}", "%B %d %Y").strftime("%Y-%m-%d")
                except ValueError:
                    approved = None
            cur = {"n": int(m.group(1)), "bill": bill, "approved": approved, "lines": []}
            segs.append(cur)
            continue
        if _PAGE_HDR.match(line) or _BARE_NUM.match(line):
            continue
        if cur is not None:
            cur["lines"].append(line)
    out: list[dict] = []
    for s in segs:
        t = re.sub(r"\s+", " ", " ".join(s["lines"]))
        for m in _CLAUSE.finditer(t):
            pre = m.group(2)
            d, basis, retro, raw = _effective(m.group(3), s["approved"])
            refs = _ICREF.findall(pre)
            kind = _kind(pre, refs)
            targets = refs[:1] if kind.startswith("add_") and refs else (refs or [None])
            for ic in targets:
                out.append({
                    "act": f"P.L.{s['n']}-{year}", "act_number": s["n"], "year": year, "bill": s["bill"], "approved": s["approved"],
                    "section_in_act": int(m.group(1)), "kind": kind, "target": ic,
                    "level": None if ic is None else _LEVELS.get(ic.count("-") + 1),
                    "effective_date": d, "effective_basis": basis, "retroactive": retro, "effective_raw": raw[:60],
                })
    return out
