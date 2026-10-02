# Indiana Law

**Domain:** Indiana legal data — Indiana Code, Administrative Code, court rules — made accessible.
**Owner:** Danielle Teagarden, JD
**Domain:** indianacle.com

---

## What This Is

Indiana's official legal sources are functional but one-dimensional. This project makes them accessible:
- Indiana Code as structured, searchable text (not PDFs)
- Terms-and-connectors full-text search
- MCP server exposing Indiana law to AI tools
- Free. Links back to official sources. Not a replacement — an access layer.

Long-term: the entire Indiana Code digitized as structured text. Start with the Code, expand to court rules and administrative code.

Related brands:
- **ITJD** (`~/projects/itjd/`) — the technologist-lawyer brand; this project lives under it
- **indianacle.com** — the domain; CLE hosting is a separate revenue track on this domain

---

## Structure

| Component | Description |
|-----------|-------------|
| `data/` | Raw source data — XML from IGA, parsed JSON, SQLite |
| `scraper/` | Scripts to fetch and update from official sources |
| `search/` | Search index and query logic (SQLite FTS5 or similar) |
| `mcp-server/` | MCP server exposing Indiana law as tools |
| `api/` | REST API layer (optional, for web frontend) |
| `web/` | Search UI — simple, fast, public |
| `cle/` | CLE hosting track (separate revenue stream) |

---

## Data Sources

| Source | Format | URL |
|--------|--------|-----|
| Indiana Code | XML | iga.in.gov |
| Indiana Administrative Code | XML/HTML | in.gov |
| Indiana Court Rules | PDF/HTML | in.gov/courts |
| Indiana Rules of Trial Procedure | HTML | courts.in.gov |

Indiana Code XML from the IGA is the priority target. Public domain — no licensing issues.

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

## CLE Track (separate, same domain)

Indiana requires 36 CLE hours per 3-year reporting period.
Focus: legal technology, AI in law, legal research tools — maps directly to ITJD brand.
Competition: ICLEF (incumbent), ISBA. Niche provider opportunity.
Revenue model: per-course purchase or subscription.

---

## North Star Alignment

Law should be accessible. Serving text with search treats users — attorneys and the public — as they'd like to be treated. Rugged elegance: fast, plain, honest. Links back to official sources; this is an access layer, not a rewrite.

---

## Director

Ventures Director — reports to the Captain.
See `~/projects/itjd/CLAUDE.md` for brand context.
