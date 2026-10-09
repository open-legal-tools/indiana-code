import os
import pytest
from indiana_law import acts, asof, store
from indiana_law.parse_code import parse_title_html

FIXD = os.path.join(os.path.dirname(__file__), "fixtures")


def load_records(snapshot_id):
    with open(os.path.join(FIXD, "title_sample.html"), encoding="utf-8") as fh:
        out = []
        for r in parse_title_html(fh.read(), "2.html"):
            r["snapshot_id"] = snapshot_id
            out.append(r)
    return out


@pytest.fixture()
def conn(tmp_path):
    c = store.connect(str(tmp_path / "t.db"))
    store.add_snapshot(c, "2025-06-30", 2025, "2025-06-30")
    store.add_snapshot(c, "2026-06-23", 2026, "2026-06-23")
    # 2025 snapshot: only the quarterly version, no 2026 amendment of 2-5-36-11.5
    recs25 = [r for r in load_records("2025-06-30") if r["id"] in ("2-5-36-1", "2-5-36-9", "2-5-36-9-b", "2-5-36-11.5")]
    for r in recs25:
        if r["id"] == "2-5-36-11.5":
            r["text"] = r["text"].replace("annually", "every other year")  # pre-amendment wording
    store.add_records(c, recs25)
    store.add_records(c, load_records("2026-06-23"))
    with open(os.path.join(FIXD, "acts_sample.txt"), encoding="utf-8") as fh:
        store.add_clauses(c, acts.parse_acts_text(fh.read(), 2026))
    store.finalize(c)
    return c


def test_identical_versions_are_stored_once(conn):
    n_apps = conn.execute("SELECT count(*) FROM appearance").fetchone()[0]
    n_ver = conn.execute("SELECT count(*) FROM section_version").fetchone()[0]
    assert n_apps > n_ver  # 2-5-36-1 appears in both snapshots with one version row
    assert conn.execute("SELECT count(*) FROM appearance a JOIN section_version v ON v.vid=a.vid WHERE v.id='2-5-36-1'").fetchone()[0] == 2


def test_after_july_first_uses_snapshot_of_that_year(conn):
    r = asof.resolve(conn, "2-5-36-9", "2026-08-01")
    assert r["found"] and r["snapshot_year"] == 2026 and r["version_id"] == "2-5-36-9"
    assert r["effective_until"] == "2027-07-01" and "quarterly" in r["text"]
    assert r["pending_acts"] and r["pending_acts"][0]["effective_date"] == "2027-07-01"


def test_dated_version_becomes_operative(conn):
    r = asof.resolve(conn, "2-5-36-9", "2027-07-02")
    assert r["version_id"] == "2-5-36-9-b" and "monthly" in r["text"]
    assert r["confidence"] in ("low", "high", "medium")


def test_before_july_all_clauses_not_yet_effective_uses_prior_snapshot(conn):
    # 2-5-36-9 has session-2026 clauses effective 2026-07-01 and 2027-07-01, both after 2026-03-01 -> use 2025 file
    r = asof.resolve(conn, "2-5-36-9", "2026-03-01")
    assert r["found"] and r["snapshot_year"] == 2025 and r["confidence"] == "high"


def test_before_july_all_clauses_effective_uses_current_snapshot(conn):
    r = asof.resolve(conn, "2-5-36-11.5", "2026-04-01")  # clause effective 2026-03-03
    assert r["snapshot_year"] == 2026 and r["confidence"] == "high"


def test_mixed_clauses_are_ambiguous(conn):
    # make a mixed case: add a clause effective before and one after the date for the same section
    conn.execute("INSERT INTO act_clause VALUES ('P.L.20-2026',9,'amend','2-5-36-1','section','2026-02-01','stated',0)")
    conn.execute("INSERT INTO act_clause VALUES ('P.L.20-2026',10,'amend','2-5-36-1','section','2026-07-01','stated',0)")
    r = asof.resolve(conn, "2-5-36-1", "2026-03-01")
    assert r["confidence"] == "ambiguous" and not r["found"] and any("partial" in f for f in r["flags"])


def test_repealed_and_missing_sections(conn):
    r = asof.resolve(conn, "2-5-36-10", "2026-09-01")
    assert r["found"] and r["status"] == "repealed" and any("repealed" in f for f in r["flags"])
    r = asof.resolve(conn, "9-9-9-9", "2026-09-01")
    assert not r["found"] and r["unofficial"] and r["disclaimer"]


def test_date_before_earliest_and_after_latest(conn):
    assert not asof.resolve(conn, "2-5-36-1", "2010-01-01")["found"]
    r = asof.resolve(conn, "2-5-36-1", "2030-01-01")
    assert r["found"] and r["confidence"] == "low" and any("after the latest snapshot" in f for f in r["flags"])


def test_normalize_citation():
    assert asof.normalize_citation("see IC 31-16-15-25 and I.C. § 7.1-3-1.5-2 and Ind. Code § 35-42-1-1 (2024)") == [
        "31-16-15-25", "7.1-3-1.5-2", "35-42-1-1"]
    assert asof.normalize_citation("31‐16‐15‐25") == ["31-16-15-25"]


def test_search_returns_snippets(conn):
    hits = asof.search(conn, "commission quarterly", "2026-06-23")
    assert hits and hits[0]["base_id"] == "2-5-36-9" and "[" in hits[0]["snip"]
