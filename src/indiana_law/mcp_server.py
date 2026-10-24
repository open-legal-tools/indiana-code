"""Local, read-only MCP server (stdio by default) over the Indiana Code store. Unofficial; not legal advice.

Run:  INDIANA_LAW_DB=/path/to/indiana-code.db PYTHONPATH=src python -m indiana_law.mcp_server
"""
import os
import sqlite3
import sys
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from . import tools, usage

INSTRUCTIONS = (
    "Dated, unofficial copies of the Indiana Code from the General Assembly's annual downloads (2017 to 2026), with effective-dated "
    "versions and the acts that amended each section. Section ids look like '31-16-15-25' (title-article-chapter-section; decimals "
    "such as '7.1-1-1-1' are normal). Use ic_search to find sections, ic_resolve_citation for citation strings, ic_get_section for text "
    "as of a date, ic_get_versions for history, ic_browse to explore, ic_get_act for what a public law changed. Companion PDFs from the "
    "same downloads page (Constitution, Non-code statutes, full Acts text, optional pre-2017 archive titles) use ic_list_companion, "
    "ic_search_companion and ic_get_companion when loaded. Every answer includes its snapshot, dates and flags. Always show the user "
    "the source date and say the copy is unofficial; this tool provides no legal advice."
)


def _connect():
    path = os.environ.get("INDIANA_LAW_DB", "")
    if not path or not os.path.exists(path):
        sys.exit("Set INDIANA_LAW_DB to the path of a built indiana-code.db store.")
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def build_server(conn=None, host: str = "127.0.0.1", port: int = 8765):
    mcp = FastMCP(
        "indiana-code",
        instructions=INSTRUCTIONS,
        host=host,
        port=port,
        stateless_http=True,
        json_response=True,
    )
    db = conn or _connect()
    usage.count_tools(mcp, usage.from_env())
    ro = dict(readOnlyHint=True, idempotentHint=True, openWorldHint=False, destructiveHint=False)

    @mcp.tool(title="Search Indiana Code", annotations=ToolAnnotations(title="Search Indiana Code", **ro))
    def ic_search(query: str, as_of: str | None = None, title: str | None = None, limit: int = 10) -> dict[str, Any]:
        """Full-text search of Indiana Code sections. Returns section ids, headings and short snippets (one hit per section); fetch the text
        with ic_get_section. `as_of` (YYYY-MM-DD) picks the year's snapshot; `title` limits to one title number such as '31' or '7.1'."""
        return tools.search(db, query, as_of, title, limit)

    @mcp.tool(title="Resolve Indiana Code citation", annotations=ToolAnnotations(title="Resolve Indiana Code citation", **ro))
    def ic_resolve_citation(text: str) -> dict[str, Any]:
        """Find Indiana Code citations in free text ('IC 31-16-15-25', 'I.C. § 7.1-1-1-1', 'Ind. Code § 35-42-1-1 (2024)') and return canonical
        section ids, headings, and nearby sections when an id does not exist."""
        return tools.resolve_citation(db, text)

    @mcp.tool(title="Get Indiana Code section as of a date", annotations=ToolAnnotations(title="Get Indiana Code section as of a date", **ro))
    def ic_get_section(section_id: str, as_of: str | None = None) -> dict[str, Any]:
        """Text of one section, e.g. section_id '31-16-15-25', as of a date (YYYY-MM-DD, default today). Returns the version in force with
        effective dates, amending acts, acts that take effect later (pending_acts), a confidence level and flags. Check `flags` and
        `confidence` before relying on a date between January and June."""
        return tools.get_section(db, section_id, as_of)

    @mcp.tool(title="List versions of an Indiana Code section", annotations=ToolAnnotations(title="List versions of an Indiana Code section", **ro))
    def ic_get_versions(section_id: str) -> dict[str, Any]:
        """All distinct versions of a section across 2017 to 2026 with effective dates, the years each appeared in, and the act clauses that touch it."""
        return tools.get_versions(db, section_id)

    @mcp.tool(title="Browse the Indiana Code outline", annotations=ToolAnnotations(title="Browse the Indiana Code outline", **ro))
    def ic_browse(node_id: str | None = None) -> dict[str, Any]:
        """Outline of the Code. With no node_id, list titles; with '31' list articles; with '31-16' chapters; with '31-16-15' sections (latest snapshot)."""
        return tools.browse(db, node_id)

    @mcp.tool(title="Get an Indiana public law's code changes", annotations=ToolAnnotations(title="Get an Indiana public law's code changes", **ro))
    def ic_get_act(act_id: str, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        """The Code sections an act amended, added or repealed, with effective dates. act_id like 'P.L.98-2026' (loaded for 2017 and 2019 to 2026). Long acts are paged with limit and offset."""
        return tools.get_act(db, act_id, limit, offset)

    @mcp.tool(title="List companion IGA documents", annotations=ToolAnnotations(title="List companion IGA documents", **ro))
    def ic_list_companion(kind: str | None = None, year: int | None = None) -> dict[str, Any]:
        """List Constitution, Non-code, full Acts, and archive-title PDFs loaded from the IGA downloads page. kind is constitution, noncode, acts, or archive_title."""
        return tools.list_companion(db, kind, year)

    @mcp.tool(title="Search companion IGA documents", annotations=ToolAnnotations(title="Search companion IGA documents", **ro))
    def ic_search_companion(query: str, kind: str | None = None, year: int | None = None, limit: int = 10) -> dict[str, Any]:
        """Full-text search of companion PDFs (Constitution, Non-code statutes, full Acts text, archive titles). Use ic_get_companion for a page."""
        return tools.search_companion(db, query, kind, year, limit)

    @mcp.tool(title="Get a companion document page", annotations=ToolAnnotations(title="Get a companion document page", **ro))
    def ic_get_companion(doc_id: str, page: int = 1) -> dict[str, Any]:
        """One page of a companion document (doc_id like 'constitution-2026' or 'acts-2026'). Pages are 1-based."""
        return tools.get_companion(db, doc_id, page)

    return mcp


def main(argv: list[str] | None = None) -> None:
    args = list(argv if argv is not None else sys.argv[1:])
    transport = os.environ.get("INDIANA_LAW_TRANSPORT", "stdio")
    if "--http" in args:
        transport = "streamable-http"
    host = os.environ.get("INDIANA_LAW_HOST", "127.0.0.1")
    port = int(os.environ.get("INDIANA_LAW_PORT", "8765"))
    if transport not in {"stdio", "streamable-http", "sse"}:
        sys.exit(f"Unknown INDIANA_LAW_TRANSPORT={transport!r} (use stdio or streamable-http)")
    build_server(host=host, port=port).run(transport=transport)


if __name__ == "__main__":
    main()
