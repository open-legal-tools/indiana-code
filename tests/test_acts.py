import os
from indiana_law.acts import parse_acts_text

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "acts_sample.txt")


def clauses():
    with open(FIX, encoding="utf-8") as fh:
        return parse_acts_text(fh.read(), 2026)


def test_acts_and_approval():
    c = clauses()
    assert {x["act"] for x in c} == {"P.L.20-2026", "P.L.21-2026"}
    a = next(x for x in c if x["act"] == "P.L.20-2026")
    assert a["bill"] == "S.212" and a["approved"] == "2026-01-29"


def test_effective_dates_and_kinds():
    c = clauses()
    by = {(x["act"], x["section_in_act"]): x for x in c}
    assert by[("P.L.20-2026", 1)]["effective_date"] == "2026-07-01" and by[("P.L.20-2026", 1)]["kind"] == "amend"
    assert by[("P.L.20-2026", 2)]["effective_date"] == "2027-07-01"
    rep = by[("P.L.20-2026", 3)]
    assert rep["kind"] == "repeal" and rep["effective_basis"] == "upon_passage" and rep["effective_date"] == "2026-01-29"
    add = by[("P.L.20-2026", 4)]
    assert add["kind"] == "add_section" and add["retroactive"] is True and add["effective_date"] == "2027-01-01"
    assert by[("P.L.20-2026", 5)]["kind"] == "uncodified" and by[("P.L.20-2026", 5)]["target"] is None
    assert by[("P.L.21-2026", 1)]["effective_date"] == "2026-03-03"


def test_page_header_inside_clause_does_not_break_dates():
    c = clauses()
    # clause 2 is followed by a page break; clause 3 must still parse as a repeal of IC 2-5-36-10
    assert any(x["target"] == "2-5-36-10" and x["kind"] == "repeal" for x in c)
    assert all(x["effective_basis"] != "unparsed" for x in c)


def test_levels():
    c = clauses()
    assert all(x["level"] in ("section", None) for x in c)
