# Indiana Law

**Domain:** Indiana legal data — Indiana Code, Administrative Code, court rules — made accessible.
**Owner:** Danielle Teagarden, JD
**Domain:** indianacle.com — Indiana as oracle. Our flag.

---

## What This Is

Indiana's official legal sources are functional but one-dimensional. This project makes them accessible:
- Indiana Code as structured, searchable text (not PDFs)
- Terms-and-connectors full-text search over statutes and opinions
- MCP server exposing Indiana law to AI tools
- Free. Links back to official sources. Not a replacement — an access layer.

Indiana is home. Build it right for one place. No CLE, no public stage, no accreditation. The bunker.

Related brands:
- **ITJD** (`~/projects/itjd/`) — the technologist-lawyer brand; this project lives under it

---

## Structure

| Component | Description |
|-----------|-------------|
| `data/` | Raw source data — XML from IGA, parsed JSON, SQLite |
| `scraper/` | Scripts to fetch and update from official sources |
| `search/` | Search index and query logic (SQLite FTS5 or similar) |
| `mcp-server/` | MCP server exposing Indiana law as tools |
| `api/` | REST API layer (optional, for web frontend) |
| `web/` | Public search UI at indianacle.com |

---

## Data Sources

| Source | Format | URL |
|--------|--------|-----|
| Indiana Code | annual HTML download (ZIP), one file per title | iga.in.gov/laws/ic/downloads — official; the API is not used |
| Indiana Appellate Opinions | S3 bulk CSV + REST API | CourtListener (ind, indctapp, indtc) |
| Indiana Administrative Code | TBD (HTML or XML) | in.gov |
| Indiana Court Rules | PDF/HTML | in.gov/courts |

Indiana Code from the annual HTML download (ten snapshots, 2017 to 2026, are parsed); act clauses from each year's Acts PDF. No IGA API token is used (its license restricts caching and reformatting).
Opinions via CourtListener quarterly bulk files (public domain mark), with an optional API top-up for new opinions. See docs/SPEC-ROADMAP-v2.md.

---

## MCP Tools (target spec)

```
search_indiana_code(query, title?, article?, chapter?)
  → sections matching query, with citation + text + link to official source

get_section(citation)
  → IC XX-XX-XX-XX → full section text + official link

list_titles()
  → browsable index of IC Titles

search_court_rules(query)
  → matches in Indiana Trial Rules, Appellate Rules, etc.

search_admin_code(query, agency?)
  → Indiana Administrative Code search
```

---

## North Star Alignment

Law should be accessible. Serving text with search treats users — attorneys and the public — as they'd like to be treated. Rugged elegance: fast, plain, honest. Links back to official sources; this is an access layer, not a rewrite.

---

## Current Status

**Schema v1 built locally** (branch `add-schema-v1`, draft PR #1). Done: parser, act-clause parser, versions store, as-of resolver, local stdio MCP server (six tools), title-to-SALI mapping, 34 tests. Not done: opinions in the store, section-level tags, relationship web, evaluation run, hosting or publication.

Read first: `docs/DESIGN-schema-v1.md` (data model), `docs/SPEC-ROADMAP-v2.md` (scope, phases, who does what), `docs/EVAL-plan-v1.md`.
Rules that matter: official text stays verbatim; everything we add is stored apart with provenance; no look-alike of an official citator; raw data under `data/` is read-only for agents; work orders return draft PRs only. `ROADMAP.md` and `SPEC.md` predate this and are historical.

## Director

Ventures Director — reports to the Captain.
See `~/projects/itjd/CLAUDE.md` for brand context.
