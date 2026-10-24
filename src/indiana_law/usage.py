"""Optional usage counts: calls and errors per tool per UTC day, and nothing else.

Off unless INDIANA_LAW_USAGE_DB names a file. No IP addresses, queries, arguments, results or session ids are
recorded or even seen by this module, so the numbers are totals that cannot identify anyone. Counting can never
break a tool: any failure to write a count is swallowed.

Read the totals with:  python -m indiana_law.usage /path/to/usage.sqlite
"""
from __future__ import annotations

import datetime as dt
import functools
import inspect
import os
import sqlite3
import sys
import threading

ENV_VAR = "INDIANA_LAW_USAGE_DB"


class UsageCounter:
    def __init__(self, path: str):
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock, self._conn:
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS usage (day TEXT, tool TEXT, calls INTEGER NOT NULL DEFAULT 0, "
                "errors INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (day, tool))"
            )

    def record(self, tool: str, ok: bool) -> None:
        day = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO usage (day, tool, calls, errors) VALUES (?, ?, 1, ?) "
                "ON CONFLICT(day, tool) DO UPDATE SET calls = calls + 1, errors = errors + excluded.errors",
                (day, tool, 0 if ok else 1),
            )


def from_env() -> UsageCounter | None:
    path = os.environ.get(ENV_VAR)
    return UsageCounter(path) if path else None


def count_tools(mcp, counter: UsageCounter | None) -> None:
    """Make every tool registered on `mcp` afterwards add one count per call. Does nothing when counter is None."""
    if counter is None:
        return
    register = mcp.tool

    def safe_record(name: str, ok: bool) -> None:
        try:
            counter.record(name, ok)
        except Exception:
            pass

    def tool(*args, **kwargs):
        decorate = register(*args, **kwargs)

        def wrap(fn):
            name = kwargs.get("name") or fn.__name__
            if inspect.iscoroutinefunction(fn):
                @functools.wraps(fn)
                async def counted(*a, **k):
                    try:
                        result = await fn(*a, **k)
                    except Exception:
                        safe_record(name, False)
                        raise
                    safe_record(name, True)
                    return result
            else:
                @functools.wraps(fn)
                def counted(*a, **k):
                    try:
                        result = fn(*a, **k)
                    except Exception:
                        safe_record(name, False)
                        raise
                    safe_record(name, True)
                    return result
            return decorate(counted)

        return wrap

    mcp.tool = tool


def report(path: str) -> list[tuple[str, str, int, int]]:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    return conn.execute("SELECT day, tool, calls, errors FROM usage ORDER BY day, tool").fetchall()


def main(argv: list[str] | None = None) -> None:
    args = list(argv if argv is not None else sys.argv[1:])
    if len(args) != 1:
        sys.exit("usage: python -m indiana_law.usage /path/to/usage.sqlite")
    rows = report(args[0])
    totals: dict[str, int] = {}
    for day, tool, calls, errors in rows:
        print(f"{day}  {tool:<24} calls={calls} errors={errors}")
        totals[tool] = totals.get(tool, 0) + calls
    print("\nTotals by tool:", ", ".join(f"{t}={n}" for t, n in sorted(totals.items())) or "none yet")
    print("All calls:", sum(totals.values()))


if __name__ == "__main__":
    main()
