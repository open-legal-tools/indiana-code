# Open Indiana citations (prototype)

`src/indiana_law/cite.py` parses and formats Indiana case citations built on the case number (Indiana Appellate Rule 22, amended
effective January 1, 2024), adds an optional paragraph pinpoint, makes permanent ids and permalinks, and resolves a pinpoint to the
official opinion PDF's page with the paragraph's opening words (the "jump").

## Forms
| | Example |
|---|---|
| Full, page pinpoint (Rule 22) | `Martinez v. State, No. 22A-CR-1196, at *4 (Ind. Ct. App. Jan. 26, 2023) (mem.), trans. denied` |
| Full, paragraph pinpoint | `Smith v. Jones, No. 25A-CR-1234, ¶ 23 (Ind. Ct. App. Oct. 3, 2025)` |
| Short | `Smith, No. 25A-CR-1234, ¶ 23` |
| Id. | `Id. at *5` or `Id. ¶ 24` |
| Permanent id | `ind:25A-CR-1234:p23` or `ind:25A-CR-1234:page-4` |
| Permalink | `/opinions/25A-CR-1234#p23` or `#page-4` |

The case number is written without zero padding and read with or without it. The court comes from the letter in the case number
(A = Court of Appeals, S = Supreme Court, T = Tax Court). Page numbers are the slip opinion's own "Page N of M".

## What the 176 opinions in the judicial-education project showed (2026-10-23)
- All 170 Court of Appeals opinions have bracketed paragraph numbers (169 are consecutive), and every one's "Page N of M" matches its PDF page.
- The 6 Supreme Court opinions have no numbered paragraphs, so they are cited by page.
- Three Supreme Court opinions append separate opinions (dissents) whose page numbers restart; a pinpoint into those needs the author named.
- One memorandum decision (SEP-07) has paragraph numbers the indexer cannot read past [27]; an edge case to examine.

## Resolver and history (prototype)

`case_resolve` (MCP tool) and `GET /opinions/{case number}` turn a case number or a Rule 22 citation into one opinion in the
extract: the canonical citation, the permalink, the source link, and a check that a paragraph pinpoint exists in the text.

- `/opinions/22A-CT-925` shows the opinion as plain text with an empty anchor before each numbered paragraph, so
  `/opinions/22A-CT-925#p23` jumps to paragraph 23 in any browser, with no script. Add `?format=json` (or send
  `Accept: application/json`) for the structured answer.
- Paragraph anchors use the ascending run `[1] [2] [3]...` only, so a cross-reference such as "[27]" inside paragraph 2 is not
  mistaken for a paragraph.
- Page pinpoints (`at *4`) are not resolved here: the extract holds plain text without page breaks. The official PDF indexer in
  `cite.py` (`index_pdf`) does that when a PDF is at hand.
- **History** is read from how later opinions in the extract write a citation of the case followed by `trans. denied`,
  `trans. granted`, `trans. dismissed`, `vacated`, `aff'd` or `rev'd`. It is evidence of what the court wrote later, not the
  docket, and not a citator; the answer says so and points to the court's docket.

## Not done yet
The reporter ("N.E.3d") cite when verified, a detector for citations inside later opinions that feeds a citator, official-PDF page
jumps from the server, and the choice of whether to propose "Op. Ind." as a shorthand. Tests: `tests/test_cite.py`,
`tests/test_resolver.py`.
