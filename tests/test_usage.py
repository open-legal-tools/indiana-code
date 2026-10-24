import asyncio
import sqlite3
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from indiana_law import usage


def _server(counter):
    mcp = FastMCP("t")
    usage.count_tools(mcp, counter)

    @mcp.tool()
    def ok_tool(secret_query: str) -> dict:
        return {"echo": 1}

    @mcp.tool()
    def bad_tool() -> dict:
        raise ValueError("boom")

    return mcp


def _rows(path: Path):
    return sqlite3.connect(path).execute("SELECT tool, calls, errors FROM usage ORDER BY tool").fetchall()


def test_counts_calls_and_errors_per_tool_without_storing_arguments(tmp_path: Path):
    db = tmp_path / "usage.sqlite"
    mcp = _server(usage.UsageCounter(str(db)))
    asyncio.run(mcp.call_tool("ok_tool", {"secret_query": "my client's name"}))
    asyncio.run(mcp.call_tool("ok_tool", {"secret_query": "another"}))
    try:
        asyncio.run(mcp.call_tool("bad_tool", {}))
    except Exception:
        pass
    assert _rows(db) == [("bad_tool", 1, 1), ("ok_tool", 2, 0)]
    raw = db.read_bytes()
    assert b"my client" not in raw and b"another" not in raw


def test_off_unless_env_var_set(tmp_path: Path, monkeypatch):
    monkeypatch.delenv(usage.ENV_VAR, raising=False)
    assert usage.from_env() is None
    mcp = _server(None)
    asyncio.run(mcp.call_tool("ok_tool", {"secret_query": "x"}))
    assert list(tmp_path.iterdir()) == []
    monkeypatch.setenv(usage.ENV_VAR, str(tmp_path / "u.sqlite"))
    assert usage.from_env() is not None


def test_counting_failure_never_breaks_a_tool():
    class Broken:
        def record(self, tool, ok):
            raise RuntimeError("disk full")

    mcp = _server(Broken())
    result = asyncio.run(mcp.call_tool("ok_tool", {"secret_query": "x"}))
    assert result
