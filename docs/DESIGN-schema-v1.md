# Indiana Code data model, schema v1 (design)

Status: **proposed design with a working prototype**. Unofficial; not legal advice. Source of truth for how the project
represents the Indiana Code. The older prototype files (`schema.sql`, `scripts/bootstrap_code.py`, `src/db.py`,
`src/mcp_server.py`) predate this design: they key sections by integers (which cannot hold ids such as `1-1-1-2.1`) and
build the Code from the API; they are left in place and are not used by the new package.

## Principles
1. **Official source, dated.** Text comes from the General Assembly's annual HTML download for each year. Every record names
   its snapshot, source file and the SHA-256 of the source ZIP. Nothing is described as current law without a date.
2. **Verbatim text.** Statutory text is whitespace-normalized only. Notes that come before the text (version notes,
   recodification citations, revisor's notes) are kept in `preamble_notes`; the history note ("As added by P.L...") is kept
   in `history_note`. Tables are flattened to text and italics are dropped.
3. **JSON Lines are canonical;** SQLite is derived and rebuildable. Source ZIPs stay outside the repository.
4. **Our additions stay separate** from official text (tags, links, annotations), with provenance.
5. **Return text, not conclusions.** Every answer carries `unofficial: true`, the snapshot and effective dates, flags and a
   disclaimer.

## Identifiers
- Section work id: `31-16-15-25` (text; decimals allowed in any part, for example `7.1-1-1-1`, `6-1.1-17-1`, `3-11-1.5-18`).
- A dated version adds a letter suffix in the official files (`2-5-36-9-b`); `base_id` drops it. Articles can also carry a
  suffix (`20-20-b`).
- Accepted citation forms: `IC 31-16-15-25`, `I.C. § 31-16-15-25`, `Ind. Code § 31-16-15-25 (2024)`
  (`indiana_law.asof.normalize_citation`).

## Tables (`src/indiana_law/store.py`)
- `snapshot(snapshot_id, year, compile_date, compile_date_certain, source_zip_sha256, parser_version)`
- `section_version(vid, id, base_id, version_suffix, text, text_hash, effective_from, effective_until, status)`; one row per
  distinct (id, text, dates); `''` means unbounded.
- `appearance(snapshot_id, vid, heading, history_note, history_acts, preamble_notes, hierarchy ids and headings, source_file)`
- `act(act_id, year, number, bill, approved_on)` and `act_clause(act_id, section_in_act, kind, target, level, effective_date,
  basis, retroactive)`, parsed from each year's Acts PDF.
- `section_fts`: full-text index over version text.

## Version notes
Official files split a section into dated versions and say so in a note, for example "This version of section effective
until 7-1-2027. See also following version of this section, effective 7-1-2027." `parse_code.dates_from_note` reads these
forms (including repeal and chapter-repeal variants and "amended by P.L.x, SEC.n, effective D" pairs). Revisor's notes that
re-date a section are kept as notes and not interpreted.

## "As of" rule (`indiana_law.asof.resolve`)
Measured on ten annual files (2017 to 2026) against the Acts: each file's undated text reflects the law as of July 1 of its
year (97% to 99% of acts effective that day are already in it, in seven tested years); later effective dates appear as dated
versions. For a date D:
- on or after July 1 of year Y: use snapshot Y and the version whose dates cover D;
- before July 1 of year Y: look at the section's session-Y act clauses. All effective by D: snapshot Y. None effective by D:
  snapshot Y-1. Mixed: ambiguous, report it and list the clauses;
- after the latest snapshot: use the latest, confidence `low`, flagged.
Answers include `pending_acts` (acts effective after D that amend the section).

## Known limits
- Act clauses come from a heuristic parse of the Acts PDF text (2018 has no usable acts file; 2009 to 2016 are PDF-only and not parsed).
- 2017 and 2018 compile dates are unknown (the ZIP members are dated June 2024).
- Pre-July-1 answers are only as good as the clause parse; sections with no clauses get `medium` confidence.
- Cosmetic differences (formatting, repeated headings) count as text changes in diffs.

## Using the code
```
PYTHONPATH=src python -m indiana_law.cli parse-snapshot <html_dir> out.jsonl --snapshot-id 2026-06-23 --zip-sha256 <sha>
PYTHONPATH=src python -m indiana_law.cli parse-acts <acts.txt> acts-2026.jsonl --year 2026
PYTHONPATH=src python -m indiana_law.cli build-store store.db --snapshot ID:YEAR:COMPILE_DATE:CERTAIN:JSONL ... --acts acts-2026.jsonl ...
python -m pytest tests
```

## MCP tools (`src/indiana_law/mcp_server.py`, local stdio; `tools.py` holds the logic)
`ic_search`, `ic_resolve_citation`, `ic_get_section`, `ic_get_versions`, `ic_browse`, `ic_get_act`. All read-only, titled, with
declared output schemas; every answer carries `unofficial`, the disclaimer, snapshot and dates, and `flags`. Run with
`INDIANA_LAW_DB=<store> PYTHONPATH=src python -m indiana_law.mcp_server`; `scripts/smoke_mcp.py` starts it over stdio and asks
twelve research-style questions (answers were 213 to about 3,200 tokens each in the first run).

## SALI mapping
`mappings/title_area_of_law.csv` maps each Code title to LMSS Area of Law classes (hand-curated; exact, close or approximate; five
titles left unmapped). `scripts/make_title_map.py` rebuilds it and verifies every class against `LMSS.owl`, whose SHA-256 is recorded.
No section-level tags exist yet.

## Not decided here
Hosting, public site, registration as a connector, section-level SALI tags, opinions, and any licence for this repository.
