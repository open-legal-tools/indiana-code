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
| Indiana Code | REST API (JSON) | api.iga.in.gov — free token, official |
| Indiana Appellate Opinions | S3 bulk CSV + REST API | CourtListener (ind, indctapp, indtc) |
| Indiana Administrative Code | TBD (HTML or XML) | in.gov |
| Indiana Court Rules | PDF/HTML | in.gov/courts |

Indiana Code via IGA public REST API. Token: email apitoken.request@iga.in.gov.
Opinions via CourtListener S3 bulk data (bootstrap) + daily API sync. Public domain.

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

**Phase 0 — Validate** *(started October 2026)*

Active work items:
- [ ] Confirm IGA XML availability and download format
- [ ] Parse one sample title (XML → SQLite FTS5 proof of concept)
- [ ] Stand up minimal MCP server and test with case-reader
- [ ] Decide domain structure (one site vs subdomains for CLE)
- [ ] Assess openlegaltools.org disposition

See `ROADMAP.md` for full phase plan and success criteria.

Phase 1 (Indiana Code MVP) begins when Phase 0 validation is complete.

---

## Director

Ventures Director — reports to the Captain.
See `~/projects/itjd/CLAUDE.md` for brand context.
