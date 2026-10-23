import json

from indiana_law import asof, caselaw, companion, store, tools


def test_parse_harvard_filepath():
    assert caselaw.parse_harvard_filepath("law.free.cap.ne2d.848/341.8409796.json") == ("ne2d", "848", "341")
    assert caselaw.parse_harvard_filepath("not-harvard") is None


def test_classify_historical_and_records():
    assert companion.classify("1852RS1-O.pdf") == companion.KIND_ACTS
    assert companion.classify("records.pdf") == companion.KIND_COURT_RULES
    assert companion.classify("Title 12 Derivation Table.pdf") == companion.KIND_HISTORICAL_TABLE


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


def test_extract_statute_citations_requires_prefix():
    assert asof.extract_statute_citations(
        "See IC 35-42-1-1 and Ind. Code § 31-16-15-25. Indiana Code 7.1-1-1-1."
    ) == ["35-42-1-1", "31-16-15-25", "7.1-1-1-1"]
    assert asof.extract_statute_citations("the form 1-2-3-4 is not a citation") == []
    assert asof.extract_statute_citations("") == []


def _cluster(cluster_id, date_filed, text, court_id="indctapp"):
    return {
        "cluster_id": cluster_id,
        "court_id": court_id,
        "court": caselaw.COURTS[court_id],
        "case_name": f"Case {cluster_id}",
        "date_filed": date_filed,
        "docket_id": f"docket-{cluster_id}",
        "precedential_status": "Published",
        "slug": f"case-{cluster_id}",
        "citation_count": 0,
        "summary": "",
        "headmatter": "",
        "opinion_id": cluster_id,
        "opinion_text": text,
        "text_source": "html",
        "has_opinion_text": 1 if text else 0,
        "search_text": text,
    }


def test_cases_citing_statute_mentions(tmp_path):
    db = str(tmp_path / "mentions.db")
    conn = store.connect(db)
    store.add_snapshot(conn, "2017-07-01", 2017, "2017-07-01")
    conn.execute(
        "INSERT INTO section_version(id,base_id,version_suffix,text,text_hash,effective_from,effective_until,status) "
        "VALUES (?,?,?,?,?,?,?,?)",
        ("35-42-1-1", "35-42-1-1", "", "Murder.", "x", "", "", "current"),
    )
    store.add_case_clusters(conn, [
        _cluster("1", "2020-03-01", "Cited IC 35-42-1-1 and again IC 35-42-1-1. Bare 9-30-5-1 is ignored."),
        _cluster("2", "2005-01-01", "See Ind. Code § 35-42-1-1."),
        _cluster("3", "2021-06-01", "No statute citation here."),
    ])
    stats = caselaw.ingest_statute_mentions(conn)
    assert stats["opinions_scanned"] == 3
    assert stats["opinions_with_mentions"] == 2
    assert stats["mention_pairs"] == 2
    hits = tools.cases_citing(conn, "IC 35-42-1-1")
    assert hits["indexed_mention_count"] == 2
    by_id = {r["cluster_id"]: r for r in hits["results"]}
    assert by_id["1"]["mention_count"] == 2 and by_id["1"]["code_resolved"] is True
    assert by_id["2"]["code_resolved"] is False
    assert "not a citator" in " ".join(hits["flags"])
    assert tools.cases_citing(conn, "9-30-5-1")["results"] == []


MEMO_HEAD = (
    "Pursuant to Indiana Appellate Rule 65(E), the trial court and parties shall not take any action "
    "in reliance upon this memorandum decision until it is certified. MEMORANDUM DECISION Pursuant to "
    "Ind. Appellate Rule 65(D), this Memorandum Decision is not binding precedent for any court and "
    "may be cited only for persuasive value. Court of Appeals Case No. 26A-CR-1234"
)
OPINION_HEAD = (
    "Pursuant to Indiana Appellate Rule 65(E), the trial court and parties shall not take any action "
    "in reliance upon this Opinion until it is certified. IN THE Court of Appeals of Indiana "
    "Court of Appeals Case No. 26A-PL-99"
)


def test_classify_decision_form_from_slip_wording():
    memo = caselaw.classify_decision_form(MEMO_HEAD)
    assert memo["decision_form"] == "memorandum"
    assert memo["case_number_in_text"] == "26A-CR-1234"
    opin = caselaw.classify_decision_form(OPINION_HEAD)
    assert opin["decision_form"] == "opinion"
    assert caselaw.citability_for("memorandum", "2023-01-01") == "persuasive"
    assert caselaw.citability_for("memorandum", "2022-12-31") == "limited"
    assert caselaw.citability_for("opinion", "2020-01-01") == "precedent"


def test_ingest_decision_forms_flags_source_disagreement(tmp_path):
    db = str(tmp_path / "forms.db")
    conn = store.connect(db)
    store.add_case_clusters(conn, [
        _cluster("m", "2026-10-22", MEMO_HEAD),
        _cluster("p", "2026-10-22", OPINION_HEAD),
        _cluster("wrong", "2018-06-01", MEMO_HEAD),
    ])
    conn.execute("UPDATE case_cluster SET precedential_status='Unpublished' WHERE cluster_id='m'")
    conn.execute("UPDATE case_cluster SET precedential_status='Published' WHERE cluster_id IN ('p','wrong')")
    stats = caselaw.ingest_decision_forms(conn)
    assert stats["counts"]["memorandum"] == 2
    assert stats["counts"]["opinion"] == 1
    assert stats["disagrees_with_source"] == 1
    case = tools.get_case(conn, "m")
    assert case["decision_form"] == "memorandum" and case["citability"] == "persuasive"
    wrong = tools.get_case(conn, "wrong")
    assert wrong["decision_form"] == "memorandum" and any("Published" in f for f in wrong["flags"])


