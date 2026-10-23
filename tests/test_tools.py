import asyncio

from indiana_law import tools
from indiana_law.mcp_server import build_server


def test_search_dedupes_versions_and_returns_snippets(mini):
    r = tools.search(mini, "commission meet")
    ids = [x["section_id"] for x in r["results"]]
    assert "2-5-36-9" in ids and len(ids) == len(set(ids))
    assert r["unofficial"] and r["snapshot_year"] == 2026
    assert tools.search(mini, "")["flags"] == ["empty query"]
    assert tools.search(mini, 'a "quoted" OR (weird')["results"] == []  # FTS syntax in user text must not raise


def test_search_title_filter_and_as_of(mini):
    assert tools.search(mini, "commission", title="2")["results"]
    assert not tools.search(mini, "commission", title="99")["results"]
    r = tools.search(mini, "commission", as_of="2025-12-01")
    assert r["snapshot_year"] == 2025


def test_resolve_citation_with_nearby(mini):
    r = tools.resolve_citation(mini, "See IC 2-5-36-1 and Ind. Code § 2-5-36-99 (2026).")
    by = {c["section_id"]: c for c in r["citations"]}
    assert by["2-5-36-1"]["exists_in_latest_snapshot"] and by["2-5-36-1"]["heading"] == "Definitions"
    assert not by["2-5-36-99"]["exists_in_latest_snapshot"] and "2-5-36-1" in by["2-5-36-99"]["nearby_sections"]
    assert "flags" in tools.resolve_citation(mini, "no cite here")


def test_get_section_accepts_citation_forms(mini):
    r = tools.get_section(mini, "IC 2-5-36-1", "2026-09-01")
    assert r["found"] and r["citation"] == "IC 2-5-36-1" and r["disclaimer"]


def test_versions_and_act(mini):
    v = tools.get_versions(mini, "2-5-36-9")
    assert [x["version_suffix"] for x in v["versions"]] == [None, "b"] or {x["version_suffix"] for x in v["versions"]} == {None, "b"}
    assert any(c["act_id"] == "P.L.20-2026" for c in v["act_clauses"])
    a = tools.get_act(mini, "P.L. 20-2026")
    assert a["found"] and a["bill"] == "S.212" and len(a["clauses"]) >= 4
    assert not tools.get_act(mini, "P.L.999-2026")["found"]
    page = tools.get_act(mini, "P.L.20-2026", limit=2, offset=0)
    assert len(page["clauses"]) == 2 and page["total_clauses"] >= 4 and "offset=2" in page["flags"][0]


def test_browse_levels(mini):
    assert tools.browse(mini)["children"][0]["node_id"] == "2"
    assert tools.browse(mini, "2")["children"][0]["node_id"] == "2-5"
    assert tools.browse(mini, "2-5")["children"][0]["node_id"] == "2-5-36"
    secs = [c["node_id"] for c in tools.browse(mini, "2-5-36")["children"]]
    assert secs[0] == "2-5-36-1" and "2-5-36-11.5" in secs
    assert "leaf" in tools.browse(mini, "2-5-36-1")["flags"][0]


def test_server_lists_read_only_tools_with_schemas(mini):
    mcp = build_server(mini)
    listed = asyncio.run(mcp.list_tools())
    names = {t.name for t in listed}
    assert names == {
        "ic_search", "ic_resolve_citation", "ic_get_section", "ic_get_versions", "ic_browse", "ic_get_act",
            "ic_list_companion", "ic_search_companion", "ic_get_companion",
            "case_search", "case_get", "ic_cases_citing",
            "cases_citing_case", "cases_cited_in",
    }
    for t in listed:
        assert t.title and t.annotations.readOnlyHint is True and t.annotations.openWorldHint is False
        assert t.inputSchema and len(t.name) <= 64
        assert t.outputSchema, t.name  # structured output is declared


def test_server_call_returns_structured_content(mini):
    mcp = build_server(mini)
    content, structured = asyncio.run(mcp.call_tool("ic_get_section", {"section_id": "2-5-36-1", "as_of": "2026-09-01"}))
    assert structured["found"] is True and structured["unofficial"] is True
    assert content and "2-5-36-1" in content[0].text


def test_search_falls_back_to_any_word(mini):
    r = tools.search(mini, "commission quarterly xylophone")
    assert r["results"] and any("some of the words" in f for f in r["flags"])
    r2 = tools.search(mini, "commission quarterly")
    assert not any("some of the words" in f for f in r2["flags"])
    assert not tools.search(mini, "xylophone zebra")["results"]


def test_companion_empty_store(mini):
    empty = tools.list_companion(mini)
    assert empty["documents"] == [] and empty["flags"]


def test_companion_search_and_get(mini):
    from indiana_law import store
    pages = [
        {"doc_id": "constitution-2026", "kind": "constitution", "year": 2026, "title": "Indiana Constitution (2026)",
         "source_file": "Indiana_Constitution.pdf", "page": 1, "text": "We the People of the State of Indiana bill of rights"},
        {"doc_id": "noncode-2026", "kind": "noncode", "year": 2026, "title": "Non-code (2026)",
         "source_file": "2026_Noncode_Statutes.pdf", "page": 1, "text": "A special appropriation for a named county bridge"},
    ]
    store.add_companion_pages(mini, pages)
    store.finalize_companion(mini)
    listed = tools.list_companion(mini, kind="constitution")
    assert listed["documents"][0]["doc_id"] == "constitution-2026"
    hits = tools.search_companion(mini, "bill of rights")
    assert hits["results"] and hits["results"][0]["doc_id"] == "constitution-2026"
    page = tools.get_companion(mini, "constitution-2026", 1)
    assert page["found"] and "Indiana" in page["text"]
