# Indiana Law — Project Roadmap

*Last updated: October 2026 | Status: Phase 0 — Validate*

---

## The Sequence

Phase 0 is a gate. If IGA bulk XML isn't available, Phase 1 timeline changes — potentially by weeks. Everything downstream depends on knowing the data acquisition answer. Don't skip it.

```
Phase 0 (2 weeks)   → Phase 1 (4–6 weeks)   → Phase 2 (8–12 weeks)   → Phase 3 (ongoing)
Validate            → Indiana Code MVP       → Expand                  → Sustain
```

---

## Phase 0: Validate

**Duration:** 2 weeks  
**Goal:** Confirm assumptions before building anything.

### Key Deliverables

1. **IGA XML recon** — Answer the critical question: is Indiana Code XML available for bulk download, or title-by-title crawl, or only as individual section endpoints? Document the actual URL pattern, download format, update schedule.

2. **Sample title parse** — Pick one title (e.g., Title 31 — Family Law). Download XML, write a parser, confirm it produces clean structured output: citation, title number, article, chapter, section, text, official source URL. If the XML is malformed or inconsistently structured across titles, find out now.

3. **Schema and SQLite proof of concept** — One title, fully loaded into SQLite FTS5. Run a test query. Confirm search works. Confirm citation lookup works.

4. **MCP tooling confirmed** — Stand up a minimal Python MCP server with one tool (`get_section`). Connect it to case-reader or another MCP client. Confirm the integration pattern works.

5. **openlegaltools.org disposition** — Let expire or redirect to indianacle.com. Not our flag. One decision, no revisiting.

### Critical Risk: IGA XML Availability

**If bulk download is available:** Phase 1 timeline holds. Parser is the main work.

**If title-by-title crawl is required:** Add 1–2 weeks to Phase 1. Crawl logic is more complex — need rate limiting, error handling, incremental sync. Adjust timeline accordingly.

**If XML is not usable (malformed, incomplete, no structure):** Fallback is PDF parsing via OCR on the farm. That's a significant pivot. Evaluate before committing to it.

### Dependencies

- iga.in.gov access (public, no auth required — but confirm no anti-crawl blocks)
- Python environment with `lxml`, `sqlite3`, Python MCP SDK
- At least one existing MCP client for tool testing (case-reader works)

### Success Criteria

- [ ] Know exactly how to download Indiana Code XML
- [ ] Parsed one title into SQLite with working FTS5 search
- [ ] Ran one MCP tool successfully from a client
- [ ] Domain strategy written down and decided

### What to Defer

- Full IC download and parse
- Web frontend
- Any CLE content
- IAC or court rules research (Phase 2)

### Effort

Solo developer with AI assistance: **~20 hours** across 2 weeks. Most of this is research and small scripts.

---

## Phase 1: Indiana Code MVP

**Duration:** 4–6 weeks (adjust upward if crawl is required per Phase 0 findings)  
**Goal:** Full Indiana Code parsed, indexed, served via MCP, publicly accessible at indianacle.com.

### Key Deliverables

1. **Full IC download and parse** — All titles. XML → structured JSON → SQLite. Every section has: citation (IC XX-XX-XX-XX), title/article/chapter/section numbers, title name, chapter name, section text, official URL.

2. **SQLite FTS5 search** — `ic_fts` virtual table populated. Queries tested:
   - Keyword search with BM25 ranking
   - Boolean terms-and-connectors (`AND`, `OR`, `NOT`)
   - Citation lookup (exact match on IC citation)
   - Filtered search by title or chapter

3. **Three MCP tools, production-quality:**
   - `search_indiana_code(query, title?, article?, chapter?, limit?)` — returns ranked sections with citation + text + official link
   - `get_section(citation)` — exact citation lookup
   - `list_titles()` — index of all IC titles with names

4. **MCP server running** — Stable, documented, with a config entry for MCP clients. Lives on the Mac or a farm worker. Tested with real queries from case-reader.

