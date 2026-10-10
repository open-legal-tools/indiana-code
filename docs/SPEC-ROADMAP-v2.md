# Indiana Law data: scope, spec and roadmap (v2)

Status: **Proposed.** Written 2026-10-10. Unofficial; not legal advice. Nothing here is approved for execution beyond what Danielle has already
approved (local schema, store, resolver and local MCP server on branch `add-schema-v1`). Work orders below are drafts, not issues.

**Evidence labels.** *Observed* = measured or read directly. *Agent-reported* = from a web-research subagent (2026-10-10), not independently verified.
*Inference* = my reasoning. *Unverified* = nobody confirmed it.

## 1. Goal and principles

**Goal:** the best open, dated, trustworthy data on Indiana statutes and appellate opinions, with an honest web of relationships between them, usable by AI
agents first and people second, built mostly by agents under light human supervision.

1. **Verbatim stays verbatim.** Official text is never edited. Everything we add (tags, relations, proposition cards) is stored apart, with provenance.
2. **Every derived fact carries evidence:** a quoted span with offsets, the method, the model and prompt hash, the ontology version, a confidence, and a status
   (`ai_unreviewed`, `auto_verified`, `attorney_reviewed`, `rejected`).
3. **Dates everywhere.** Snapshot, compile, effective and retrieval dates are part of every answer.
4. **No look-alike of an official citator.** We never use "good law", "overruled" or KeyCite-style names for AI output; we use "AI-detected, unreviewed".
5. **Read-only by default.** Raw data is immutable; agents work on copies; only reviewed changes become releases.
6. **Human time is the scarce resource:** the review queue is sized to about 30 minutes a week and routes only low-confidence or high-stakes items.
7. **Say what we do not cover** (`NOT_COVERED.md` ships with every release).

## 2. Where we are (Observed)

- **Code:** ten annual snapshots (2017 to 2026) parsed to 777,842 records and 114,071 distinct versions; act layer for nine years; as-of rule tested on seven
  July-1 cycles; text fidelity: 99.2% of sampled 9-word windows match the official PDF rendering; changes explained by acts 98 to 99%.
- **Software:** `indiana_law` package (parser, acts parser, SQLite store, as-of resolver, six-tool local MCP server), 34 tests, design in `docs/DESIGN-schema-v1.md`; draft PR #1.
- **SALI:** Area-of-Law mapping for 34 titles (12 exact, 13 close, 13 approximate; 5 unmapped).
- **Opinions:** CourtListener bulk files downloaded (dockets, clusters; opinions file not yet); 121,775 Indiana dockets across `ind`, `indctapp`, `indtc`; per-quarter counts running.
- **Evaluation:** plan written, not run.
- **Not done:** opinions in the store, tags below title level, relations, hosting, registration, attorney review.

## 3. Corrections that change the plan

1. **SALI does have standard-of-review and disposition concepts** (my earlier "no classes" finding was wrong; the label search missed them). Checked directly in `LMSS.owl` (2026-10-10):
   - class **Appellate Standards of Review** with eight values: Abuse of Discretion, Arbitrary and Capricious, Clearly Erroneous, De Novo, No Review, Reasonableness, Substantial Evidence, Substantial Prejudice;
   - class **Document Components** with Headnote, Judicial Concurrence, Judicial Dissent, Legal Issue, Legal Argument, Factual Statement, Citations to Another Document;
   - dispositions exist as object properties labeled `sali:affirmed`, `sali:reversed`, `sali:vacated`, `sali:remanded` (not classes);
   - still not found: holding (as a class), per curiam, procedural posture, relationship types such as overrules or distinguishes.
2. **FOLIO is a candidate primary vocabulary** (*agent-reported* plus my check of its LICENSE): same class id suffixes as LMSS, data under CC BY 4.0, working Python tools; the LMSS repo file is MIT but SALI's website reportedly says CC BY-ND, which is unreconciled (section 5).
3. **Search recall:** all-words search missed relevant sections; any-word fallback added (done).

## 4. Data architecture (layers)

| Layer | Content | Mutability | Example tables |
|---|---|---|---|
| L0 source | official ZIPs, bulk files, ontology files with hashes and dates | immutable | `source_file` |
| L1 parsed | sections and versions; opinions, components, paragraphs, offsets | rebuildable | `section_version`, `opinion`, `opinion_span` |
| L2 deterministic facts | citation mentions (eyecite plus Indiana statute pattern), CourtListener citation-map edges, act clauses, court and date metadata, disposition and standard of review by rule | rebuildable | `citation_mention`, `act_clause`, `edge(kind=rule)` |
| L3 ontology tags | class references (IRI plus id suffix plus label plus ontology commit) | regenerable | `tag` |
| L4 AI annotations | proposition cards, proposed relations, similarity edges | regenerable, never overwrites L1 to L3 | `annotation`, `edge(kind=ai)`, `evidence` |
| L5 review | verdicts and approvals | append-only | `review` |

