---
description: Add a task to the Unison board (e.g. /todo fix auth bug #forte !fri *)
argument-hint: <task> [#bucket] [!due] [*]
allowed-tools: Bash(unison:*)
---
Task text: $ARGUMENTS

If the task text is empty, run `unison ls` and show the output as-is.
Otherwise run exactly one command: `unison add --cwd "$PWD" -- '<task text>'` (escape single quotes in the text), then reply with only the line it prints. The bucket defaults to this folder's bucket; `#bucket`, `!due` (today, tmr, fri, +3d, 30.10, 2026-10-30) and `*` (pin) are parsed by unison itself. Do nothing else.
