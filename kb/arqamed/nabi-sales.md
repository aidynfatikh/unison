# nabi-sales
<!-- unison bucket=arqamed project=nabi-sales updated=1792654913 -->

## Overview
- nabi-sales (ArqaMed work area): Sales AI, a Telegram Mini App for AI-assisted lead analysis and Meta (Facebook/Instagram/WhatsApp) ad campaign management.
- Stack: Next.js 15 (App Router, TypeScript, Tailwind) with Prisma, FastAPI backend (Alembic, Redis), grammy Telegram bot, Watchtower alerting bot, PostgreSQL. Runs on DigitalOcean droplet `salesbot` (prod and dev).
- Audience: developer owner, plus datascience team for metrics queries.

## Current state
- Prod and dev are both back up after the server hang; they should come back on their own after a reboot.
- Droplet memory is still nearly exhausted, so it could hang again.
- Prod default social platform is Instagram (built-in default); dev default is WhatsApp (from an old saved draft). Both should be WhatsApp.
- Last commit: fix(autopilot) hid the autopilot toggle until it does something (2026-09-07).

## Open threads
- Decide whether to upgrade the droplet's memory to prevent another hang.
- Confirm whether WhatsApp should become the default channel for everyone on dev (and fix prod to match).
- Email metrics on prod were requested (2026-10-08) to be pulled via DB query only; no result recorded.

## Decisions
- 2026-09-25: Treat WhatsApp as the intended default social platform on both prod and dev, because the mismatch was caused by stale drafts and cache rather than intent.
- 2026-09-07: Hide the autopilot toggle until it has an effect, because a no-op toggle confused users.

## Gotchas
- Two migration systems share one DB: Prisma owns CamelCase tables, Alembic owns snake_case tables. Never write across them. Enforced by `backend/tests/test_ownership_boundary.py`; allowlists only shrink.
- `docs/ERRORS.md` is generated: edit `backend/app/errors.py`, then run `cd backend && python scripts/gen_errors_doc.py`. `errors.py` must stay stdlib-only because the watchtower image copies it.
- Read `HISTORY.md` before touching `backend/app/meta/client.py` or `backend/app/meta/objectives.py`; update it in the same change when reasoning shifts.
- Watchtower has its own bot token (`WATCHTOWER_BOT_TOKEN`) and depends only on `postgres`, so it keeps working if the app goes down.
- Env vars needed: `DATABASE_URL`, `TELEGRAM_BOT_TOKEN` (exact name), `BACKEND_URL`, optional `INTERNAL_API_KEY` (must match backend). Mini app users enter their own AI keys during onboarding, not via .env.
- Local stack: `docker compose up -d` starts postgres, redis, backend, and runs migrations. If Prisma types are missing after a schema change, run `npm run db:generate`.
- Prod access is via `ssh salesbot`. Restart requires DigitalOcean access, which was unavailable during the hang.

## Links
- Repo: /home/fatikh/projects/salesbot
- watchtower/README.md
- docs/ERRORS.md
- docs/CHANGELOG.md
- HISTORY.md
- backend/tests/test_ownership_boundary.py
- backend/app/errors.py
- backend/scripts/gen_errors_doc.py
- prisma/schema.prisma

## Notes

_Your own notes. Unison adds to this section but never rewrites it._