Every release is a versioned bundle: JSONL canonical files, a SQLite build, a manifest of hashes, a dataset card, a quality report and `NOT_COVERED.md`.

## 5. Ontology (SALI, FOLIO and our extension)

- **Tag by reference, hedge on source.** Store the bare id suffix plus both full IRIs (LMSS and FOLIO bases), the ontology name, a **pinned commit SHA** of the file used, label, and parent path. Re-resolve by suffix at each ontology update and check for "DEPRECATED" labels.
- **Primary vocabulary:** FOLIO if license reading confirms (CC BY 4.0 data), because the license is clear and tooling exists; keep LMSS IRIs alongside. *Open:* SALI's website reportedly states CC BY-ND and "no distributed derivatives"; the MIT file in the repo conflicts. Avoid redistributing modified ontology files; ask SALI in writing before any publication that bundles ontology text (Danielle's decision).
- **Local extension** in our own namespace (a separate OWL file importing a pinned snapshot, never editing upstream): Holding, Per Curiam, Procedural Posture values, disposition values as classes (Affirmed, Reversed, Vacated, Remanded, in part), relationship types, Indiana-specific standard-of-review phrasings. Each local class gets a parent in the upstream tree and a `skos:closeMatch` where one exists. Propose upstream later via FOLIO's GitHub issues or SALI's viewer comments (*agent-reported* channels); contacting either is Danielle's decision.
- **Mapping method:** retrieval over labels, alternate labels and definitions (keyword plus embeddings), restricted to a branch; an LLM judge over a **closed candidate list**; unmapped is allowed; back off to the parent when unsure; thresholds calibrated on a gold set. No published precision exists for FOLIO or LMSS tagging (*agent-reported*), so we measure it.
- **First tasks:** (a) add FOLIO IRIs to `mappings/title_area_of_law.csv` after confirming suffixes match for those classes; (b) map section-level Area of Law hierarchically (title, then article, then chapter) with a gold set; (c) tag opinions with court, document type, standard of review, disposition, Document Components (concurrence, dissent) deterministically where possible.

## 6. Opinions pipeline

