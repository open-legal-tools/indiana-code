import csv
import os
import re

import pytest

CSV = os.path.join(os.path.dirname(__file__), "..", "mappings", "title_area_of_law.csv")
OWL = os.environ.get("LMSS_OWL", "")


def rows():
    with open(CSV, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_every_row_is_either_mapped_or_marked_none():
    for r in rows():
        if r["match"] == "none":
            assert not r["lmss_iri"]
        else:
            assert re.fullmatch(r"http://lmss\.sali\.org/R[A-Za-z0-9]+", r["lmss_iri"]), r
            assert r["role"] in ("primary", "secondary")
            assert r["match"] in ("exact", "close", "approximate")


def test_each_title_has_at_most_one_primary_and_all_are_listed():
    by = {}
    for r in rows():
        by.setdefault(r["title_id"], []).append(r)
    assert len(by) == 34
    for tid, rs in by.items():
        assert sum(1 for r in rs if r["role"] == "primary") <= 1, tid


@pytest.mark.skipif(not (OWL and os.path.exists(OWL)), reason="set LMSS_OWL to the LMSS.owl path to verify IRIs")
def test_iris_exist_in_the_ontology_file():
    text = open(OWL, encoding="utf-8").read()
    for r in rows():
        if r["lmss_iri"]:
            assert f'rdf:about="{r["lmss_iri"]}"' in text, r["lmss_iri"]
