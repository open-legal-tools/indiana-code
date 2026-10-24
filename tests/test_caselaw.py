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


AFFIRM_PROSE = (
    "We therefore affirm the trial court's judgment. May, J., and Crone, J., concur. "
    "Court of Appeals of Indiana | Memorandum Decision 22A-JC-1683 | January 4, 2023 Page 11 of 11"
)
AFFIRM_LINE = (
    "[31] Affirmed. Altice, C.J., and Brown, J., concur. "
    "Court of Appeals of Indiana | Memorandum Decision 22A-PL-1492 | January 9, 2023 Page 20 of 20"
)
MIXED_LINE = "[26] Reversed and remanded with instructions. Bailey, J. and Vaidik, J. concur."
PART_LINE = "[19] Reversed in part. Crone, J., and Weissmann, J., concur."
THREE_WAY = "Affirmed in part, reversed in part, and remanded."
NO_DISPOSITION = (
    "In my view, the jury should be entrusted to assess Dr. Mundt’s testimony together with the other evidence presented at trial. "
    "Court of Appeals of Indiana | Opinion 22A-CR-1116 | January 9, 2023 Page 20 of 20"
)
NEGATIVE = "Accordingly, we do not direct the entry of summary judgment for the Commission at this time."


def test_classify_disposition_reads_the_closing_line():
    prose = caselaw.classify_disposition(AFFIRM_PROSE)
    assert prose["disposition"] == "affirmed" and prose["method"] == "prose"
    assert prose["quote"].startswith("We therefore affirm")
    line = caselaw.classify_disposition(AFFIRM_LINE)
    assert line["disposition"] == "affirmed" and line["method"] == "closing_line"
    assert line["quote"].rstrip(".").endswith("Affirmed")
    mixed = caselaw.classify_disposition(MIXED_LINE)
    assert mixed["disposition"] == "mixed"
    assert mixed["labels"] == ["reversed", "remanded"] and mixed["in_part"] is False
    part = caselaw.classify_disposition(PART_LINE)
    assert part["disposition"] == "reversed" and part["in_part"] is True
    three = caselaw.classify_disposition(THREE_WAY)
    assert three["labels"] == ["affirmed", "reversed", "remanded"] and three["in_part"] is True
    assert caselaw.classify_disposition(NO_DISPOSITION)["disposition"] == "unlabeled"
    assert caselaw.classify_disposition(NEGATIVE)["disposition"] == "unlabeled"
    assert caselaw.classify_disposition("")["method"] == "no_text"
    buried = "The Supreme Court affirmed the conviction in an earlier case. " + ("analysis " * 40)
    assert caselaw.classify_disposition(buried)["disposition"] == "unlabeled"


def test_ingest_dispositions_on_case_get_and_search(tmp_path):
    db = str(tmp_path / "disp.db")
    conn = store.connect(db)
    store.add_case_clusters(conn, [
        _cluster("a", "2023-01-04", "Child was a CHINS. " + AFFIRM_PROSE),
        _cluster("b", "2023-01-11", "The order cannot stand. " + MIXED_LINE),
        _cluster("c", "2023-01-09", NO_DISPOSITION),
    ])
    store.finalize_cases(conn)
    stats = caselaw.ingest_dispositions(conn)
    assert stats["labeled"] == 2
    got = tools.get_case(conn, "b")
    assert got["disposition"] == "mixed"
    assert got["disposition_labels"] == ["reversed", "remanded"]
    assert "not an official judgment" in " ".join(got["flags"])
    assert got["text"][got["disposition_quote"] and got["text"].index(got["disposition_quote"]):].startswith(got["disposition_quote"])
    hits = tools.search_cases(conn, "order", disposition="remanded")
    assert [r["cluster_id"] for r in hits["results"]] == ["b"]
    assert tools.search_cases(conn, "Child", disposition="affirmed")["results"][0]["cluster_id"] == "a"


