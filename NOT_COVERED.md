# What this release does not cover

Unofficial; not legal advice. Every answer from the MCP server already carries
that disclaimer.

## In this store (2017–2026 Indiana Code)

- Ten annual HTML snapshots of the Indiana Code (2017–2026).
- Act *clauses* (what each public law amended, added, or repealed) for 2017 and
  2019–2026. **2018 acts are missing** — no usable Acts file was parsed.
- As-of resolution uses a July-1 cutoff plus those clauses. Pre-July-1 answers
  are only as good as the clause parse.

## Companion PDFs (official IGA and court publications)

`indiana_law.cli ingest-companion` indexes Constitution, Non-code, Acts,
historical tables, pre-2017 archive title PDFs, and current court-rules PDFs.
Those use `ic_list_companion` / `ic_search_companion` / `ic_get_companion`.
They are not dated Code sections.

- Session laws: IGA archive 1852–2000 plus yearly Acts 2000–2026
  (`scripts/fetch_iga_historical.py`)
- Non-code statutes: 1807–2026 (years IGA published a PDF)
- Compiled Code title/chapter PDFs: 2005 and 2009–2016
  (`scripts/fetch_iga_archives.py`); **2006–2008 and pre-2005 compiled zips
  were still missing at the official path on 2026-10-23**
- Court rules: current compiled PDFs from rules.incourts.gov, including Access
  to Court Records. Not a historical rules archive.
- Companion text is `pdftotext` output, not the HTML parser
- 2018 still has no usable *act-clause* file

## Not a complete opinion library

`case_search` / `case_get` index Indiana clusters from the CourtListener
2026-09-30 bulk, with opinion bodies joined from Harvard Caselaw Access
Project JSON (static.case.law) and official PDFs from public.courts.in.gov.
That is not every Indiana decision ever issued. Unpublished / NFP memos on
the official portal begin around 2006.

`ic_cases_citing` is a text-mention index of IC / Ind. Code citations in those
opinion bodies. It is not a citator: it does not say a case construed, applied,
followed, or distinguished a statute, and it is not a “good law” signal.
`cases_construing` is a narrower index. A construction word (construe,
interpret, plain language, ambiguous) or an application word (the statute
applies, or in violation of the cited section) has to sit in the citation's
sentence, or in the sentence immediately before a short citation sentence.
The following sentence is not included. Every row is `rule_unreviewed`. No
model has reviewed them. They are not holdings.
Mentions without an IC / Ind. Code prefix are not indexed. Structured Code
resolution is only flagged when the opinion date is in a loaded snapshot year
and the section id exists in the store.

`cases_citing_case` / `cases_cited_in` / `cases_citing_court` is a text-mention
index of reporter citations and Rule 22 case numbers. Indiana identifiers come
from Harvard CAP metadata joined by cap id. The extractor also reads U.S. /
S. Ct. / F.2d / F.3d / F.4th / F. Supp. / regional reporters and
`(court year)` parentheticals using CC0 Indigo Book 2d ed. (2023-2) tables
T1.1 / T3 / T9 / T12. Those outbound cites stay unresolved: this store does
not contain SCOTUS, Seventh Circuit, or district-court opinion bodies.
Ambiguous table-page cites and *Id.* / *supra* are not resolved. This is not
KeyCite, not treatment, and not a good-law signal.

`decision_form` / `citability` on case tools is a text classification of the
slip opinion (memorandum vs opinion, App. R. 65(D) as a date rule). It is not
the court’s official publication status. CourtListener `precedential_status`
sometimes labels memoranda Published (especially 2017–2018).

`disposition` on `case_get` / `case_search` is a rule read of the closing line
(“Affirmed.”, “Reversed and remanded.”, or a short “we affirm” sentence) in
the last part of the slip. It is not the court’s official judgment, not
treatment of any other case, and not a citator. A closing the rule does not
recognize stays `unlabeled`. “In part” is kept as a flag. Transfer orders
and disciplinary orders are outside this rule.

`standards` on `case_get`, and the `standard` filter on `case_search`, are
rule reads of sentences that state a standard of review: de novo, abuse of
discretion, clearly erroneous, the sufficiency line “we neither reweigh the
evidence nor judge,” prima facie error, substantial evidence, and arbitrary
or capricious. A mention that does not state the standard stays out, including
“there was substantial evidence that” and “the court did not abuse its
discretion.” This is not a ruling on which standard governs, and an opinion
can carry more than one.

`separate_writings` on `case_get`, and the `separate` filter on `case_search`,
read the slip's own vote line that says a judge concurs or dissents "with
separate opinion." "Without separate opinion," and a sentence about another
case's separate opinion, stay out. This is not a holding, and it does not
say the separate writing is right.

## Not ingested at all

- Indiana Administrative Code
- SALI / FOLIO tags below title level (a title map CSV exists; no tool uses it)
- Daily or mid-session updates. Structured Code coverage is the annual compile,
  `data_through` 2026-06-23.

## Not this tool

- Legal advice, citator status, “good law,” or KeyCite-style signals
- An official publication. Verify every citation at iga.in.gov
- A guarantee that the hosted URL is complete or current. `mcp.indianacle.com` is unofficial.
- IGA API access. This project does not use `api.iga.in.gov`
