# datathon
<!-- unison bucket=uni project=datathon updated=1792654830 -->

## Overview
DATATHON is a registration portal for a datathon: email sign-up with verification, team building by invite code or link, and roster management for team leaders. Stack is Next.js 16 (App Router, Server Actions) with TypeScript, PostgreSQL + Prisma, Redis, Auth.js v5, Google Apps Script mail relay, and Tailwind v4. It runs in production at datathon.com.kz and is for event organizers and participants.

## Current state
- Live at datathon.com.kz; the 1200-participant cap and registration deadline lock are in place, with team edits locked at the deadline.
- Case tab reveals the dataset Drive link only to eligible teams (verified, 2+ members) from 12:00 Astana time; the server-only module keeps the link out of client code.
- Admin panel at /admin (analytics, participants, teams, bans), plus password reset by email and profile editing on the dashboard.
- Recent work is mostly organizer ops: participant CSV exports, a one-time Telegram invite email to ~1,185 participants (1,117 joined so far), and a CV export script on the server.
- Last activity 2026-10-19: CV export named "Name - Team.pdf" pending a run of `~/export-cvs.sh`.

## Open threads
- Run `bash ~/export-cvs.sh` on the datathon server and check `~/datathon-cvs-by-team`.
- Decide whether to send the remaining 68 Telegram invites now (200-email reserve) or wait for the quota to refill.
- Before 12:00 Astana time on the hackathon day: make the Drive folder shareable, and confirm the /case countdown with a participant account.
- Confirm the Telegram invite and password reset emails reach inboxes in production.
- Check the borderline international and under-16 cases in `~/datathon-exports/participants.csv` against the eligibility rules (Kazakhstan teams need at least one member 18+).
- Verify the Case tab and the "name taken" team notice on production (not yet tested there).
- Decide whether to drop the unused Invite database table.
- Pending commits: uncommitted verification-page changes, and the login rate-limit bypass fix flagged in review (2026-10-04), still open.
- Rotate the admin account's password and authenticator key on the server (they passed through chat on 2026-10-06).

## Decisions
- 2026-10-01: Send email via Google Apps Script relay instead of Resend, because it sends through the NU account and is more trustworthy for deliverability.
- 2026-10-01: Zero-downtime deploys through a self-hosted runner, so pushes to main release without downtime.
- 2026-10-06: Remove email team invites; teams join by code or link only, to simplify the join flow.
- 2026-10-10: Cap registration at 1200 confirmed accounts, after which only login is allowed, so the limit is enforced server-side.
- 2026-10-16: Lock all team changes at the registration deadline, enforced on the server.
- 2026-10-17: Reveal the dataset link only at hack start and only to eligible teams, kept in a server-only module.

## Gotchas
- Without a mail relay configured, no mail is sent; verification and invite links print to the dev server console.
- Local dev runs on ports 3100 (app), 5433 (Postgres), and 6380 (Redis), per docker-compose.yml.
- Event dates, deadline, and FAQ live in `src/lib/event.ts`; the server guards read from it, so changing it changes behavior.
- Auth checks belong in `src/lib/dal.ts`; `src/proxy.ts` is only an optimistic cookie check, not protection.
- Leader permissions are re-verified against the DB in `src/lib/teams/service.ts`, never trusted from form input.
- `npm run test:race` checks the roster limit under concurrent joins; run it after touching team logic.
- Production migrations use `npm run db:deploy`.
- Next 16 renamed middleware to proxy; read `node_modules/next/dist/docs/` before writing Next code.
- Participant data exports (CSV, CVs) are on the server under `~/datathon-exports` and `~/datathon-cvs-by-team`; treat as personal data.

## Links
- https://datathon.com.kz (production)
- https://t.me/+hpgk_VJ6r3wzNTQy (official Telegram chat)
- docs/deploy.md (deploy and CI/CD)
- scripts/gas-mailer.gs (Apps Script mail relay)
- src/lib/event.ts, src/lib/dal.ts, src/proxy.ts, src/lib/teams/service.ts
- Branch: main
- Repo: /home/fatikh/projects/datathon

## Notes

_Your own notes. Unison adds to this section but never rewrites it._