DE_NOVO = "The trial court's decision was based on a paper record. Therefore, our review is de novo. See In re Adoption of C.B.M., 992 N.E.2d 687, 691 (Ind. 2013)."
ABUSE = "A probation revocation determination, including the sanction imposed, is reviewed for abuse of discretion."
BOTH = DE_NOVO + " " + ABUSE
HOLDING_ONLY = "The trial court did not abuse its discretion in admitting the exhibit."
FACT_ONLY = "There was substantial evidence that M.R. accepted and welcomed the support."
ARGUMENT = "Smith argues that our review is de novo and that the court erred."


def test_classify_standards_keeps_stated_standards_only():
    labels = [row["label"] for row in caselaw.classify_standards(BOTH)]
    assert labels == ["de_novo", "abuse_of_discretion"]
    de_novo = caselaw.classify_standards(DE_NOVO)[0]
    assert de_novo["quote"] in DE_NOVO or DE_NOVO[de_novo["quote_start"]:de_novo["quote_end"]] == de_novo["quote"]
    assert "de novo" in de_novo["quote"]
    assert caselaw.classify_standards(HOLDING_ONLY) == []
    assert caselaw.classify_standards(FACT_ONLY) == []
    assert caselaw.classify_standards(ARGUMENT) == []
    assert caselaw.classify_standards("") == []
    sufficiency = "When assessing the sufficiency of the evidence, we neither reweigh the evidence nor judge witness credibility."
    assert caselaw.classify_standards(sufficiency)[0]["label"] == "sufficiency"


def test_ingest_standards_on_case_get_and_search(tmp_path):
    db = str(tmp_path / "std.db")
    conn = store.connect(db)
    store.add_case_clusters(conn, [
        _cluster("novo", "2024-01-01", "Paper record. " + DE_NOVO),
        _cluster("both", "2024-02-01", BOTH + " The sanction was within the court's range."),
        _cluster("none", "2024-03-01", HOLDING_ONLY + " " + FACT_ONLY),
    ])
    store.finalize_cases(conn)
    stats = caselaw.ingest_standards(conn)
    assert stats["opinions_with_standards"] == 2
    assert stats["counts"]["de_novo"] == 2
    assert stats["counts"]["abuse_of_discretion"] == 1
    got = tools.get_case(conn, "both")
    assert [row["label"] for row in got["standards"]] == ["de_novo", "abuse_of_discretion"]
    assert got["text"][got["standards"][0]["quote_start"]:got["standards"][0]["quote_end"]] == got["standards"][0]["quote"]
    assert "not a ruling on which standard governs" in " ".join(got["flags"])
    hits = tools.search_cases(conn, "sanction", standard="abuse of discretion")
    assert [row["cluster_id"] for row in hits["results"]] == ["both"]
    assert hits["results"][0]["standard"] == "abuse_of_discretion"
    de_novo_hits = {row["cluster_id"] for row in tools.search_cases(conn, "review", standard="de novo")["results"]}
    assert de_novo_hits == {"novo", "both"}
    assert tools.search_cases(conn, "exhibit", standard="de_novo")["results"] == []


CONSTRUE = 'The Act "is to be liberally construed and administered." I.C. § 34-14-1-12. The next sentence is about procedure.'
APPLIES = 'But the statute only applies if the decedent died from other causes. Ind. Code § 34-9-3-4(a).'
VIOLATION = "Foster argues that her land was assessed in violation of Indiana Code § 6-1.1-4-4.2(b)."
SEPARATE = "See I.C. § 8-15.5-2-8. When a statutory term is undefined, courts interpret the term using its plain meaning."
PURSUANT = "Pursuant to I.C. § 34-13-3-10, the notice must describe the facts."
NEGATED = "Though not applicable to this case, Indiana also has an Adult Wrongful Death Statute. Ind. Code § 34-23-1-2."
CONSTRUCTIVE = "The order constituted constructive eviction, since she was not allowed to post a bond pursuant to IC 32-30-3-8."
REPORTER = "See Smith v. State, 848 N.E.2d 341, 344 (Ind. 2006). We construe Ind. Code § 35-42-1-1 narrowly."


