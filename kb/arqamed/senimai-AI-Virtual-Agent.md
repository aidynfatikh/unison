# senimai-AI-Virtual-Agent
<!-- unison bucket=arqamed project=senimai-AI-Virtual-Agent updated=1792654712 -->

## Overview
Senimai is the AIVA SaaS: AI bots for messengers, an AI voice agent for phone calls, and an AI layer over the ArqaMed clinic CRM that analyses finished calls and writes results back into deals. Stack: pnpm monorepo with Next.js 16 web, Hono API, BullMQ worker, Postgres 16, Redis 7 and Drizzle, plus Aikon telephony, OpenAI Realtime, ElevenLabs and Yandex for voice. Runs on senimai.kz (prod), dev.senimai.kz and stage, for clinics on ArqaMed and the bot owners who run them.

## Current state
- Voice: an operator "typing" keyboard sound now fills the bot's thinking pauses (22 Oct). The "а ещё есть?" slot fix and per-line call labels in the log are also in. Dev has the 21 Oct fixes, knowledge base cleanup and prompt edits, but no new test calls yet.
- The step-by-step engine «Пошагово» (Realtime listens, GPT decides, ElevenLabs speaks) is being tested against the current engine on dev. Simulations showed no CT option in ArqaMed, slow replies and a chat double-booking bug.
- PR #119 (Kazakh support plus ElevenLabs hearing) is pushed to dev and deployed to stage. Stage test calls have not run yet.
- Prod uses ElevenLabs, but the «Поддержка» bot still has the Nastya voice even though Kari is deployed.
- main and dev were in sync as of 21 Oct. The only unmerged remote branch is kadys's owner Telegram notifications branch.

## Open threads
- Approve the Kazakh provider comparison (Yandex vs OpenAI vs ElevenLabs) on dev: about 5 minutes and under $1.
- Run stage test calls for PR #119: the «Саламатсыз ба» greeting and a full КТ booking.
- Make test calls on dev after the 21 Oct fixes and report them for review.
- Decide which simulation issues to fix first: no CT in ArqaMed, slow replies, chat double-booking.
- Switch the «Поддержка» bot to the Kari voice and make a test call.
- Check the operator typing sound on a live call.
- Confirm the «ага» barge-in and stutter fixes (14 Oct) on a live call.
- Turn on «Записывать на приём» for one channel in «Предлагать» mode and check its suggestions.
- Review kadys's owner Telegram notifications branch, if wanted.

## Decisions
- 2026-10-22: Operator keyboard sounds fill bot pauses, to make silence sound natural between answers.
- 2026-10-21: Add the «Пошагово» engine: Realtime listens, GPT decides, ElevenLabs speaks. It combines Realtime's listening with ElevenLabs voice quality, and it is still under evaluation.
- 2026-10-17: Calls use ElevenLabs for speech while OpenAI does the thinking, because ElevenLabs has better Kazakh and accent.
- 2026-10-17: Campaign script outranks the bot description. Model choice is per bot, and call cost is tracked, to reduce cost.
- 2026-10-17: Caller speech is transcribed with gpt-4o-transcribe plus a term dictionary, for more accurate transcripts.
- 2026-10-14: Barge-in is handled by the runtime, not the model, so a short «ага» does not cut the bot off.
- 2026-10-12: Voice defaults are tuned so the user only tunes the bot's task and behaviour, not its voice quality.
- 2026-10-05: Automatic booking from analysed calls stays off until a clinic enables «Записывать на приём», to avoid unwanted bookings.
- 2026-10-02: Each bot has one task list with «Где работает» checkboxes for chat and calls (both on by default), because a bot does the same work in both.
- 2026-09-30: Call analysis runs through the bot's tasks instead of separate custom logic, to avoid duplicating it.
- 2026-09-25: CRM write-back starts in shadow mode, off per channel until the owner enables it, for safety.
- 2026-09-29: Stereo per-channel transcripts are part of the ArqaMed contract, so operator and patient speech stay separate.

## Gotchas
- Pushes to `dev` auto-deploy stage. Prod runs `main`, so dev features are not on prod until merged.
- Campaign calls only go out inside calling hours, which default to weekdays 10:00–19:00. Add Saturday under «Сценарий и правила» if needed.
- When account access expires (14-day trial, then 3 days grace), the bot goes silent for replies and calls. Check the subscription before debugging a silent bot.
- The platform admin is a database flag, set only with `node dist/create-admin.js` on the server.
- The dev server is reached with `ssh senimai`. Its disk filled up on 23 Sep; size limits are now active.
- ElevenLabs prompts must not say "нажмите" or "напишите", because the person only hears the bot.
- The campaign dialer runs in the worker as a 10-second pass. `apps/voice` matches an answered call to a campaign by MD5(call_id).
- Useful commands: `pnpm check`, `pnpm db:migrate`, `pnpm db:seed`, `pnpm dev`, `pnpm --filter @aiva/api dev:worker`.
- API keys live in `.env` (copied from `.env.example`) and in the server environment. Never commit their values.
- Sibling repos on this laptop: projects/arqamed and projects/pbx-core.

## Links
- https://senimai.kz (prod)
- https://dev.senimai.kz (dev)
- https://arqamed.com (ArqaMed CRM)
- PR #119 (Kazakh support plus ElevenLabs hearing)
- Unmerged branch: kadys's owner Telegram notifications
- /home/fatikh/projects/senimai-AI-Virtual-Agent: CLAUDE.md, README.md, apps/api/CLAUDE.md, docs/arqamed-ai-layer-contract.md, docs/conventions.md, packages/db/CLAUDE.md, packages/db/src/schema/crm.ts, packages/shared/src/subscription.ts, apps/api/src/pipeline/campaign-dialer.ts
- Aikon integration spec (Markdown, written 12 Oct; path not recorded)

## Notes

_Your own notes. Unison adds to this section but never rewrites it._
