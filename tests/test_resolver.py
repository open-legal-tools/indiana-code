from indiana_law import cite, store, tools, web

OPINION = (
    "IN THE COURT OF APPEALS OF INDIANA Steele v. Taber Court of Appeals Case No. 22A-CT-925\n"
    "[1] Steele appeals the denial of his motion. We affirm.\n"
    "[2] The facts are undisputed. See [27] of the other opinion for contrast.\n"
    "[3] The trial court did not abuse its discretion."
)


def _cluster(cid, date, name, text, court_id="indctapp"):
    return {
        "cluster_id": cid, "court_id": court_id, "court": "Indiana Court of Appeals", "case_name": name,
        "date_filed": date, "docket_id": f"d{cid}", "precedential_status": "Unpublished", "slug": f"c-{cid}",
        "citation_count": 0, "summary": "", "headmatter": "", "opinion_id": cid, "opinion_text": text,
        "text_source": "html", "has_opinion_text": 1 if text else 0, "search_text": text,
    }


def _db(tmp_path):
    conn = store.connect(str(tmp_path / "r.db"))
    store.add_snapshot(conn, "2026-06-23", 2026, "2026-06-23")
    store.add_case_clusters(conn, [
        _cluster("1", "2023-01-17", "Steele v. Taber", OPINION),
        _cluster("2", "2024-05-01", "Later v. State",
                 "We rely on Steele v. Taber, No. 22A-CT-925 (Ind. Ct. App. Jan. 17, 2023) (mem.), trans. denied, "
                 "and on nothing else."),
        _cluster("3", "2024-09-01", "Other v. State",
                 "Compare Steele v. Taber, 100 N.E.3d 1 (Ind. Ct. App. 2023), aff'd, which is not our case."),
    ])
    conn.execute("INSERT INTO case_cite(cite_key, cluster_id, cite_kind, raw_cite) VALUES ('docket|22A-CT-925','1','docket','22A-CT-925')")
    conn.execute("INSERT INTO case_form(cluster_id, decision_form, citability, case_number_in_text, disagrees_with_source) VALUES ('1','memorandum','persuasive','22A-CT-925',0)")
    conn.execute("INSERT INTO case_mention(citing_id, cited_id, mention_count, cite_kind, as_of) VALUES ('2','1',1,'docket','2026-06-23')")
    conn.commit()
    return conn


def test_paragraph_markers_accept_only_the_ascending_sequence():
    marks = cite.paragraph_markers(OPINION)
    assert [n for n, _ in marks] == [1, 2, 3]  # the cross-reference "[27]" is not a paragraph


def test_resolve_by_rule_22_citation_with_paragraph_pinpoint(tmp_path):
    out = tools.resolve_opinion(_db(tmp_path), "Steele v. Taber, No. 22A-CT-925, ¶ 2 (Ind. Ct. App. Jan. 17, 2023) (mem.)")
    assert out["found"] and out["cluster_id"] == "1"
    assert out["citation"].startswith("Steele v. Taber, No. 22A-CT-925, ¶ 2 (Ind. Ct. App. Jan. 17, 2023) (mem.)")
    assert out["permalink"] == "/opinions/22A-CT-925#p2" and out["machine_id"] == "ind:22A-CT-925:p2"
    assert out["pinpoint"]["exists"] and out["pinpoint"]["snippet"].startswith("The facts are undisputed")


def test_missing_paragraph_and_page_pin_are_reported_honestly(tmp_path):
    conn = _db(tmp_path)
    missing = tools.resolve_opinion(conn, "No. 22A-CT-925, ¶ 40")
    assert missing["pinpoint"]["exists"] is False and "no such numbered paragraph" in missing["pinpoint"]["note"]
    page = tools.resolve_opinion(conn, "No. 22A-CT-925, at *4")
    assert page["pinpoint"]["exists"] is None and "official PDF" in page["pinpoint"]["note"]


def test_unknown_docket_is_not_found_and_says_so(tmp_path):
    out = tools.resolve_opinion(_db(tmp_path), "No. 99A-CR-1")
    assert out["found"] is False and out["flags"]


def test_history_comes_from_later_citations_and_is_labelled(tmp_path):
    out = tools.resolve_opinion(_db(tmp_path), "22A-CT-925")
    events = out["history"]["events"]
    assert [e["event"] for e in events] == ["trans. denied"]
    assert events[0]["seen_in"]["cluster_id"] == "2" and events[0]["seen_in"]["date_filed"] == "2024-05-01"
    note = out["history"]["note"].lower()
    assert "later opinions" in note and "not authoritative" in note and "docket" in note


def test_opinion_page_has_a_target_for_every_paragraph_so_fragments_jump(tmp_path):
    out = tools.resolve_opinion(_db(tmp_path), "22A-CT-925")
    html = web.opinion_html(out, OPINION)
    assert 'id="p1"' in html and 'id="p2"' in html and 'id="p3"' in html and 'id="p27"' not in html
    assert "<script" not in html.lower() and "Steele v. Taber" in html and "not legal advice" in html.lower()


def test_opinion_route_and_tool_are_wired(tmp_path):
    import asyncio

    from starlette.testclient import TestClient

    from indiana_law import mcp_server

    import sqlite3

    _db(tmp_path).close()
    conn = sqlite3.connect(str(tmp_path / "r.db"), check_same_thread=False)  # the test client serves requests on another thread
    conn.row_factory = sqlite3.Row
    mcp = mcp_server.build_server(conn)
    client = TestClient(mcp.streamable_http_app())
    page = client.get("/opinions/22A-CT-925")
    assert page.status_code == 200 and 'id="p2"' in page.text
    data = client.get("/opinions/22A-CT-925?format=json").json()
    assert data["cluster_id"] == "1" and data["history"]["events"][0]["event"] == "trans. denied"
    assert client.get("/opinions/99A-CR-1").status_code == 404
    tool = asyncio.run(mcp.call_tool("case_resolve", {"query": "No. 22A-CT-925, ¶ 2"}))
    assert "Steele v. Taber" in str(tool)
