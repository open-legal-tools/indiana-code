"""Build mappings/title_area_of_law.csv: Indiana Code titles -> SALI LMSS Area of Law classes (hand-curated judgments).

usage: python scripts/make_title_map.py /path/to/LMSS.owl mappings/title_area_of_law.csv
Every label is resolved against the OWL file, so a mistyped or renamed class fails loudly. Matches are judgments, not facts:
`match` is exact, close, approximate or none. LMSS `main` is unfinalized, so the OWL file's SHA-256 is recorded.
"""
import csv
import datetime
import hashlib
import sys
import xml.etree.ElementTree as ET

NS = {"owl": "http://www.w3.org/2002/07/owl#", "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#", "rdfs": "http://www.w3.org/2000/01/rdf-schema#"}
A, R = "{%s}about" % NS["rdf"], "{%s}resource" % NS["rdf"]

# title_id -> (heading, [(role, label, match, note)])
TITLES = {
    "1": ("General Provisions", []),
    "2": ("General Assembly", [("primary", "Public and Administrative Law", "approximate", "legislative organization")]),
    "3": ("Elections", [("primary", "Election Law", "exact", "")]),
    "4": ("State Offices and Administration", [("primary", "Public and Administrative Law", "approximate", "")]),
    "5": ("State and Local Administration", [("primary", "Public and Administrative Law", "approximate", ""), ("secondary", "Municipal Law", "approximate", "local portions")]),
    "6": ("Taxation", [("primary", "Tax and Revenue Law", "exact", "")]),
    "7.1": ("Alcohol and Tobacco", []),
    "8": ("Utilities and Transportation", [("primary", "Transportation Law", "approximate", "transportation half"), ("secondary", "Energy Law", "approximate", "utilities half")]),
    "9": ("Motor Vehicles", [("primary", "Motor Vehicle Law", "exact", "")]),
    "10": ("Public Safety", [("primary", "Public and Administrative Law", "approximate", "")]),
    "11": ("Corrections", [("primary", "Prison Law", "approximate", "")]),
    "12": ("Human Services", [("primary", "Public Health and Welfare Law", "approximate", "")]),
    "13": ("Environment", [("primary", "Environmental and Natural Resource Law", "exact", "")]),
    "14": ("Natural and Cultural Resources", [("primary", "Environmental and Natural Resource Law", "approximate", "")]),
    "15": ("Agriculture and Animals", [("primary", "Agriculture Law", "close", "animals portion not separately classed")]),
    "16": ("Health", [("primary", "Health Law", "exact", "")]),
    "20": ("Education", [("primary", "Education Law", "exact", "")]),
    "21": ("Higher Education", [("primary", "Education Law", "close", "")]),
    "22": ("Labor and Safety", [("primary", "Labor and Employment Law", "exact", ""), ("secondary", "Employment Health and Safety Law", "close", "")]),
    "23": ("Business and Other Associations", [("primary", "Business Organizations Law", "close", ""), ("secondary", "Corporate Law", "close", "")]),
    "24": ("Trade Regulation", [("primary", "Commercial and Trade Law", "approximate", ""), ("secondary", "Consumer Protection Law", "approximate", "")]),
    "25": ("Professions and Occupations", []),
    "26": ("Commercial Law", [("primary", "Commercial Transactions Law", "close", "")]),
    "27": ("Insurance", [("primary", "Insurance Law", "exact", "")]),
    "28": ("Financial Institutions", [("primary", "Banking Law", "close", ""), ("secondary", "Finance and Lending Law", "approximate", "")]),
    "29": ("Probate", [("primary", "Probate Law", "exact", "")]),
    "30": ("Trusts and Fiduciaries", [("primary", "Trusts and Estate Planning Law", "close", "")]),
    "31": ("Family Law and Juvenile Law", [("primary", "Personal and Family Law", "exact", ""), ("secondary", "Juvenile Law", "exact", "")]),
    "32": ("Property", [("primary", "Real Property Law", "close", "title also covers personal property"), ("secondary", "Personal Property Law", "close", "")]),
    "33": ("Courts and Court Officers", []),
    "34": ("Civil Law and Procedure", []),
    "35": ("Criminal Law and Procedure", [("primary", "Criminal Law", "exact", "procedure portion is not separately classed")]),
    "36": ("Local Government", [("primary", "Municipal Law", "close", "")]),
    "37": ("Consumer Lending", [("primary", "Finance and Lending Law", "close", ""), ("secondary", "Consumer Protection Law", "close", "")]),
}


def load_area_of_law(path):
    cls = {}
    for _, el in ET.iterparse(path, events=("end",)):
        if el.tag == "{%s}Class" % NS["owl"] and el.get(A):
            lab = el.find("rdfs:label", NS)
            cls[el.get(A)] = {"label": lab.text if lab is not None else "", "parents": [p.get(R) for p in el.findall("rdfs:subClassOf", NS) if p.get(R)]}
            el.clear()
    root = next(i for i, c in cls.items() if c["label"] == "Area of Law")
    kids = {}
    for i, c in cls.items():
        for p in c["parents"]:
            kids.setdefault(p, []).append(i)
    depth, queue = {root: 0}, [root]
    while queue:
        x = queue.pop(0)
        for k in kids.get(x, []):
            if k not in depth:
                depth[k] = depth[x] + 1
                queue.append(k)
    return cls, depth


def main(owl, out):
    sha = hashlib.sha256(open(owl, "rb").read()).hexdigest()
    cls, depth = load_area_of_law(owl)
    by_label = {}
    for i, d in depth.items():
        by_label.setdefault(cls[i]["label"], []).append((d, i))
    rows = []
    for tid, (heading, maps) in TITLES.items():
        if not maps:
            rows.append([tid, heading, "", "", "", "", "none", "no suitable Area of Law class found", sha, ""])
        for role, label, match, note in maps:
            cands = sorted(by_label.get(label, []))
            if not cands:
                raise SystemExit(f"label not found under Area of Law: {label!r}")
            d, iri = cands[0]
            parent = cls[next(p for p in cls[iri]["parents"] if p in depth)]["label"]
            rows.append([tid, heading, role, label, iri, d, match, note, sha, parent])
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["title_id", "title_heading", "role", "lmss_label", "lmss_iri", "lmss_depth", "match", "note", "lmss_owl_sha256", "lmss_parent_label"])
        w.writerows(rows)
    print(f"{len(rows)} rows for {len(TITLES)} titles -> {out} (LMSS.owl sha256 {sha[:12]}, {datetime.date.today()})")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
