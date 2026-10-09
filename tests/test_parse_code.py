import os
from indiana_law.parse_code import parse_title_html

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "title_sample.html")


def recs():
    with open(FIX, encoding="utf-8") as fh:
        return {r["id"]: r for r in parse_title_html(fh.read(), "2.html")}


def test_hierarchy_and_headings():
    r = recs()["2-5-36-1"]
    assert (r["title_id"], r["article_id"], r["chapter_id"]) == ("2", "2-5", "2-5-36")
    assert r["title_heading"].startswith("TITLE 2")
    assert r["section_heading"] == "Definitions"
    assert r["citation"] == "IC 2-5-36-1"


def test_history_note_split_from_text():
    r = recs()["2-5-36-1"]
    assert r["text"].startswith("Sec. 1. As used in this chapter")
    assert "As added by" not in r["text"]
    assert r["history_acts"] == ["P.L.1-1990", "P.L.10-2024"]


def test_dated_versions_and_dates():
    r = recs()
    a, b = r["2-5-36-9"], r["2-5-36-9-b"]
    assert a["base_id"] == b["base_id"] == "2-5-36-9"
    assert (a["version_suffix"], b["version_suffix"]) == (None, "b")
    assert a["effective_until"] == "2027-07-01" and a["effective_from"] is None
    assert b["effective_from"] == "2027-07-01" and b["effective_until"] is None
    assert a["preamble_notes"][0].startswith("Note: This version")
    assert a["text"] == "Sec. 9. The commission shall meet quarterly."


def test_repealed_decimal_and_preamble():
    r = recs()
    assert r["2-5-36-10"]["status"] == "repealed"
    d = r["2-5-36-11.5"]
    assert d["base_id"] == "2-5-36-11.5" and d["preamble_notes"] == ["[Pre-1986 Recodification Citation: 2-1-1-1 part.]"]
    assert d["text"].startswith("Sec. 11.5.")


def test_effective_prefix_inside_body_paragraph():
    r = recs()["2-5-36-12"]
    assert r["effective_from"] == "2027-07-01"
    assert r["preamble_notes"] == ["Effective 7-1-2027."]
    assert r["text"].startswith("Sec. 12.")


def test_note_date_forms():
    from indiana_law.parse_code import dates_from_note as d
    assert d("Note: This version of section effective until 7-1-2027. See also following version of this section, effective 7-1-2027.") == (None, "2027-07-01")
    assert d("Note: This version of section effective 7-1-2027. See also preceding version of this section, effective until 7-1-2027.") == ("2027-07-01", None)
    assert d("Note: This version of section effective until 7-1-2027. See also following repeal of this section, effective 7-1-2027.") == (None, "2027-07-01")
    assert d("Note: This repeal of section effective 7-1-2027. See also preceding version of this section, effective until 7-1-2027.") == ("2027-07-01", None)
    assert d("Note: This version of section effective until 7-1-2027. See also following repeal of this chapter, effective 7-1-2027.") == (None, "2027-07-01")
    assert d("Note: This version of section amended by P.L.77-2026, SEC.14, effective 3-1-2026. See also following version of this section amended by P.L.157-2026, SEC.12, effective 7-1-2026.") == ("2026-03-01", "2026-07-01")
    assert d("Effective 7-1-2027.") == ("2027-07-01", None)
    assert d("Revisor's Note: The effective date of this section, as amended by P.L.68-2025, was amended by P.L.157-2026, SEC.290 to 7-1-2026.") == (None, None)