def test_case_cite_normalize_and_extract():
    from indiana_law import case_cites

    assert case_cites.reporter_key("N.E.2d", "848", "341") == "ne2d|848|341"
    assert case_cites.parse_reporter_cite("See Henderson, 848 N.E.2d 341, 344.") == "ne2d|848|341"
    assert case_cites.parse_reporter_cite("109 Ind. App. 1") == "ind-app|109|1"
    assert case_cites.parse_reporter_cite("1 Blackf. 1") == "blackf|1|1"
    assert case_cites.normalize_docket("No. 22A-CT-0925") == "22A-CT-925"
    assert case_cites.docket_key("22A-CT-925") == "docket|22A-CT-925"
    assert case_cites.harvard_cap_id_from_filepath("law.free.cap.ne2d.848/341.8409796.json") == "8409796"
    text = "Cited 848 N.E.2d 341 and again 848 N.E.2d 341. Also No. 22A-CT-925 (Ind. Ct. App.). Bare 1 U.S. 1 stays out of the regex. Pinpoint 848 N.E.2d at 344 is not a first-page key."
    assert case_cites.extract_reporter_keys(text).count("ne2d|848|341") == 2
    assert "ne2d|848|344" not in case_cites.extract_reporter_keys(text)
    assert case_cites.extract_docket_keys(text) == ["docket|22A-CT-925"]


def test_ingest_case_citations_resolves_unique_keys(tmp_path):
    from indiana_law import case_cites

    clusters = tmp_path / "clusters.jsonl"
    harvard = tmp_path / "harvard.jsonl"
    clusters.write_text(
        json.dumps({
            "id": "cited",
            "filepath_json_harvard": "law.free.cap.ne2d.848/341.8409796.json",
        }) + "\n" + json.dumps({
            "id": "citing",
            "filepath_json_harvard": "law.free.cap.ne3d.10/1.99.json",
        }) + "\n" + json.dumps({
            "id": "table-a",
            "filepath_json_harvard": "law.free.cap.ne3d.92/1090.1.json",
        }) + "\n" + json.dumps({
            "id": "table-b",
            "filepath_json_harvard": "law.free.cap.ne3d.92/1090.2.json",
        }) + "\n"
    )
    harvard.write_text(
        json.dumps({
            "cap_id": 8409796, "reporter": "ne2d", "volume": "848", "first_page": "341",
            "citations": ["848 N.E.2d 341"], "docket_number": "No. 06A-CR-341",
        }) + "\n" + json.dumps({
            "cap_id": 99, "reporter": "ne3d", "volume": "10", "first_page": "1",
            "citations": ["10 N.E.3d 1"], "docket_number": "",
        }) + "\n" + json.dumps({
            "cap_id": 1, "reporter": "ne3d", "volume": "92", "first_page": "1090",
            "citations": ["92 N.E.3d 1090"], "docket_number": "",
        }) + "\n" + json.dumps({
            "cap_id": 2, "reporter": "ne3d", "volume": "92", "first_page": "1090",
            "citations": ["92 N.E.3d 1090"], "docket_number": "",
        }) + "\n"
    )
    db = str(tmp_path / "cites.db")
    conn = store.connect(db)
    store.add_case_clusters(conn, [
        _cluster("cited", "2006-06-01", "Henderson v. State, 848 N.E.2d 341."),
        _cluster("citing", "2020-03-01", "We follow Henderson, 848 N.E.2d 341. See also 92 N.E.3d 1090 and 1 U.S. 1."),
        _cluster("table-a", "2018-01-01", "Table disposition A."),
        _cluster("table-b", "2018-01-02", "Table disposition B."),
        _cluster("later", "2024-06-01", "Also No. 06A-CR-341 (Ind. Ct. App.)."),
    ])
    conn.execute(
        "INSERT INTO case_form(cluster_id, decision_form, citability, case_number_in_text, disagrees_with_source) "
        "VALUES (?,?,?,?,?)",
        ("cited", "opinion", "precedent", "06A-CR-341", 0),
    )
    stats = case_cites.ingest_case_citations(conn, str(clusters), str(harvard))
    assert stats["opinions_scanned"] == 5
    assert stats["mention_pairs"] == 2
    inbound = tools.cases_citing_case(conn, "848 N.E.2d 341")
    assert inbound["cluster_id"] == "cited"
    assert {r["cluster_id"] for r in inbound["results"]} == {"citing", "later"}
    assert any("not a citator" in f for f in inbound["flags"])
    outbound = tools.cases_cited_in(conn, "citing")
    assert [r["cluster_id"] for r in outbound["results"]] == ["cited"]
    table = tools.cases_citing_case(conn, "92 N.E.3d 1090")
    assert table["results"] == [] and table.get("candidates")
    case = tools.get_case(conn, "cited")
    assert case["citing_this"] == 2 and case["cited_by_this"] == 0
    assert any("848" in c for c in case["reporter_cites"])
