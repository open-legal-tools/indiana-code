#!/usr/bin/env python3
"""
Indiana Law MCP Server

Exposes Indiana Code and Indiana appellate opinions as MCP tools.
All data is served from a local SQLite database — no live internet
calls at query time.

Configure your MCP client to run:
    python /path/to/indiana-law/src/mcp_server.py

Optional env var:
    INDIANA_LAW_DB=/path/to/indiana_law.db
"""

import asyncio
import sys
from pathlib import Path

# Allow running directly from src/ or project root
sys.path.insert(0, str(Path(__file__).parent))

import db
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
import mcp.types as types

app = Server("indiana-law")


# ─────────────────────────────────────────────
# TOOL REGISTRY
# ─────────────────────────────────────────────

@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [

        types.Tool(
            name="search_indiana_code",
            description=(
                "Full-text search of the Indiana Code (IC). Returns sections ranked by relevance "
                "using BM25 scoring. Supports terms-and-connectors: AND, OR, NOT, and phrase quotes. "
                "Example queries: 'custody modification', '\"best interests\" AND child', "
                "'termination NOT adoption'. "
                "Optionally narrow to a specific Title by providing title_num."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search terms. Supports AND, OR, NOT, phrase quotes.",
                    },
                    "title_num": {
                        "type": "integer",
                        "description": "Optional: restrict to a specific IC Title number (e.g. 31 for Family Law).",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max sections to return (default 10, max 50).",
                        "default": 10,
                    },
                },
                "required": ["query"],
            },
        ),

        types.Tool(
            name="get_section",
            description=(
                "Retrieve the full text of a specific Indiana Code section by citation. "
                "Accepts IC citation format: 'IC 31-14-5-3' (Title-Article-Chapter-Section). "
                "Returns the complete section text and a link to the official iga.in.gov source."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "citation": {
                        "type": "string",
                        "description": "IC citation, e.g. 'IC 31-14-5-3' or '31-14-5-3'.",
                    },
                },
                "required": ["citation"],
            },
        ),

        types.Tool(
            name="list_titles",
            description=(
                "List all titles in the Indiana Code with their names and section counts. "
                "Use this to browse the IC structure or find the correct Title number "
                "before using search_indiana_code with a title_num filter."
            ),
            inputSchema={"type": "object", "properties": {}},
        ),

        types.Tool(
            name="browse_chapter",
            description=(
                "Return all sections within a specific Indiana Code chapter in sequential order. "
                "Use after identifying the chapter via search or list_titles. "
                "Good for reading through a chapter in full."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "title_num":   {"type": "integer", "description": "IC Title number."},
                    "article_num": {"type": "integer", "description": "IC Article number."},
                    "chapter_num": {"type": "integer", "description": "IC Chapter number."},
                },
                "required": ["title_num", "article_num", "chapter_num"],
            },
        ),

        types.Tool(
            name="search_indiana_opinions",
            description=(
                "Full-text search of Indiana Supreme Court and Court of Appeals opinions. "
                "Supports AND, OR, NOT, phrase quotes. "
                "Filter by court: 'ind' (Supreme Court) or 'indctapp' (Court of Appeals). "
                "Filter by date range to find opinions from a specific period. "
                "Returns case name, court, date, author, and a text excerpt "
                "with a link to the full opinion on CourtListener."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search terms. Supports AND, OR, NOT, phrase quotes.",
                    },
                    "court": {
                        "type": "string",
                        "enum": ["ind", "indctapp", "indtc"],
                        "description": "Optional: 'ind' = Supreme Court, 'indctapp' = Court of Appeals, 'indtc' = Tax Court.",
                    },
                    "date_after": {
                        "type": "string",
                        "description": "Optional: ISO date YYYY-MM-DD. Return opinions filed after this date.",
                    },
                    "date_before": {
                        "type": "string",
                        "description": "Optional: ISO date YYYY-MM-DD. Return opinions filed before this date.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max opinions to return (default 10, max 50).",
                        "default": 10,
                    },
                },
                "required": ["query"],
            },
        ),

        types.Tool(
            name="get_opinion",
            description=(
                "Retrieve the full text of an Indiana appellate opinion by its CourtListener ID. "
                "Get the ID from search_indiana_opinions or recent_indiana_opinions results."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "opinion_id": {
                        "type": "integer",
                        "description": "CourtListener opinion ID (shown in search results).",
                    },
                },
                "required": ["opinion_id"],
            },
        ),

        types.Tool(
            name="recent_indiana_opinions",
            description=(
                "Return recently decided Indiana appellate opinions, newest first. "
                "Use for daily handdown review or to check what's been decided recently. "
                "Returns case name, court, date, author, and a CourtListener link. "
                "Optionally filter to a specific court."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "court": {
                        "type": "string",
                        "enum": ["ind", "indctapp", "indtc"],
                        "description": "Optional: filter to one court.",
                    },
                    "days": {
                        "type": "integer",
                        "description": "How many days back to look (default 30).",
                        "default": 30,
                    },
                },
            },
        ),

        types.Tool(
            name="search_indiana_law",
            description=(
                "Unified search across both the Indiana Code and Indiana appellate opinions in one call. "
                "Use when researching how courts have interpreted a statute, or when the question "
                "spans both statutory text and case law. Returns results from each source labeled separately."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search terms. Supports AND, OR, NOT, phrase quotes.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results per source (default 5 each, max 25).",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        ),

        types.Tool(
            name="indiana_law_status",
            description=(
                "Return the current state of the local Indiana law database: "
                "how many IC sections are loaded, how many opinions, the IC year, "
                "and when opinions were last synced from CourtListener. "
                "Use this to verify the database is populated before legal research."
            ),
            inputSchema={"type": "object", "properties": {}},
        ),

    ]


# ─────────────────────────────────────────────
# FORMATTERS
# ─────────────────────────────────────────────

def _fmt_section(s: dict, excerpt: bool = False) -> str:
    parts = [
        f"**{s['citation']}**",
        f"Title {s.get('title_num', '')}: {s.get('title_name', '')}",
    ]
    if s.get("chapter_name"):
        parts.append(f"Chapter: {s['chapter_name']}")
    if s.get("section_name"):
        parts.append(f"Section heading: {s['section_name']}")
    parts.append("")
    text = s.get("text", "")
    parts.append(text[:400] + "…" if excerpt and len(text) > 400 else text)
    if s.get("official_url"):
        parts.append(f"\n[Official source (iga.in.gov)]({s['official_url']})")
    return "\n".join(parts)


def _fmt_opinion(o: dict, full: bool = False) -> str:
    court_name = db.COURT_NAMES.get(o.get("court_id", ""), o.get("court_id", ""))
    author = o.get("author_str") or ("Per Curiam" if o.get("per_curiam") else "Unknown")
    parts = [
        f"**{o['case_name']}**",
        f"{court_name}  |  {o.get('date_filed', 'Date unknown')}  |  {author}",
        f"ID: {o['id']}  |  Type: {o.get('doc_type', 'opinion')}",
        "",
    ]
    if full:
        parts.append(o.get("plain_text", "") or "(No text available)")
    else:
        excerpt = o.get("excerpt") or (o.get("plain_text", "")[:600])
        parts.append(excerpt)
    if o.get("html_url"):
        parts.append(f"\n[Full opinion on CourtListener]({o['html_url']})")
    return "\n".join(parts)


# ─────────────────────────────────────────────
# DISPATCH
# ─────────────────────────────────────────────

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    try:
        if name == "search_indiana_code":
            results = db.search_code(
                arguments["query"],
                title_num=arguments.get("title_num"),
                limit=arguments.get("limit", 10),
            )
            if not results:
                return [types.TextContent(type="text", text="No matching Indiana Code sections found.")]
            header = f"**{len(results)} matching section(s)** for "{arguments['query']}"\n\n---\n\n"
            body = "\n\n---\n\n".join(_fmt_section(r) for r in results)
            return [types.TextContent(type="text", text=header + body)]

        elif name == "get_section":
            row = db.get_section(arguments["citation"])
            if not row:
                return [types.TextContent(type="text", text=f"Section not found: {arguments['citation']}")]
            return [types.TextContent(type="text", text=_fmt_section(row))]

        elif name == "list_titles":
            titles = db.list_titles()
            if not titles:
                return [types.TextContent(type="text", text=(
                    "No titles found. The database may not be bootstrapped yet.\n"
                    "Run: python scripts/bootstrap_code.py"
                ))]
            lines = ["**Indiana Code — Title Index**\n"]
            for t in titles:
                lines.append(f"Title {t['title_num']:>3}: {t['title_name']}  ({t['section_count']} sections)")
            return [types.TextContent(type="text", text="\n".join(lines))]

        elif name == "browse_chapter":
            sections = db.browse_chapter(
                arguments["title_num"],
                arguments["article_num"],
                arguments["chapter_num"],
            )
            if not sections:
                return [types.TextContent(type="text", text=(
                    f"No sections found in IC {arguments['title_num']}-{arguments['article_num']}-{arguments['chapter_num']}."
                ))]
            header = (
                f"**IC {arguments['title_num']}-{arguments['article_num']}-{arguments['chapter_num']}** "
                f"— {len(sections)} section(s)\n\n---\n\n"
            )
            body = "\n\n---\n\n".join(_fmt_section(s) for s in sections)
            return [types.TextContent(type="text", text=header + body)]

        elif name == "search_indiana_opinions":
            results = db.search_opinions(
                arguments["query"],
                court=arguments.get("court"),
                date_after=arguments.get("date_after"),
                date_before=arguments.get("date_before"),
                limit=arguments.get("limit", 10),
            )
            if not results:
                return [types.TextContent(type="text", text="No matching Indiana opinions found.")]
            header = f"**{len(results)} opinion(s)** matching "{arguments['query']}"\n\n---\n\n"
            body = "\n\n---\n\n".join(_fmt_opinion(r) for r in results)
            return [types.TextContent(type="text", text=header + body)]

        elif name == "get_opinion":
            row = db.get_opinion(arguments["opinion_id"])
            if not row:
                return [types.TextContent(type="text", text=f"Opinion not found: {arguments['opinion_id']}")]
            return [types.TextContent(type="text", text=_fmt_opinion(row, full=True))]

        elif name == "recent_indiana_opinions":
            days = arguments.get("days", 30)
            results = db.recent_opinions(court=arguments.get("court"), days=days)
            if not results:
                return [types.TextContent(type="text", text=f"No opinions in the last {days} days.")]
            court_label = arguments.get("court", "all courts")
            lines = [f"**Recent Indiana Opinions** — {court_label}, last {days} days\n"]
            for r in results:
                court_abbr = {"ind": "INSC", "indctapp": "INCA", "indtc": "INTC"}.get(r["court_id"], r["court_id"])
                per_curiam = " (per curiam)" if r.get("per_curiam") else ""
                author = f"  {r['author_str']}{per_curiam}" if r.get("author_str") else per_curiam
                lines.append(
                    f"[{r['date_filed']}] [{court_abbr}] {r['case_name']}{author}\n"
                    f"  ID: {r['id']}  |  {r.get('html_url', '')}"
                )
            return [types.TextContent(type="text", text="\n\n".join(lines))]

        elif name == "search_indiana_law":
            limit = min(arguments.get("limit", 5), 25)
            code_results    = db.search_code(arguments["query"], limit=limit)
            opinion_results = db.search_opinions(arguments["query"], limit=limit)

            parts = []
            if code_results:
                parts.append(
                    f"## Indiana Code ({len(code_results)} result(s))\n\n" +
                    "\n\n---\n\n".join(_fmt_section(r) for r in code_results)
                )
            else:
                parts.append("## Indiana Code\n\nNo matching sections.")

            if opinion_results:
                parts.append(
                    f"## Opinions ({len(opinion_results)} result(s))\n\n" +
                    "\n\n---\n\n".join(_fmt_opinion(r) for r in opinion_results)
                )
            else:
                parts.append("## Opinions\n\nNo matching opinions.")

            return [types.TextContent(type="text", text="\n\n═══\n\n".join(parts))]

        elif name == "indiana_law_status":
            stats = db.db_stats()
            lines = [
                "**Indiana Law Database — Status**\n",
                f"Indiana Code sections: {stats['ic_sections']:,}  (year: {stats['ic_year']})",
                f"Appellate opinions:    {stats['opinions']:,}",
                f"Last opinion sync:     {stats['last_opinion_sync']}",
                "",
            ]
            if stats["ic_sections"] == 0:
                lines.append("⚠  Indiana Code not loaded. Run: python scripts/bootstrap_code.py")
            if stats["opinions"] == 0:
                lines.append("⚠  Opinions not loaded. Run: python scripts/bootstrap_opinions.py")
            return [types.TextContent(type="text", text="\n".join(lines))]

        else:
            return [types.TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as e:
        return [types.TextContent(type="text", text=f"Error in {name}: {e}")]


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────

async def _main() -> None:
    from mcp.server.lowlevel import NotificationOptions
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="indiana-law",
                server_version="0.1.0",
                capabilities=app.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(_main())
