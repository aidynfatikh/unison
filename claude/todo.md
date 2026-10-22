---
description: Add a task to the Unison board (e.g. /todo @forte fix auth bug !due fri 18:00 *)
argument-hint: <task> [@bucket] [!due <date> <time>] [*]
allowed-tools: Bash(unison:*)
---
Task text: $ARGUMENTS

If the task text is empty, run `unison ls` and show the output as-is.
Otherwise run exactly one command: `unison add --cwd "$PWD" -- '<task text>'` (escape single quotes in the text), then reply with only the line it prints. The bucket defaults to this folder's bucket; `@bucket`, `!due <date> [time]` (today, tmr, fri, +3d, 30.10; time like 18:00 or 6pm; also `!fri@14:00`, `!18:00`) and `*` (pin) are parsed by unison itself. Do nothing else.
