---
name: unison
description: Write tasks and knowledge notes into the user's Unison tracker (http://unison) in a concise format, update or complete tasks, and look up project knowledge pages. Use when the user asks to add, note, track or remember a task, todo, reminder, deadline or fact ("put this on my board", "remind me to…", "add a task for…"), asks to turn notes, a message, meeting notes, a plan or this session's next steps into tasks, asks what is on their board, or says a tracked task is done.
---

# Unison tasks

Unison is the user's own task board. Everything goes through the `unison` CLI, which is on PATH. Don't touch its database directly.

## Writing a task

One task per line, in this format:

```
<title> [@bucket] [!due <date> [time]] [*]
```

**Title**
- Imperative and concise: 3–8 words, a verb first. "Fix CCH auth token refresh", not "I need to look into fixing the auth issue".
- Keep the specifics that make it actionable: project, feature, person, ticket or branch names.
- Drop filler, politeness and context the bucket already gives ("for Forte", "task to").
- Write it in the language the user used. Keep their terms as they are, including Russian or Kazakh product terms.
- Never put `#`, `@`, `!` or `*` inside the title text. Those characters are syntax.

**@bucket**: pick from the content. If nothing points to a bucket, leave `@` off, and Unison uses the bucket of the current folder.

| bucket | what belongs there |
|---|---|
| `@forte` | Forte job: speech-analytics, cch-backend, chat-analytics, bt-assistant, forte-knowledge, Premier/ВЛ scoring |
| `@uni` | University: courses (SWE, PHIL, KAZ, AI, ALG, CSO, DB, PL), assignments, exams, datathon |
| `@arqamed` | ArqaMed / NABIPRO-Labs: ArqaMed CRM, Senimai voice agent, pbx-core, saq, konak, Kalqan, DENTRO, uyren-ai, nabi-sales |
| `@zap` | ZAP and ZAP-web |
| `@other` | personal and everything else |

**!due**: only when the user gave or clearly implied a deadline. Never invent one.
- Dates: `today`, `tmr`, `mon`…`sun` (the next one, or today if it's that day), `nextweek`, `+3d`, `+2w`, `30.10`, `2026-11-05`
- Times: `18:00`, `9:30`, `6pm`, written after the date: `!due fri 18:00`. Shorthands also work: `!fri@14:00`, and `!18:00` for today.
- "End of day" → `18:00`. "Morning" → `10:00`. "By Friday" → `!due fri`.

**\***: pin. Use it only when the user calls something urgent, important or top priority, or explicitly says pin. Pinned tasks sit on the pinboard, so keep them few.

## Adding

Before adding more than one task, run `unison ls` and skip anything already on the board under a similar title.

One task:
```bash
unison add -- 'Fix CCH auth token refresh @forte !due fri 18:00'
```

Several tasks:
```bash
unison add - <<'EOF'
Finish AI call analysis @arqamed !due today 18:00 *
Replace shoe-store KB with clinic info @arqamed
Submit SWE assignment 4 @uni !due 30.10 23:59
EOF
```

Pass `--cwd "$PWD"` if you are not in the folder the user is working in.

**Extracting tasks from notes, messages or a session:** one task per concrete action the user owns. Skip things other people will do, unless the user has to chase them; then write e.g. "Chase Abylay for prod DB access". Merge duplicates, and keep it to the handful that matter rather than every sentence.

## Updating

Find the id with `unison ls` (the number in `[n]`), then:

| command | effect |
|---|---|
| `unison done <id>` | complete |
| `unison doing <id>` | in progress |
| `unison todo <id>` | back to open |
| `unison pin <id>` / `unison unpin <id>` | pin / unpin |
| `unison rm <id>` | delete; only when the user asks |
| `unison due <id> fri 18:00` | set the deadline (`none` clears it) |
| `unison rename <id> -- '<new title>'` | change the title |

Several ids work at once: `unison done 4 7`.

## Knowledge base

Each project has a markdown page at `~/projects/unison/kb/<bucket>/<project>.md` with these sections: Overview, Current state, Open threads, Decisions, Gotchas, Links, Notes. Unison rewrites everything above Notes from recent activity. The Notes section belongs to the user and is only ever added to.

| command | effect |
|---|---|
| `unison kb read <project>` | show a project's page (`@bucket` shows that bucket's general page) |
| `unison kb search <words>` | search pages, sessions, commits, tasks and summaries |
| `unison note -- '<fact> [@bucket] [+project]'` | add a dated line to the page's Notes (defaults to the current folder's project) |
| `unison kb refresh <project>` | rewrite the page from recent activity |

**Notes:** use them for durable facts the user asks you to remember, or that you'd want next time: a decision and its reason, where something lives, a gotcha, a contact. Keep each to one line, and never include secret values.

**Questions about a project's history or state:** read its page first.

## Reporting back

Reply with the `added …` / `done …` lines the CLI printed, and nothing else unless something was skipped as a duplicate or was ambiguous. No preamble.