def test_classify_statute_signals_stay_in_the_same_sentence():
    constru = caselaw.classify_statute_signals(CONSTRUE)
    assert [(row["section_id"], row["relation"]) for row in constru] == [("34-14-1-12", "construes")]
    assert constru[0]["status"] == "rule_unreviewed"
    assert CONSTRUE[constru[0]["quote_start"]:constru[0]["quote_end"]] == constru[0]["quote"]
    assert "next sentence" not in constru[0]["quote"]
    applies = caselaw.classify_statute_signals(APPLIES)
    assert [(row["section_id"], row["relation"]) for row in applies] == [("34-9-3-4", "applies")]
    violation = caselaw.classify_statute_signals(VIOLATION)
    assert violation[0]["section_id"] == "6-1.1-4-4.2" and violation[0]["relation"] == "applies"
    assert caselaw.classify_statute_signals(SEPARATE) == []
    assert caselaw.classify_statute_signals(PURSUANT) == []
    assert caselaw.classify_statute_signals(NEGATED) == []
    assert caselaw.classify_statute_signals(CONSTRUCTIVE) == []
    reporter = caselaw.classify_statute_signals(REPORTER)
    assert [(row["section_id"], row["relation"]) for row in reporter] == [("35-42-1-1", "construes")]
    assert "848 N.E.2d" not in reporter[0]["quote"]


def test_cases_construing_returns_the_quote(tmp_path):
    db = str(tmp_path / "sig.db")
    conn = store.connect(db)
    store.add_case_clusters(conn, [
        _cluster("c1", "2024-05-01", CONSTRUE),
        _cluster("c2", "2024-06-01", APPLIES),
        _cluster("c3", "2024-07-01", SEPARATE),
    ])
    stats = caselaw.ingest_statute_signals(conn)
    assert stats["opinions_with_signals"] == 2
    got = tools.cases_construing(conn, "IC 34-14-1-12", relation="construes")
    assert got["results"][0]["cluster_id"] == "c1"
    assert got["results"][0]["status"] == "rule_unreviewed"
    assert "not a holding" in " ".join(got["flags"])
    assert tools.cases_construing(conn, "34-9-3-4", relation="construes")["results"] == []
    case = tools.get_case(conn, "c2")
    assert case["statute_signals"][0]["section_id"] == "34-9-3-4"
    assert case["text"][case["statute_signals"][0]["quote_start"]:case["statute_signals"][0]["quote_end"]] == case["statute_signals"][0]["quote"]


def test_case_cite_normalize_and_extract():
    from indiana_law import case_cites

    assert case_cites.reporter_key("N.E.2d", "848", "341") == "ne2d|848|341"
    assert case_cites.parse_reporter_cite("See Henderson, 848 N.E.2d 341, 344.") == "ne2d|848|341"
    assert case_cites.parse_reporter_cite("109 Ind. App. 1") == "ind-app|109|1"
    assert case_cites.parse_reporter_cite("1 Blackf. 1") == "blackf|1|1"
    assert case_cites.normalize_docket("No. 22A-CT-0925") == "22A-CT-925"
    assert case_cites.docket_key("22A-CT-925") == "docket|22A-CT-925"
    assert case_cites.harvard_cap_id_from_filepath("law.free.cap.ne2d.848/341.8409796.json") == "8409796"
    text = "Cited 848 N.E.2d 341 and again 848 N.E.2d 341. Also No. 22A-CT-925 (Ind. Ct. App.). 17 U.S.C. § 1983 is a statute. Pinpoint 848 N.E.2d at 344 is not a first-page key."
    assert case_cites.extract_reporter_keys(text).count("ne2d|848|341") == 2
    assert "ne2d|848|344" not in case_cites.extract_reporter_keys(text)
    assert case_cites.extract_docket_keys(text) == ["docket|22A-CT-925"]
    assert "us|" not in " ".join(case_cites.extract_reporter_keys(text))


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
    unresolved = tools.cases_cited_in(conn, "citing")["unresolved"]
    assert any(r["cite_key"] == "us|1|1" for r in unresolved)


