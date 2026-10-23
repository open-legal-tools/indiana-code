# Idea log

Ideas are logged here so they are not lost. An idea is **not** a plan, a priority or an approval. Each entry says who raised it, when, and what a first small test would be.

## 2026-10-09 (Danielle): our own annotation layer and a "web" of related authorities
Our own headnote-style annotations, kept apart from official text, relating statutes to each other and to court cases; over time a constellation of interrelated authorities
for AI agents and later human readers. First candidates: cross-references already in the Code ("see IC ..."), amending-act links, opinion-to-section citation edges.
Status: reflected in `docs/SPEC-ROADMAP-v2.md` sections 5 and 7 (proposition cards, tiered edges). Opinion-to-section text mentions started 2026-10-23 (`statute_mention` / `ic_cases_citing`); not treatment.

## 2026-10-09 (Danielle): funded digitization of the pre-2017 Code years
The 2009 to 2016 Code years exist only as PDFs. A funded project (nonprofit grants, a library or school partner) could digitize and parse them. Not pursued now.

## 2026-10-10 (Danielle): a simple "universal" case citation based on the case number
**The idea.** Cite an Indiana appellate decision as *case name, case number, pinpoint, (year)*, because the case number already shows the court; use the "(Ind. year)" parenthetical
only for Indiana Supreme Court decisions and omit "(Ind. Ct. App.)". She dislikes North Eastern Reporter citations. Example forms (illustrative only):
- Court of Appeals: `Steele v. Taber, 22A-CT-925, 5 (2023)`
- Supreme Court: `Smith v. State, 21S-CR-123, 5 (Ind. 2022)`
**What the data says (Observed, CourtListener dockets for the three Indiana courts, 2026-09-30).**
- Modern appellate case numbers look like `19A-CR-1441`: two-digit filing year, court letter (A appeals, S supreme, T tax), case-type code, sequence. In the dockets the sequence is sometimes zero-padded (`24A-PL-02536`),
  so a canonical form is needed.
- Older numbers differ: county-coded forms such as `02A05-1206-CR-331` and `49A02-1312-CR-1091` (year and month inside), Supreme Court transfer forms such as `71S03-1506-CT-350`, Tax Court `49T10-1406-TA-25`,
  numeric forms like `No. 6,912`, and about 18,000 older Supreme Court records with no docket number. So a number-based citation covers roughly 2018 onward cleanly; earlier years need a fallback (reporter citation or a stable id).
- Only about 103,000 of 122,000 Indiana dockets have a docket number.
**Design notes.**
- One case number can have several decisions (an opinion, a rehearing, a Supreme Court transfer opinion under a new number), so the machine id should be court + number + decision date + form, for example `indctapp:22A-CT-925:2023-01-17:mem`.
  The human string can be the short form above.
- The "year" in the parenthetical should be the decision year, not the filing year coded in the number.
- Pinpoint: slip-opinion page or paragraph; whether Indiana opinions carry usable pagination or numbered paragraphs is unchecked.
- Indiana's own rule already cites memoranda by number (Appellate Rule 22 example, agent-reported: `Steele v. Taber, No. 22A-CT-925 (Ind. Ct. App. Jan. 17, 2023) (mem.)`), so this is close to existing practice.
- Court filings must follow Rule 22 (agent-reported), so the tool should emit both: our short universal form and a Rule-22-compliant string on request. Do not present the short form as a replacement for filing practice.
- We would need our own detector for case-number citations inside later opinions, alongside eyecite.
**First small test.** Take 200 recent decisions, generate the short form and the machine id, and check that each is unique and resolves back to one record.

## 2026-10-10 (Danielle): detect memorandum decisions and decision form from the text
Her hypothesis: memoranda are present in the data but are not "hidden" because the source labels most records as published, so parse the text for the top-of-opinion disclaimer language and the
"Memorandum Decision" or "Opinion" wording in the footer, which also carries the case number. Consistent with the counts (pre-2021 yearly volumes of 1,900 to 3,800 suggest published decisions plus
memoranda; post-2022 volumes near 300 suggest published only), but **unconfirmed until the opinion text is extracted.** First test: count opinions containing the memorandum disclaimer, by year and status.
Recorded as a component-parsing task in `docs/SPEC-ROADMAP-v2.md` phase 2 (decision form and citability fields).
