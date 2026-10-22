from indiana_law import caselaw, store, tools


def test_html_to_text_and_opinion_fallback():
    assert "Henderson" in caselaw.html_to_text("<p>Henderson <b>v.</b> State</p>")
    text, src = caselaw.opinion_text({"plain_text": "", "html_with_citations": "<p>Reversed.</p>"})
    assert text == "Reversed." and src == "html_with_citations"


def test_case_search_and_get(tmp_path):
    db = str(tmp_path / "cases.db")
    conn = store.connect(db)
    store.add_snapshot(conn, "2026-06-23", 2026, "2026-06-23")
    store.add_case_clusters(conn, [{
        "cluster_id": "2223991",
        "court_id": "indctapp",
        "court": "Indiana Court of Appeals",
        "case_name": "Henderson v. State",
        "date_filed": "2006-06-01",
        "docket_id": "2042973",
        "precedential_status": "Published",
        "slug": "henderson-v-state",
        "citation_count": 44,
        "summary": "Post-conviction relief denied.",
        "headmatter": "",
        "opinion_id": "9",
        "opinion_text": "The trial court denied relief.",
        "text_source": "html_with_citations",
        "has_opinion_text": 1,
        "search_text": "Henderson v. State Post-conviction relief denied. The trial court denied relief.",
    }])
    store.finalize_cases(conn)
    hits = tools.search_cases(conn, "henderson post-conviction")
    assert hits["results"] and hits["results"][0]["cluster_id"] == "2223991"
    case = tools.get_case(conn, "2223991")
    assert case["found"] and case["has_opinion_text"] and "denied" in case["text"]
    assert case["unofficial"]
