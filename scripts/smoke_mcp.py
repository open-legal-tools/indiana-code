"""Smoke test and size check: start the local MCP server over stdio and ask it research-style questions.
usage: INDIANA_LAW_DB=data/store/indiana-code.db PYTHONPATH=src python scripts/smoke_mcp.py"""
import asyncio
import json
import os
import sys
import time

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

QUESTIONS = [
    ("search", "ic_search", {"query": "statute of limitations personal injury two years", "limit": 5}),
    ("search in title", "ic_search", {"query": "income withholding order", "title": "31", "limit": 5}),
    ("search topic", "ic_search", {"query": "expungement of arrest records", "limit": 5}),
    ("resolve", "ic_resolve_citation", {"text": "See I.C. § 7.1-5-1-1 and Ind. Code § 35-42-4-1 (2024), also IC 99-1-1-1."}),
    ("get section today", "ic_get_section", {"section_id": "35-42-4-1"}),
    ("get section by date", "ic_get_section", {"section_id": "6-3.6-3-5", "as_of": "2026-03-01"}),
    ("get section later date", "ic_get_section", {"section_id": "6-3.6-3-5", "as_of": "2027-07-02"}),
    ("ambiguous date", "ic_get_section", {"section_id": "3-11-13-11", "as_of": "2026-03-01"}),
    ("versions", "ic_get_versions", {"section_id": "6-3.6-3-5"}),
    ("browse titles", "ic_browse", {}),
    ("browse chapters", "ic_browse", {"node_id": "31-16"}),
    ("act", "ic_get_act", {"act_id": "P.L.98-2026"}),
    ("cases citing", "ic_cases_citing", {"section_id": "35-42-1-1", "limit": 5}),
]


async def main():
    params = StdioServerParameters(command=sys.executable, args=["-m", "indiana_law.mcp_server"], env=dict(os.environ))
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = await s.list_tools()
            print("tools:", [t.name for t in tools.tools])
            for label, name, args in QUESTIONS:
                t0 = time.time()
                res = await s.call_tool(name, args)
                dt = time.time() - t0
                data = res.structuredContent or {}
                size = sum(len(c.text) for c in res.content if getattr(c, "text", None))
                brief = ""
                if name == "ic_search":
                    brief = [x["citation"] + " " + (x["heading"] or "")[:30] for x in data.get("results", [])[:3]]
                elif name == "ic_get_section":
                    brief = {k: data.get(k) for k in ("found", "snapshot_year", "version_id", "confidence", "effective_from", "effective_until")}
                    brief["flags"] = data.get("flags", [])[:1]
                elif name == "ic_resolve_citation":
                    brief = [(c["section_id"], c["exists_in_latest_snapshot"]) for c in data.get("citations", [])]
                elif name == "ic_get_versions":
                    brief = [(v["version_id"], v["effective_from"], v["effective_until"], len(v["snapshot_years"])) for v in data.get("versions", [])]
                elif name == "ic_browse":
                    brief = [c["node_id"] for c in data.get("children", [])[:6]] + ["... %d children" % len(data.get("children", []))]
                elif name == "ic_get_act":
                    brief = {"found": data.get("found"), "clauses": len(data.get("clauses", []))}
                print(f"{label:22} {name:20} {size:6d} chars (~{size // 4} tokens) {dt * 1000:6.0f} ms  {brief}")


asyncio.run(main())
