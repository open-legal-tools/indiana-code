"""Optional checks against a locally built store (skipped when the store is absent)."""
import os
import sqlite3

import pytest
from indiana_law import asof

DB = os.environ.get("INDIANA_LAW_DB", os.path.join(os.path.dirname(__file__), "..", "data", "store", "indiana-code.db"))
pytestmark = pytest.mark.skipif(not os.path.exists(DB), reason="local store not built")


@pytest.fixture(scope="module")
def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def test_every_snapshot_loaded(conn):
    years = [r[0] for r in conn.execute("SELECT year FROM snapshot ORDER BY year")]
    assert years == list(range(2017, 2027))


def test_dated_version_chain_has_no_gaps_or_overlaps(conn):
    rows = conn.execute("SELECT v.* FROM section_version v JOIN appearance a ON a.vid=v.vid WHERE a.snapshot_id='2026-06-23'").fetchall()
    fam = {}
    for r in rows:
        fam.setdefault(r["base_id"], []).append(r)
    for vs in fam.values():
        vs.sort(key=lambda r: r["version_suffix"] or "")
        for a, b in zip(vs, vs[1:]):
            if a["effective_until"] and b["effective_from"]:
                assert a["effective_until"] == b["effective_from"]


def test_known_dated_section_resolves_by_date(conn):
    r1 = asof.resolve(conn, "6-3.6-3-5", "2026-09-01")
    r2 = asof.resolve(conn, "6-3.6-3-5", "2027-07-02")
    assert r1["found"] and r1["effective_until"] == "2027-07-01"
    assert r2["found"] and r2["version_id"] == "6-3.6-3-5-b"
