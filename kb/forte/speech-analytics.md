# speech-analytics
<!-- unison bucket=forte project=speech-analytics updated=1792654773 -->

## Overview
Speech analytics service for contact-centre call transcripts: an LLM engine that extracts topics, sentiment, KPI scores and summaries through organisation-specific pipelines. Built with FastAPI, Celery/Beat, async SQLAlchemy, PostgreSQL, Redis and LiteLLM, on port 8001 behind the Django BFF. Used by the Forte team for Rangers, Premier, VL/BSC and other pipelines.

## Current state
- Premier auto-evaluation follows the 21.10.2026 checklist. Calls without a client still score the operator. `score_version` stays at 6. Pushed to `feature/premier-checklist-21-10`.
- Premier wrongly deducted 25 points for the normal word «минуту», treated as a diminutive, so a call scored 77 instead of 100. The prompt fix is ready and awaits approval.
- Outbound ВЛ/Solo calls are scored exactly like inbound ones. Pushed to `feature/vl-outbound-same-as-inbound` with the requeue script removed. Not yet merged into `dev`.
- GitLab CI/CD auto-deploys `dev` on every push and blocks the deploy when tests fail.
- Rangers pipeline, auto-evaluation API and call card use the `connid-audios` endpoint. The UR report was reworked to match the client's requirement.

## Open threads
- Approve the «минуту» prompt fix and choose whether it ships as `premier-v5` or stays `premier-v4`.
- Deploy the 21.10 checklist changes, then reprocess Premier "Разговор не состоялся" calls.
- Merge `feature/vl-outbound-same-as-inbound` into `dev`, set `VL_CALL_DIRECTIONS=Inbound,Outbound`, then trigger `/process-vl-celery`.
- Confirm with the business whether Premier criterion weights should sum to 105, as the 13.10 sheet has them.
- Rangers UR: decide whether to add a single whole-range UR option, and whether to fix Срыв undercounting.
- Rangers: decide which scores to focus on, and whether «Не применимо» should count differently in the charts.
- Premier endpoints were overwritten in recent commits (reported 2026-10-09). Not yet resolved.
- Premier pipeline on the dev server: not confirmed as enabled.
- Diagnose the Premier call that shows no auto-evaluation with a "skipped" response, likely scored under checklist version 4 or 5. Run the diagnostic SQL to confirm.
- Frontend specs not committed: the calls-per-operator chart (`docs/frontend_rangers_calls_per_operator_chart_ru.md`) and the zeroed-call, header and critical-tag spec. Review, commit, and send to the frontend team.
- Premier 5-second call: paste its `auto_evaluation` and transcript for review (waiting on user).
- LLM cost reduction: pull a week of per-stage numbers from the LLM spend dashboard to replace the estimates in `docs/llm_cost_optimization_before_after.md`.
- Knowledge base: add a Premier segment and a BSC category. Paste the ForteKnowledge categories response or its `openapi.json` (segments live there, not in cch-backend).
- Rangers: open a PR from `feature/rangers-auto-evaluation` into `dev` if not already open, and hand the spec to frontend.

## Decisions
- 2026-09-25: Keep the LLM (gpt-5.6-luna) for topic classification. Jev reached 66% agreement against the LLM's 88%, and splitting did not help.
- 2026-09-28: Rangers calls are scored with their own checklist and their own topic catalog, so they stay separate from other pipelines.
- 2026-09-28: Missing Rangers criteria are stored as NULL, so they don't count as zero.
- 2026-09-29: Auto-evaluation calls are identified by `connid`, so cch-backend needs no changes.
- 2026-09-30: The Rangers card blocks depend on `auto_evaluation` alone. Rangers uses the same `connid-audios` endpoint as normal analytics.
- 2026-10-01: GitLab CI deploys `dev` on every push, and failing tests block the deploy. Reason: automate dev deploys safely.
- 2026-10-02: Segments are handled in the ForteKnowledge service, not cch-backend.
- 2026-10-07: Premier operators are not penalised for ASR errors or bilingual speech. Reason: scoring should be fair to operators.
- 2026-10-13: Premier is scored by the 13.10.2026 five-criterion checklist. Superseded on 10-16 and 10-21.
- 2026-10-13: Rangers UR report reworked to match the client requirement.
- 2026-10-21: Premier calls without a client still score the operator. `score_version` stays at 6 to avoid reprocessing all calls. Reason: the 21.10 checklist requires it.
- 2026-10-22: Outbound ВЛ/Solo calls are scored like inbound ones. Supersedes the separate outbound checklist from 10-20. Reason: the team wants the same scoring for both directions.

## Gotchas
- Service port is 8001. The Django BFF on 8000 is the upstream consumer.
- Env vars: `DATABASE_URL_TEXTS`, `REDIS_URL`, `LITELLM_BASE_URL`, `LITELLM_API_KEY`, `NLP_SERVER_URL`, `VL_CALL_DIRECTIONS` (currently `Inbound` only; set to `Inbound,Outbound` after merge). LiteLLM key is in the environment, not in the repo.
- Celery queues: `fresh_queue`, `backlog_queue`, `maintenance_queue`.
- Changing `score_version` requires reprocessing. Bumping it means re-running every affected call.
- Premier checklist files differ by date. Use the newest one, and check its criterion weights.
- CI tests run with a placeholder database URL. CI runs in Almaty time; a bug in the image's timezone offset was fixed on 2026-10-02.
- Use only status constants available in the pinned starlette version.
- Rangers test calls are copied from prod into dev's `classification_results` with DBeaver's Export data, then processed with `/process-rangers-celery`.
- Benchmarks and datasets were moved to another folder in `forte/`. Location not recorded.

## Links
- Branches: `dev`, `feature/premier-checklist-21-10`, `feature/vl-outbound-same-as-inbound`, `feature/rangers-auto-evaluation`, `feature/rangers-pipeline`
- Endpoints: `/process-vl-celery`, `/process-rangers-celery`, `/api/speech_analytics/v1/api/analytics/summary/connid-audios?connid=<id>`
- Docs: `docs/frontend_rangers_calls_per_operator_chart_ru.md`, `docs/llm_cost_optimization_before_after.md`, classification benchmark report in `docs/`
- Checklists: «чек лист Премьер для оценки для РА» 13.10.2026, 15.10.2026 (and 15.10.2026-1), 20.10.2026 (used for the 21.10 update)
- Specs: «РА автоматическая оценка для КЦ Премьер 02.09.2026.docx»
- Reference CI/CD: `forte/chat-analytics`

## Notes

_Your own notes. Unison adds to this section but never rewrites it._
