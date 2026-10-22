# hackathon
<!-- unison bucket=forte project=hackathon updated=1792654840 -->

## Overview
- ForteBank Datathon 26 hackathon project in the Forte work area: case document, participant datasets (open and closed), submission form, and scoring of team submissions.
- Local work in `/home/fatikh/forte/hackathon`; no hosted service mentioned.

## Current state
- Submissions from the Datathon are being evaluated on the closed test set.
- The 30-team shortlist matches the strict leaderboard for 25 teams, and the top 5 are identical.
- Open dataset and merged case-plus-FAQ docx were checked and are ready to share once the duplicate-video label is settled.
- Case document v2 has a point descriptor table and a cleaned-up section 5.

## Open threads
- Decide whether to add OISEREK to the shortlist.
- Decide how to break the large tie below place 5.
- Decide the label for duplicate videos Х-4 and Х-47 (or drop one), then rebuild the participant zip.
- Decide whether to add a scoring note under the points table, including how close a timecode must be to count.
- Decide whether the API answer gets a simple rule-reference field so criterion 4 can be scored automatically.
- Replace the YOLOv8 license example in the submission form with RT-DETR.

## Decisions
- 2026-10-15: Present the case scoring as a point descriptor table with point divisions, to make the criteria clear.
- 2026-10-16: Remove model restrictions from the case; the solution just has to run locally.
- 2026-10-17: Write the extra submission form fields in English, to match the case.
- 2026-10-17: Do not use Ultralytics YOLO, because its AGPL license is a problem; use RT-DETR (Apache-2.0) instead.
- 2026-10-18: Judge submissions on the closed test set, which participants have not seen.

## Gotchas
- Open dataset contains only video timestamp and verdict, with no explanation text.
- Closed dataset is in `closed/`; its textual descriptions are in `Хакатон.xlsx`, so the last column is removed from the target output file.
- The Datathon submission CSV is named `Datathon solution submission .csv`, with a space before the extension.
- Tool working directory (`/home/fatikh/projects/unison/data`) differs from the project folder (`/home/fatikh/forte/hackathon`).

## Links
- `/home/fatikh/forte/hackathon`
- `Кейс_ForteBank.docx` (case rules)
- `Хакатон.xlsx` (textual descriptions and target output)
- `кейсы_беззвука/` (case videos)
- `closed/` (closed dataset)
- `Datathon solution submission .csv` (team responses)

## Notes

_Your own notes. Unison adds to this section but never rewrites it._
