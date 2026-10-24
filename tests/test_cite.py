import datetime as dt
from pathlib import Path

import pytest

from indiana_law import cite as C

RULE_22_EXAMPLES = [
    "Steele v. Taber, No. 22A-CT-925 (Ind. Ct. App. Jan. 17, 2023) (mem.)",
    "Martinez v. State, No. 22A-CR-1196, at *4 (Ind. Ct. App. Jan. 26, 2023) (mem.), trans. denied",
]


@pytest.mark.parametrize("text", RULE_22_EXAMPLES)
def test_indiana_rule_22_examples_round_trip_exactly(text):
    assert C.format_full(C.parse(text)) == text


@pytest.mark.parametrize("raw,canonical", [("25A-CR-01234", "25A-CR-1234"), ("25A-CR-1234", "25A-CR-1234"), ("No. 25S-CR-00349", "25S-CR-349"),
                                           ("26S-CR-00198", "26S-CR-198"), ("25T-TA-0012", "25T-TA-12")])
def test_dockets_are_normalised_without_zero_padding(raw, canonical):
    assert C.normalize_docket(raw) == canonical


def test_a_trial_court_number_is_not_an_appellate_case_number():
    with pytest.raises(ValueError):
        C.normalize_docket("18C04-2311-F1-16")


def test_court_comes_from_the_case_number():
    assert C.parse("No. 25A-CR-1234").court == "Ind. Ct. App."
    assert C.parse("No. 25S-CR-349").court == "Ind."
    assert C.parse("No. 25T-TA-12").court == "Ind. Tax Ct."


def test_paragraph_pinpoint_full_short_id_machine_and_permalink():
    c = C.parse("Smith v. Jones, No. 25A-CR-01234, ¶ 23 (Ind. Ct. App. Oct. 3, 2025)")
    assert C.format_full(c) == "Smith v. Jones, No. 25A-CR-1234, ¶ 23 (Ind. Ct. App. Oct. 3, 2025)"
    assert C.format_short(c) == "Smith, No. 25A-CR-1234, ¶ 23"
    assert C.format_id(C.Pinpoint("para", 24)) == "Id. ¶ 24"
    assert C.format_id(C.Pinpoint("page", 5)) == "Id. at *5"
    assert C.machine_id(c) == "ind:25A-CR-1234:p23"
    assert C.permalink(c, "https://indianacle.com") == "https://indianacle.com/opinions/25A-CR-1234#p23"


def test_page_pinpoint_machine_id_and_permalink():
    c = C.parse("Martinez v. State, No. 22A-CR-1196, at *4 (Ind. Ct. App. Jan. 26, 2023) (mem.)")
    assert C.machine_id(c) == "ind:22A-CR-1196:page-4"
    assert C.permalink(c) == "/opinions/22A-CR-1196#page-4"


def test_ranges_and_supreme_court_form():
    assert str(C.parse("Taylor v. State, No. 25S-CR-349, at *4–5 (Ind. Dec. 17, 2025)").pin) == "*4–5"
    assert C.format_full(C.parse("Taylor v. State, No. 25S-CR-349 (Ind. Dec. 17, 2025)")) == "Taylor v. State, No. 25S-CR-349 (Ind. Dec. 17, 2025)"
    assert str(C.parse("Doe, No. 25A-CR-9, ¶¶ 23–25").pin) == "¶¶ 23–25"


def test_find_citations_in_running_text():
    text = ("The court held otherwise. Steele v. Taber, No. 22A-CT-925 (Ind. Ct. App. Jan. 17, 2023) (mem.). "
            "Later, Steele, No. 22A-CT-925, at *3, was followed in Smith v. Jones, No. 25A-CR-01234, ¶ 23 (Ind. Ct. App. Oct. 3, 2025).")
    found = C.find_citations(text)
    assert [c.docket for c in found] == ["22A-CT-925", "22A-CT-925", "25A-CR-1234"]
    assert found[1].pin == C.Pinpoint("page", 3) and found[2].pin == C.Pinpoint("para", 23)


PAGES = [
    "IN THE Court of Appeals of Indiana ... cover",
    "Case Summary\n[1]   Boehm entered into a contract with Washboard for the purchase of property and construction of a home.\n[2]   The trial court granted summary judgment.\nCourt of Appeals of Indiana | Memorandum Decision 25A-CT-1008 | Page 2 of 3",
    "Discussion\n[3]   We review summary judgment de novo, as explained in [1] above.\nPage 3 of 3",
]


def test_paragraph_index_finds_the_page_each_paragraph_starts_on():
    idx = C.index_text(PAGES)
    assert idx["pages"] == 3 and idx["has_paragraphs"] and idx["paragraphs_consecutive"]
    assert idx["page_labels_match_pdf_pages"] is True
    assert idx["paragraphs"][1]["page"] == 2 and idx["paragraphs"][3]["page"] == 3
    assert idx["paragraphs"][3]["snippet"].startswith("We review summary judgment")


def test_jump_to_a_paragraph_opens_the_official_pdf_at_its_page_with_the_opening_words():
    idx = C.index_text(PAGES)
    url = "https://public.courts.in.gov/Decisions/api/Document/Opinion?Id=abc"
    result = C.jump(C.parse("Boehm, No. 25A-CT-1008, ¶ 3"), url, idx)
    assert result["page"] == 3 and result["url"] == url + "#page=3" and result["snippet"].startswith("We review")


def test_jump_explains_when_a_paragraph_or_page_does_not_exist():
    idx = C.index_text(PAGES)
    url = "https://example.test/o"
    assert "no such numbered paragraph" in C.jump(C.parse("Boehm, No. 25A-CT-1008, ¶ 99"), url, idx)["note"]
    assert C.jump(C.parse("Boehm, No. 25A-CT-1008, at *9"), url, idx)["url"] == url
    unnumbered = C.index_text(["Opinion text without numbered paragraphs\nPage 1 of 1"])
    assert "not numbered" in C.jump(C.parse("Taylor, No. 25S-CR-349, ¶ 4"), url, unnumbered)["note"]


def test_a_paragraph_pinpoint_converts_to_the_star_page_rule_22_asks_for():
    idx = C.index_text(PAGES)
    c = C.to_page_pin(C.parse("Boehm v. Washboard BDF LLC, No. 25A-CT-1008, ¶ 3 (Ind. Ct. App. Mar. 23, 2026) (mem.)"), idx)
    assert C.format_full(c) == "Boehm v. Washboard BDF LLC, No. 25A-CT-1008, at *3 (Ind. Ct. App. Mar. 23, 2026) (mem.)"


CACHE = Path(__file__).resolve().parent.parent / "data" / "opinions-cache"


@pytest.mark.skipif(not (CACHE / "MAR-10.pdf").exists(), reason="opinion cache not downloaded")
def test_real_court_of_appeals_memorandum_decision_has_numbered_paragraphs_and_matching_pages():
    idx = C.index_pdf(CACHE / "MAR-10.pdf")
    assert idx["pages"] == 29 and idx["has_paragraphs"] and idx["page_labels_match_pdf_pages"] is True
    assert idx["paragraphs"][1]["page"] == 2


@pytest.mark.skipif(not (CACHE / "DEC-02.pdf").exists(), reason="opinion cache not downloaded")
def test_real_supreme_court_opinion_is_cited_by_page_not_paragraph():
    idx = C.index_pdf(CACHE / "DEC-02.pdf")
    assert idx["pages"] == 8 and not idx["has_paragraphs"] and idx["page_labels_match_pdf_pages"] is True
