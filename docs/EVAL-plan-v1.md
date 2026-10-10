# Evaluation plan v1: does the Indiana Code tool help an agent do legal research?

Status: **plan, not yet run.** Unofficial research aid; the answers produced are test material, not legal advice.

## Questions the evaluation should answer
1. **Accuracy:** on statutory questions, is an agent with the tool at least as accurate as the same agent with web search alone?
2. **Cost:** does the tool reduce tokens, tool calls and wall time?
3. **Currency:** does it handle "as of a date" questions correctly and say so when it cannot (ambiguous dates, pending acts)?
4. **Honesty about limits:** when the answer lives in caselaw or court rules (not loaded yet), does the agent say so instead of presenting a statute as the answer?
5. **Hallucinated authority:** how often does each condition cite a section, case or rule that does not exist or does not say what is claimed?

## Conditions (same model, same system prompt, fresh session per run)
- **A0 memory only:** no tools. Shows what the model already "knows".
- **A web search:** web search and fetch only.
- **B tool:** the local MCP server only (`indiana-code`, six tools).
- (**C tool plus web**, later, if B alone shows gaps.)
System prompt for all: "You are an Indiana legal research assistant. Answer concisely, cite the sources you relied on, give the date of
the text you used, and say plainly if you cannot answer from your sources. This is not legal advice."
Each question is run 3 times per condition to see variance. Record the store's SHA-256, tool version and date for every run.

## Question set (10)
| # | Question | Type | Expected anchors (hypotheses until Danielle's key replaces them) |
|---|---|---|---|
| 1 | What is the sentencing range for a Level 3 felony? | statute lookup | IC 35-50-2-5(b): 3 to 16 years, advisory 9, fine up to $10,000 |
| 2 | When modifying child custody, does the trial court need to enter special findings? | caselaw and rules | statute IC 31-17-2-21 (and 31-14-13-6) sets the standard; the findings requirement likely comes from Trial Rule 52 and cases (not loaded) |
| 3 | Is a school a body politic subject to sovereign immunity? | mixed | ITCA definitions (IC 34-6-2.1-77, -155) and immunities (IC 34-13-3-3); school statutes in Title 20; likely caselaw |
| 4 | What agency, if any, oversees lemon laws and vehicle sales? | statute and agency | IC 24-5-13 (lemon law; informal procedures certified by the attorney general, IC 24-5-13-19); dealer regulation under IC 9-32 (dealer services division); to confirm |
| 5 | What is the statute of limitations under the ITCA? | mixed | notice within 180 days for political subdivisions (IC 34-13-3-8) plus the general limitation and state-claim notice; caselaw likely |
| 6 | What was the definition of "fertilizer material" on March 1, 2026, and did it change on July 1, 2026? | date-sensitive | IC 15-16-2-11; the 2025 text on March 1; P.L.98-2026 effective July 1, 2026 |
| 7 | Who may make a will in Indiana? | statute lookup | IC 29-1-5-1 |
| 8 | What did IC 99-1-1-1 say? | negative control | no such section; the agent should say so |
| 9 | What did IC 3-11-13-11 say on March 1, 2026? | ambiguous date | three 2026 acts with different effective dates; the tool flags it ambiguous; a good answer says the text cannot be pinned down |
| 10 | What did P.L.98-2026 change in the Indiana Code, and when? | act question | the clauses listed by the tool; web search may find only a summary |

## Grading
- **Key first.** Before any run, Danielle (JD) writes the expected answer and the controlling authorities for each question
  (statutes, rules, cases). The hypotheses above are placeholders.
- **Blind rubric.** Answers are shuffled and stripped of condition labels. For each answer Danielle scores 0 to 2 on: correct answer;
  controlling authority cited; currency and date handling; appropriate limits and hedging. She also flags any invented or
  mischaracterized authority and says whether she would rely on it.
- **Automatic checks:** every section id cited exists in the store; every quoted passage appears in the cited section's text at the date
  claimed; tokens, tool calls and wall time from the run logs.

## Low-effort mode (Danielle has little time, 2026-10-10)
- **Draft key by Claude, check by Danielle.** For questions answerable from statute text (1, 4, 6, 7, 8, 9, 10) the key is derived from the loaded
  statute text and act clauses and shown as a one-page list of "question, expected answer, authority"; Danielle only marks each line agree,
  disagree or unsure (about ten minutes). For questions 2, 3 and 5 the draft lists the likely authorities as unverified and she marks them the same way.
- **Grade disagreements only.** Automatic checks run on every answer; Danielle blind-grades only the answers where conditions disagree with each other
  or with the key, plus any answer flagged for an invented or unsupported authority.
- **Pilot first.** One question run once per condition to check mechanics and cost before the full set.

## Mechanics (to confirm before running)
- Run non-interactively with Claude Code's print mode (`claude -p`, JSON output, `--allowedTools`, `--mcp-config`); this uses Danielle's
  subscription and may need her to renew the CLI login. Alternative: run by hand in Claude Desktop with the connector toggled.
- Condition B starts the local server over stdio with `INDIANA_LAW_DB` set; conditions A0 and A disable it.
- Keep transcripts locally; do not commit them (they may be long and contain model output about real statutes only, no personal data).

## Decision rules
- Tool is **good enough to publish as a connector** only if, on questions 1, 4, 6, 7, 9 and 10 (statute-answerable), it matches or beats A on
  accuracy, never invents authority, and flags ambiguity and pending acts in at least 8 of 9 relevant runs.
- Questions 2, 3 and 5 are **expected to expose the caselaw gap**; success there means the answer says what the statute covers and where
  the rest is likely to be found, not a full answer.
- Any invented authority attributable to the tool's output (not the model) blocks release until fixed.

## Known weaknesses of this design
Ten questions and three runs is a smoke test, not a benchmark; one grader; the same model family on both sides; web search results vary
by day; memory-only answers may be right for famous provisions; the grader knows the topic and may infer condition from style.

## First findings from preparing the set (tool side only, 2026-10-09)
Running the five questions Danielle proposed through the search tool showed that all-words matching missed relevant sections (for example
ITCA notice and lemon-law chapters), so search now falls back to ranking sections that match any of the words and says so in `flags`.
After that change the tool surfaced IC 34-13-3-8, 34-13-3-3, 24-5-13 and 9-32-13 sections. These are leads for the key, not answers.