5. **Web UI live at indianacle.com** — Static or Next.js. Requires:
   - Search box → results list (citation, chapter name, text excerpt)
   - Section view at `/section/IC-31-14-5-3`
   - Every section links to iga.in.gov official source
   - Mobile-responsive
   - Fast: <2s page load, <50ms search

6. **Update process documented** — IGA publishes on the annual legislative calendar. Write the re-sync script. Document when to run it.

### Dependencies

- Phase 0 complete with positive IGA XML confirmation
- indianacle.com DNS configured (already owned)
- Netlify or farm worker for hosting decision finalized

### Success Criteria

- [ ] All IC titles loaded (no gaps)
- [ ] Search returns correct results for 10 test queries covering different areas of law
- [ ] MCP tools work from case-reader on realistic legal research tasks
- [ ] indianacle.com publicly accessible with working search
- [ ] Page links to iga.in.gov on every section

### What to Defer

- Court rules (Phase 2)
- Administrative code (Phase 2)
- Advanced search UI features (filters, saved searches, history)
- Citation graph or cross-reference links
- User accounts or personalization
- CLE content

### Effort

Solo developer with AI assistance: **~80–100 hours** across 4–6 weeks. Parse logic is the heavy lift. MCP server and web UI are fast once data is clean.

---

## Phase 2: Expand

**Duration:** 8–12 weeks (can start immediately after Phase 1 ships)  
**Goal:** Add Indiana court rules and administrative code to the same search index and MCP server.

### Key Deliverables

1. **Indiana Court Rules parsed and indexed:**
   - Rules of Trial Procedure
   - Rules of Appellate Procedure
   - Rules of Evidence
   - Criminal Procedure Rules
   - Each rule has: citation, rule number, rule name, text, official link

2. **Indiana Administrative Code parsed and indexed:**
   - All agencies, all articles
   - Citation format: IAC XX-XX-XX (agency:article:rule)
   - Official link to in.gov

3. **Two additional MCP tools:**
   - `search_court_rules(query)` — Indiana procedural rules
   - `search_admin_code(query, agency?)` — IAC search with optional agency filter

4. **Unified search** — Search box on indianacle.com queries IC, court rules, and IAC simultaneously. Results labeled by source. Filtered search available per corpus.

5. **Improved search UI** — Based on Phase 1 usage:
   - Source filter (Code / Court Rules / Admin Code)
   - Citation autocomplete or suggest
   - Better text excerpts (highlight matches)

### Dependencies

- Phase 1 live and stable
- Confirm IAC format: structured XML or scrape-from-HTML (research in parallel with Phase 1)
- Court rules: courts.in.gov HTML parse — confirm stability of page structure

### Success Criteria

- [ ] Court rules queryable via MCP and web
- [ ] IAC queryable via MCP and web
- [ ] Unified search works across all three corpora
- [ ] No regressions on IC search from Phase 1

### What to Defer

- Session law (enrolled acts, amendments — complex, deferred until Phase 2 stable)
- Legal annotations or case citations
- CLE content

### Effort

Solo developer with AI assistance: **~60–80 hours** across 8–12 weeks. Court rules are probably fast (HTML parse). IAC format is the unknown — may be quick or may require scraping work.

---

## Decisions Outstanding

| Decision | Needed By | Notes |
|----------|-----------|-------|
| IGA API token | Now | Email apitoken.request@iga.in.gov — free, same-day |
| IAC format (XML vs scrape) | Mid Phase 1 | Parallel research |
| openlegaltools.org | Phase 0 | Shared domain — not our flag. Let expire or redirect. |

---

## What This Is Not

- A replacement for official sources. Every section links back. This is an access layer.
- A legal research platform. No annotations, no citators, no headnotes. That's Westlaw territory.
- A law firm or legal services provider. Just tools.
- A CLE provider. That's the stage. This is the bunker.
- A big production system. SQLite on a farm worker handles 50k sections fine. Don't over-engineer it.
- A 50-state platform. Indiana is home. Build it right for one place first.