1. **Source:** CourtListener bulk files (public domain mark; terms read 2026-10-10). Record snapshot date and hashes. FCRA-use restriction and "attribute honestly" go into our terms.
2. **Select:** Indiana dockets (`ind`, `indctapp`, `indtc`), clusters, then stream the 55 GB opinions file for those clusters; keep the text and metadata; store `data_through` per court.
3. **Parse components** (rules first, then model-assisted): caption, panel, procedural history, issues, facts, standard of review, analysis, holding statements, disposition, concurrence, dissent, per curiam; every component a span with offsets. Publication status and memorandum decisions labeled (App. R. 65: memoranda issued on or after 2023-01-01 may be cited for persuasive value; *agent-reported*).
4. **Citations:** eyecite for case citations; our Indiana Code pattern for statutes (eyecite's Indiana statute coverage is unverified); resolve statutes to a section id **and a version by the opinion's date**; resolve cases through the citation map.
5. **Gap handling:** quarterly bulk lag is bridged by (A) `data_through` flags and a pointer to the courts' opinion pages, (B) an API top-up for new Indiana opinions with an account token (default limits 5 a minute, 50 an hour, 125 a day), (C) later, webhooks. The courts' own endpoint is not used without their permission.

## 7. The relationship web and "proposition cards" (our headnotes)

**Edge vocabulary and feasibility** (*agent-reported* plus my judgment):
| Edge | Tier | Evidence | Default visibility |
|---|---|---|---|
| cites_case (citation map, eyecite) | 1 deterministic | map row, mention offsets, depth | shown |
| cites_statute (version by opinion date) | 1 deterministic | mention span, resolved version | shown |
| disposition (affirmed, reversed...), standard_of_review_applied | 1 rule, then model check | span | shown |
| construes_statute, applies_statute | 2 model-proposed, quote-anchored | quote naming the section in the same paragraph | shown with "AI-detected, unreviewed" |
| follows, distinguishes | 2 | explicit signal words plus quote | same |
| overrules, criticizes, questions | 3 high stakes | human review before display | hidden until reviewed |
| similar_to, same_cluster | separate non-legal layer | embeddings | labeled "similarity, not law" |

**Proposition card** (original text, never West or Lexis headnote language): one or two sentences stating a rule or holding from an opinion; `kind` (holding, rule statement, standard of review, dicta, procedural); the quote spans supporting it; linked statute versions; ontology tags; `dicta_flag`; confidence; status. **Verification gates** before a card is published as `auto_verified`: (1) every quote exists verbatim at the stated offsets; (2) a second model, from a different family, judges that the quoted text entails the proposition; (3) cited statutes resolve; (4) no overlap with known proprietary headnote text where such text is available for a check. Anything failing stays `ai_unreviewed` or `rejected`. General models hallucinate heavily on specific legal questions (Stanford RegLab/HAI figures of 69 to 88%, *agent-reported*), which is why quote-anchoring is mandatory.

**MCP surface to add:** `cases_construing(section_id, as_of)`, `neighbors(authority_id, relation_filter)`, `get_card(card_id)`, `get_evidence(edge_id)`, with every result carrying status and the not-a-citator notice.

## 8. Quality system and release gate

Automated layers (run on every build, results committed): schema and required fields; referential integrity; citation resolve rates (exceptions published); text fidelity against a second rendering; date logic (no overlapping versions, effective dates inside plausible ranges); release regression (counts, change rate, text changed without act evidence flagged); diff summary; annotation scoring on gold sets. Human time: worst-20 fidelity review per release, gold-set labeling, and the review queue.

**Gold sets (built once, grown slowly):** Code fidelity (done at scale; extend to all titles); opinion component boundaries, 25 opinions; relation edges, 150 stratified by type; ontology tags, 200 passages; cards, 100. Double annotation on 50 items where a second reviewer exists; otherwise model-versus-attorney and say so.

**Release gate (all must pass):** schema and integrity 100%; fidelity above threshold and worst-20 reviewed; resolve rate not below the last release; zero date-logic errors; counts within tolerance or explained; manifest verified from a clean download; `NOT_COVERED.md` updated; gold scores recorded.

**Documentation bundle** (*agent-reported* standards): README, dataset card, data and code licenses, `CITATION.cff`, changelog, `MANIFEST.sha256`, sources file with URLs and dates, JSON Schema, quality report, `NOT_COVERED.md`, and Croissant JSON-LD for machine discovery; `llms.txt` and a quickstart with example prompts for agents. Publishing options (later): GitHub for code and docs, Zenodo for dated DOI releases, Hugging Face mirror. Annotations CC0 or CC BY 4.0; code MIT or Apache-2.0; state that the statute text is public-domain material with no claim, and that the dataset is unofficial.

## 9. Who does what (adopted two-lane workflow: work orders in, draft PRs out)

Rung 1 of the autonomy ladder: one tool, one approved work order, supervised, draft PR only. No tool merges.

| Tool | Give it | Do not give it |
|---|---|---|
| **Claude Code** (primary executor) | parsers, schema, store, MCP server, test suites, data-quality scripts, pipelines that touch the large local data | secrets, merges |
| **Codex / ChatGPT** | independent review of Claude's PRs (different model family); well-specified, test-gated scripts; second opinions on spec ambiguity | long batch runs; open internet |
| **Cursor** | interactive edits, documentation, small self-contained issues | autonomous multi-file pipeline work (weakest fit; cloud agents bill at API rates beyond the plan) |
| **Jules** | docs, unit tests for existing code, small bounded fixes, with hidden acceptance tests | ambiguous parsing, taxonomy mapping (an earlier trial passed 24 visible tests and failed 3 of 34 hidden cases) |
| **Google Deep Research, ChatGPT deep research, NotebookLM** | literature and standards surveys, with sources listed | any change to data or code |
| **Danielle** | decides mapping rules and risk labels, answers legal questions, reviews the queue, approves every work order and every merge | |

**Guardrails (*agent-reported*, adopted here):** raw data read-only at the OS level and agents work on copies; protected main with required CI and draft-PR-only; hidden acceptance tests agents never see, and a CI check that existing tests are not edited; no changes to dependency or lock files unless the work order allows; no secrets and network off or allowlisted for cloud agents; budget and time stops in every work order; a different tool reviews each PR. Large data jobs run locally under supervision; cloud agents only see the GitHub clone.

## 10. Roadmap

Each phase has an exit gate. Nothing starts without an approved work order.

| Phase | Outcome | Main work (tool) | Exit gate | Danielle's decisions and time |
|---|---|---|---|---|
| **0 Code core** (done) | schema, store, resolver, local MCP, title map | Claude Code | tests pass; fidelity and diff results recorded | decided: headings kept, push |
| **1 Code release candidate** | fidelity across all titles; frozen schema; CI; dataset card and quality report; as-of tests on more sections | Claude Code builds; Codex reviews; Jules drafts docs | release gate passes; evaluation run (statute questions) | review a short key and disagreements (about 1 hour total) |
| **2 Opinions ingest** | Indiana opinions in the store with components, citations and statute links; `data_through`; top-up path | Claude Code (local); Codex reviews | parse gold set (25 opinions) passes; citation resolve rates reported | approve the 55 GB pull; accounts for API top-up; terms questions |
| **3 Ontology layer** | section and opinion tags against FOLIO and LMSS; local extension file; gold-set scores | Claude Code harness; Danielle sets rules; Deep Research for ontology survey | per-branch precision reported; unmapped rate known | mapping rules and risky-class list (about 2 hours once) |
| **4 Web and cards** | edges, proposition cards, evidence, review queue, new MCP tools | Claude Code; Codex adversarial review; hidden tests | tier-1 precision at least 95% on gold; cards pass verification gates; tier 3 hidden | weekly queue of about 30 minutes |
| **5 Evaluation and decision** | tool versus web search on ten questions; attorney review of terms and disclaimer | Claude Code runs; Danielle grades disagreements | release thresholds met; legal questions answered | attorney visit; decide to host |
| **6 Public surface** (gated) | Worker for the MCP endpoint and pages; permalinks; accessibility pass; optional connector directory listing | Claude Code, Cursor for UI | legal gate passed; budget approved | domain, entity, privacy policy, support contact |
| **7 Expand** | Administrative Code, court rules (with the courts' permission), historical digitization (funded) | to be scoped | funding or partner secured | grant or partner decisions |

**Order of value:** phases 1, 2, 3 and 4 build the data and can proceed locally without any third-party contact; phase 5 and 6 are where legal, hosting and cost decisions begin.

## 11. Draft work orders (not created; adopted format)

**WO-A Code fidelity at scale.** Outcome: compare every title's parsed text with the second rendering and report match rates and the worst 20 sections. Tool: Claude Code. Scope: `src/`, `tests/`, `scripts/`, read-only `data/`. Deliverable: draft PR with a script, a report and a check added to CI. Stop: 2 hours or any failed check. Not authorized: merge, network access beyond already-downloaded files, edits to data.
**WO-B Dataset card and manifest generator.** Outcome: generate `MANIFEST.sha256`, a dataset card and `NOT_COVERED.md` from the store. Tool: Jules (docs) with Claude Code review. Hidden acceptance: manifest verifies from a clean checkout.
**WO-C Opinions: select and load.** Outcome: stream the bulk files into an Indiana opinions table with spans and `data_through`. Tool: Claude Code locally. Stop: disk or time limits. Not authorized: any request to a court website.
**WO-D Statute-citation extractor.** Outcome: a tested extractor for Indiana Code citations in opinion text with version resolution. Tool: Claude Code; Codex reviews with an independent test corpus.
**WO-E Ontology harness.** Outcome: candidate retrieval plus judge pipeline with a closed list and a scoring script for a gold set. Tool: Claude Code; Danielle supplies the mapping rules and 200 labels over time.
**WO-F Card verification service.** Outcome: quote-span, entailment and statute-resolution checks. Tool: Claude Code, with a second-family model as judge.
Each work order lists: heading link, scope (files it may touch), deliverable and checks, stop conditions, non-authorizations (merge, accounts, billing, sends, DNS, deletion), North Star check, and Danielle's approval date.

## 12. Risks (top eight) and mitigations

1. **Hallucinated or over-general holdings:** quote-anchoring, entailment by a different model family, dicta flag, review of high-stakes types only.
2. **Mistaken for an official citator:** naming rules, visible "AI-detected, unreviewed" status, no treatment signals shown until reviewed.
3. **Statute version mismatch** (case construed an older text): link by opinion date; show both.
4. **Time gap and coverage gaps:** `data_through`, top-up path, labels for memoranda and unpublished decisions.
5. **License conflicts** (SALI wording, LSA site terms, CourtListener terms): tag by reference; record sources; attorney review before publication.
6. **Agent mishaps** (silent test weakening, data deletion, dependency tricks): guardrails above.
7. **Reviewer fatigue:** queue capped, routing by risk, nothing blocks on review except tier 3.
8. **Single-person dependency:** runbook, pinned toolchain, documented credentials location, `NOT_COVERED.md`.

## 13. Open decisions (for Danielle, none blocking the local work)

- Approve the 55 GB opinions pull after the counts are in (staged plan in brief section 29).
- FOLIO versus LMSS as primary tag vocabulary; whether to ask SALI or FOLIO about license and contribution (not now).
- Whether to take the legal questions (UPL, liability, site terms, headings) to an Indiana attorney before phase 5.
- Entity and domain for any public surface (`indianacle.com` is recorded as Cloudflare-managed).
- Which of the tools beyond Claude Code to trial first (suggest Codex as reviewer on one PR).

## 14. Not authorized by this document

Hosting, publication, DNS or domain work, connector registration or directory submission, third-party messages, accounts, credentials, licenses, merging, creating issues or work orders, and dispatching any tool.
