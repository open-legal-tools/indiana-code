# Indiana Law Project — Spec

*Status: pre-build, speccing phase — October 2026*

---

## Problem

Indiana's official legal sources (iga.in.gov, courts.in.gov) publish the law. They don't make it accessible. PDFs dominate. Search is weak. There is no machine-readable API. There is no MCP server. An Indiana attorney using AI tools for legal research is either pasting statutes manually or risking hallucinated citations.

---

## Solution

An access layer over Indiana's public legal data:
1. **Text, not PDFs** — parse Indiana Code XML into clean structured text
2. **Search** — full-text with terms-and-connectors style queries
3. **MCP server** — expose Indiana law as tools any AI client can call
4. **Free, with links back** — public good positioning; official source stays authoritative

---

## Phase 1: Indiana Code (MVP)

### Data Acquisition

The Indiana General Assembly publishes the Indiana Code in XML at iga.in.gov. This is the key insight — no scraping, no OCR. Pull XML, parse to sections.

Indiana Code structure:
```
Title XX → Article XX → Chapter XX → Section XX (IC XX-XX-XX-XX)
```

Example: `IC 31-14-5-3` = Title 31, Article 14, Chapter 5, Section 3

Action items:
- [ ] Confirm XML endpoint / download format at iga.in.gov
- [ ] Write parser: XML → structured JSON (title, article, chapter, section, text)
- [ ] Store in SQLite with FTS5 virtual table
- [ ] Build citation resolver (IC XX-XX-XX-XX → row)
- [ ] Add official source URL to each section

### Search

SQLite FTS5 is sufficient for Phase 1. Terms-and-connectors = boolean full-text search.

```sql
-- FTS5 table
CREATE VIRTUAL TABLE ic_fts USING fts5(
  citation, title_num, article_num, chapter_num, section_num,
  title_name, chapter_name, text,
  content=sections
);
```

Queries:
- `search?q=custody+modification` → BM25 ranked results
- `search?q=custody+AND+modification+NOT+adoption` → boolean
- `section/IC-31-14-5-3` → direct citation lookup

### MCP Server

Python MCP server (or Node.js — TBD based on existing farm patterns):

```python
@tool
def search_indiana_code(query: str, title: int = None, limit: int = 10):
    """Search the Indiana Code by keywords or terms and connectors."""
    ...

@tool  
def get_section(citation: str):
    """Get a specific IC section by citation (e.g. 'IC 31-14-5-3')."""
    ...

@tool
def list_titles():
    """List all Indiana Code titles with their names."""
    ...
```

Server runs on Mac or one farm worker. Extremely low compute — text search in SQLite.

### Web Frontend

Simple. Fast. Public. 
- Search box, results list, section view
- Citation format in URL: `/section/IC-31-14-5-3`
- Every section links to official iga.in.gov source
- indianacle.com as the public domain

---

## Phase 2: Court Rules + Admin Code

Indiana Court Rules:
- Rules of Trial Procedure
- Rules of Appellate Procedure  
- Rules of Evidence
- Criminal Procedure Rules
- Courts publish HTML — parseable

Indiana Administrative Code:
- Agency regulations, indexed by agency
- Available from in.gov in structured form

Add to the same MCP server and search index. Same pattern: parse → SQLite → tools.

---

## Phase 3: CLE Hosting (Revenue Track)

Separate from the free law access layer. Same domain (indianacle.com), different section.

- Indiana CLE requirement: 36 hours per 3-year reporting period
- Focus: legal technology content (ITJD brand angle)
- Content: video courses, written materials, live webinars
- ICLEF accreditation: required for official CLE credit (apply when ready)
- Revenue: per-course ($25-75) or annual subscription ($150-250)

Phase 3 is independent of Phase 1/2. Can start building content before Phase 1 ships.

---

## Technical Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| Storage | SQLite + FTS5 | Zero infra, adequate for text search at this scale |
| MCP framework | Python MCP SDK | Consistent with farm/O-LT patterns |
| Hosting | Mac or farm worker | Low traffic, no need for cloud yet |
| Frontend | Static site or simple Next.js | Fast, cheap to host on Netlify |
| Domain | indianacle.com | Already owned |
| Update cadence | IGA publishes annually; scrape on session law changes | |

---

## Scale Estimate

- Indiana Code: ~50,000 sections, ~80MB of text
- SQLite FTS5 index: ~200MB total
- Search latency: <50ms for most queries
- Hosting: one farm worker or the Mac handles this without breaking a sweat

---

## First Steps

1. Check IGA XML endpoint — confirm format and download process
2. Write XML parser → JSON → SQLite schema
3. Seed Phase 1 data (full Indiana Code)
4. Build MCP server (3 tools: search, get_section, list_titles)
5. Test inside case-reader
6. Ship simple web UI to indianacle.com

---

## Open Questions

- [ ] IGA XML: available for bulk download, or must crawl per-title?
- [ ] Update schedule: does IGA push XML after each session, or is it static?
- [ ] IAC format: structured enough for direct parse, or needs scraping?
- [ ] Court rules: HTML parse sufficient, or request source format from courts?
- [ ] CLE accreditation: contact ICLEF early to understand timeline?