def test_indigo_shaped_federal_and_parenthetical_extract():
    from indiana_law import case_cites

    # Bandido's-style parallel SCOTUS + cramped 7th Cir. / N.D. Ind.
    bandidos = (
        "New York Times Co. v. Sullivan, 376 U.S. 254, 269, 84 S.Ct. 710, "
        "11 L.Ed.2d 686 (1964). See Chang, 20 F.3d 255, 262 (7th Cir.1994); "
        "Gintert v. Howard Publications, Inc., 565 F.Supp. 829, 838-39 (N.D.Ind.1983)."
    )
    keys = case_cites.extract_reporter_keys(bandidos)
    assert "us|376|254" in keys
    assert "sct|84|710" in keys
    assert "led2d|11|686" in keys
    assert "us|376|84" not in keys
    assert "f3d|20|255" in keys
    assert "fsupp|565|829" in keys
    cites = {c["cite_key"]: c for c in case_cites.extract_cites(bandidos)}
    assert cites["f3d|20|255"]["court"] == "7th Cir."
    assert cites["f3d|20|255"]["year"] == "1994"
    assert cites["fsupp|565|829"]["court"] == "N.D. Ind."
    assert cites["fsupp|565|829"]["year"] == "1983"

    # Reever: 7th Cir. + S.D. Ind. Westlaw slip + SCOTUS year-only paren.
    reever = (
        "aff’d, 990 F.3d 565 (7th Cir. 2021), cert. denied. "
        "See 2020 WL 1149595 (S.D. Ind. Mar. 10, 2020) and 520 U.S. 564, 592 (1997)."
    )
    cites = {c["cite_key"]: c for c in case_cites.extract_cites(reever)}
    assert cites["f3d|990|565"]["court"] == "7th Cir." and cites["f3d|990|565"]["year"] == "2021"
    assert cites["wl|2020|1149595"]["court"] == "S.D. Ind." and cites["wl|2020|1149595"]["year"] == "2020"
    assert cites["us|520|564"]["year"] == "1997"

    # Hunter Warfield: F.4th, F. Supp. 2d, sister circuit, W.Va.
    hunter = (
        "27 F.4th 544, 550 (7th Cir. 2022); 530 U.S. 15, 20-21 (2000); "
        "725 F.Supp. 406, 412 (N.D. Ind. 1989); 706 F.Supp.2d 916, 925 (E.D. Wis. 2010); "
        "399 S.E.2d 694 (W.Va. 1990); 947 F.3d 735 (11th Cir. 2020)."
    )
    cites = {c["cite_key"]: c for c in case_cites.extract_cites(hunter)}
    assert cites["f4th|27|544"]["court"] == "7th Cir."
    assert cites["fsupp|725|406"]["court"] == "N.D. Ind."
    assert cites["fsupp2d|706|916"]["court"] == "E.D. Wis."
    assert cites["se2d|399|694"]["court"] == "W.Va."
    assert cites["f3d|947|735"]["court"] == "11th Cir."
    assert case_cites.normalize_court("seventh circuit") == "7th Cir."
    assert case_cites.normalize_court("2d. Cir.") == "2d Cir."
    assert case_cites.parse_court_year("7th Cir. 2021") == ("7th Cir.", "2021")
    assert case_cites.parse_court_year("N.D. Ind. 2019") == ("N.D. Ind.", "2019")
    assert case_cites.parse_court_year("West 2020") is None
    assert case_cites.parse_court_year("Burns 2019") is None
    assert not any(c["court"] in {"West.", "Burns.", "Eff.", "Supp."} for c in case_cites.extract_parentheticals(
        "(West 2020) (Burns 2019) (Eff. 2017) (Supp. 2021) (7th Cir. 2021)"
    ))


