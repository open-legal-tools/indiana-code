import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
FIXD = os.path.join(os.path.dirname(__file__), "fixtures")


def _records(snapshot_id):
    from indiana_law.parse_code import parse_title_html
    with open(os.path.join(FIXD, "title_sample.html"), encoding="utf-8") as fh:
        out = []
        for r in parse_title_html(fh.read(), "2.html"):
            r["snapshot_id"] = snapshot_id
            out.append(r)
    return out


@pytest.fixture()
def mini(tmp_path):
    """A two-snapshot store (2025 and 2026) with the fixture title and acts."""
    from indiana_law import acts, store
    c = store.connect(str(tmp_path / "mini.db"))
    store.add_snapshot(c, "2025-06-30", 2025, "2025-06-30")
    store.add_snapshot(c, "2026-06-23", 2026, "2026-06-23")
    recs25 = [r for r in _records("2025-06-30") if r["id"] in ("2-5-36-1", "2-5-36-9", "2-5-36-9-b", "2-5-36-11.5")]
    for r in recs25:
        if r["id"] == "2-5-36-11.5":
            r["text"] = r["text"].replace("annually", "every other year")
    store.add_records(c, recs25)
    store.add_records(c, _records("2026-06-23"))
    with open(os.path.join(FIXD, "acts_sample.txt"), encoding="utf-8") as fh:
        store.add_clauses(c, acts.parse_acts_text(fh.read(), 2026))
    store.finalize(c)
    return c
