# What this release does not cover

Unofficial; not legal advice. Every answer from the MCP server already carries
that disclaimer.

## In this store (2017–2026 Indiana Code)

- Ten annual HTML snapshots of the Indiana Code (2017–2026).
- Act *clauses* (what each public law amended, added, or repealed) for 2017 and
  2019–2026. **2018 acts are missing** — no usable Acts file was parsed.
- As-of resolution uses a July-1 cutoff plus those clauses. Pre-July-1 answers
  are only as good as the clause parse.

## Companion PDFs (optional, same downloads page)

`indiana_law.cli ingest-companion` can index Constitution, Non-code, and full
Acts PDFs from the official HTML zips, plus pre-2017 archive title PDFs you
download yourself (see `docs/ARCHIVE-PDFS.md`). Those use
`ic_list_companion` / `ic_search_companion` / `ic_get_companion`. They are
not dated Code sections.

- 2018 still has no usable *act-clause* file
- Pre-2017 archive zips are not bundled; ingest them locally after download
- Companion text is `pdftotext` output, not the HTML parser

## Not ingested at all

- Indiana Administrative Code
- Indiana court rules
- Appellate opinions (CourtListener bulk may exist locally; it is not in this
  store and is not served by these tools)
- SALI / FOLIO tags below title level (a title map CSV exists; no tool uses it)
- Daily or mid-session updates. Coverage is the annual compile, `data_through`
  2026-06-23.

## Not this tool

- Legal advice, citator status, “good law,” or KeyCite-style signals
- An official publication. Verify every citation at iga.in.gov
- A hosted public URL until one is separately stood up
- IGA API access. This project does not use `api.iga.in.gov`