def test_cases_citing_unresolved_and_court_year(tmp_path):
    from indiana_law import case_cites

    db = str(tmp_path / "outbound.db")
    conn = store.connect(db)
    store.add_case_clusters(conn, [
        _cluster("reever", "2024-01-10", "aff’d, 990 F.3d 565 (7th Cir. 2021). See 2020 WL 1149595 (S.D. Ind. Mar. 10, 2020)."),
        _cluster("hunter", "2026-09-30", "27 F.4th 544, 550 (7th Cir. 2022) and 725 F.Supp. 406 (N.D. Ind. 1989)."),
        _cluster("local", "2020-03-01", "We follow Henderson, 848 N.E.2d 341 (Ind. 2006)."),
    ])
    stats = case_cites.ingest_case_citations(conn, "", "")
    assert stats["outbound_rows"] >= 3
    seventh = tools.cases_citing_court(conn, "7th Cir.", "2021")
    assert {r["cluster_id"] for r in seventh["results"]} == {"reever"}
    assert any("not a citator" in f for f in seventh["flags"])
    nd = tools.cases_citing_court(conn, "northern district of indiana")
    assert {r["cluster_id"] for r in nd["results"]} == {"hunter"}
    mention = tools.cases_citing_case(conn, "990 F.3d 565")
    assert mention["cluster_id"] is None and mention.get("resolved") is False
    assert {r["cluster_id"] for r in mention["results"]} == {"reever"}
    via_paren = tools.cases_citing_case(conn, "7th Cir. 2021")
    assert {r["cluster_id"] for r in via_paren["results"]} == {"reever"}


DISSENT_LINE = "Riley, J., dissents with separate opinion."
CONCUR_LINE = "Brown, Judge, concurs with separate opinion."
BOTH_PARTS = "Judge Bradford concurs in part, dissents in part with separate opinion."
TRANSFER = "David, J., dissents from the denial of transfer with separate opinion in which Rush, C.J., concurs."
OTHER_CASE = "In a separate opinion, Justice Goff dissented from the foreseeability holding."
WITHOUT = "Wife dissents without separate opinion from the fee order."
NARRATIVE = "895 N.E.2d at 1225. He expressed his disagreement in a separate opinion concurring in the result."
PRIOR_CONCUR = "We reverse and remand. Brown, J., concurs. Riley, J., dissents with a separate opinion. Ivy concedes the point."


def test_classify_separate_writings_reads_the_slip_vote_line():
    assert [row["label"] for row in caselaw.classify_separate_writings(DISSENT_LINE)] == ["dissents"]
    assert [row["label"] for row in caselaw.classify_separate_writings(CONCUR_LINE)] == ["concurs"]
    both = [row["label"] for row in caselaw.classify_separate_writings(BOTH_PARTS)]
    assert both == ["concurs_in_part", "dissents_in_part"]
    transfer = [row["label"] for row in caselaw.classify_separate_writings(TRANSFER)]
    assert transfer == ["joins", "transfer_dissent"]
    quote = caselaw.classify_separate_writings(DISSENT_LINE)[0]
    assert DISSENT_LINE[quote["quote_start"]:quote["quote_end"]] == quote["quote"]
    assert caselaw.classify_separate_writings(OTHER_CASE) == []
    assert caselaw.classify_separate_writings(WITHOUT) == []
    assert caselaw.classify_separate_writings(NARRATIVE) == []
    prior = caselaw.classify_separate_writings(PRIOR_CONCUR)
    assert [row["label"] for row in prior] == ["dissents"]
    assert "Brown" not in prior[0]["quote"]
    assert "Ivy" not in prior[0]["quote"]


def test_separate_writings_round_trip(tmp_path):
    db = str(tmp_path / "sep.db")
    conn = store.connect(db)
    store.add_case_clusters(conn, [
        _cluster("d1", "2024-01-01", "The panel affirms. " + DISSENT_LINE),
        _cluster("c1", "2024-02-01", CONCUR_LINE + " We affirm."),
        _cluster("n1", "2024-03-01", OTHER_CASE),
    ])
    stats = caselaw.ingest_separate_writings(conn)
    store.finalize_cases(conn)
    assert stats["opinions_with_separate"] == 2
    case = tools.get_case(conn, "d1")
    assert case["separate_writings"][0]["label"] == "dissents"
    assert case["text"][case["separate_writings"][0]["quote_start"]:case["separate_writings"][0]["quote_end"]] == case["separate_writings"][0]["quote"]
    assert "not a holding" in " ".join(case["flags"])
    found = tools.search_cases(conn, "affirms", separate="dissents")
    assert {row["cluster_id"] for row in found["results"]} == {"d1"}
