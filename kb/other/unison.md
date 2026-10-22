# unison
<!-- unison bucket=other project=unison updated=1792654861 -->

## Overview
- Unison is a local work tracker for tasks, Claude sessions, and git activity, organized into buckets mapped by GitHub remote (folders as fallback). Work area: Other.
- Runs locally in the browser UI with a bottom-docked command bar and a Claude Code skill for writing tasks. Repo: /home/fatikh/projects/unison.

## Current state
- Board tab (pinboard and lanes with drag and drop) and Activity tab are both in place.
- Command bar supports tab completion, batch add, due dates and deadlines with times, and rename.
- Each bucket gets a daily Claude-written summary; commits are linked to the Claude sessions that produced them.
- Card stats are bottom-aligned; activity filters were removed.

## Open threads
- none

## Decisions
- 2026-10-22: Map buckets by GitHub remote, with folder names only as fallback, so repos are grouped by identity rather than local path.
- 2026-10-22: Split the UI into Board and Activity tabs to separate planning from the activity feed.
- 2026-10-22: Remove activity filters, since the command bar covers finding items.

## Gotchas
- Primary working directory for the agent is /home/fatikh/projects/unison/data, not the repo root.
- none

## Links
- /home/fatikh/projects/unison (repo)
- /home/fatikh/projects/unison/data (data directory)

## Notes

_Your own notes. Unison adds to this section but never rewrites it._
