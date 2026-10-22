# ArqaMed
<!-- unison bucket=arqamed project=ArqaMed updated=1792654887 -->

## Overview
ArqaMed is a multi-tenant dental clinic CRM with scheduling, sales funnels, patient management, and WhatsApp and phone channels. It runs on Next.js 16, React 19, TypeScript, Drizzle with Postgres 16, NextAuth, and TanStack Query. It is served from dev.arqamed.com and production, and is used by dental clinics such as Syzganov and НКЦ.

## Current state
- Latest activity is 2026-10-14: the API can book a phone appointment without a deal, and a phone booking can be pinned to one funnel.
- Sidebar rebuild (⌘K search, task-based menu) and per-department phone masking are committed on dev as of 2026-10-11. They were not pushed at that time, and push status after that is unconfirmed.
- Pushing dev deploys, so review before pushing.
- eOtinish and 1414 complaints are on dev. The complaints commit that needs a DB migration is not on prod yet.
- Deal-notes fix (2026-10-08) is live on production.

## Open threads
- Review and push the 2026-10-11 commits on dev (sidebar, department masks).
- Confirm the "Build and release" step passes for the eOtinish/1414 deploy. The previous run failed.
- Release the eOtinish/1414 complaints commit to prod. It needs a DB migration.
- Syzganov telephony move from Sipuni to AIkon: ask the clinic who owns their main number. The answer decides whether the number is ported or the trunk is re-registered on AIkon.
- Syzganov AIkon: add base URL, API secret and extension so КТ cards can call out.
- КТ funnel: the clinic sets doctor working hours in «Специалисты» and links КТ services to doctors. Booking currently shows «Выходной».
- КТ funnel on prod: new deals are not created when the existing deal is in Успешно реализовано, Закрыто, не реализовано or Удален, and records land in the deleted deal. Run the read-only query to find who deleted it. Confirm whether the «Удалить» button in Корзина was added.
- Senimai sandbox channel in Senimai dev is still to connect (unconfirmed).

## Decisions
- 2026-09-22: Keep WhatsApp providers on QR linking, not Meta's official API. All three providers already work this way, so Meta's pricing change has no effect now.
- 2026-09-17: Complaint threads reply only from the complaints number, and their deals are not touched by integrations or auto-stages. This keeps complaint conversations separate from routine ones.
- 2026-09-29: Call recording access is limited to users who can see the deal.
- 2026-10-01: A phone line is tied to a WhatsApp number, so both channels stay together in «Каналы».
- 2026-10-04: Sipuni stays on the main line and AIkon runs on a separate line. Senimai is enabled only on the SyzganovNSCS КТ line, so the main line is untouched.
- 2026-10-08: Notes and tasks work on deal cards whose number has no WhatsApp, and notes can be edited and deleted.
- 2026-10-09: eOtinish and 1414 appeals go into «Жалобы».
- 2026-10-11: Setup flow generates the AIkon webhook first and asks for the signing key after, since the key is only available once the webhook exists.
- 2026-10-11: Departments see masked phone numbers (+7 7•• ••• •• 34) instead of the full number.
- 2026-10-14: Phone bookings can be pinned to one funnel (appointments.funnel), and an API call can create an appointment by phone when the caller has no deal.

## Gotchas
- Pushing to dev triggers a deploy to dev.arqamed.com.
- Tenancy is enforced twice: `getTenantSession()` in route handlers, and Postgres RLS via `withTenant()`. The RLS migration is hand-written, so a new tenant table must be added to its list. Run foreign keys from request bodies through `assertRefsInTenant`.
- `src/proxy.ts` is the middleware. Page access is defined by the `PAGE_ACCESS` matrix in `src/lib/permissions/index.ts`. A page missing from it is denied.
- Lint is `continue-on-error` in CI, so a green CI does not prove lint is clean. Run `npm run typecheck`, `npm run test` and `npm run lint` before finishing.
- Use `TZ=America/New_York npm test` to match CI.
- Prod analysis is done read-only over `ssh arqamed`.
- Sipuni call-recording sweep runs every 10 minutes in the notification worker.
- Seeded login credentials are listed in docs/setup.md → Login Credentials. Do not copy them here.

## Links
- Repo: /home/fatikh/projects/ArqaMed
- Dev site: dev.arqamed.com
- Docs index: docs/README.md, overview: docs/overview.md, setup: docs/setup.md
- Scheduling: docs/architecture/scheduling.md
- Companies: docs/architecture/companies.md
- CRM tasks: docs/architecture/crm-tasks.md
- CRM automation: docs/architecture/crm-automation.md
- Backups: docs/operations/backups.md, scripts/backup-db.sh
- RLS migration: src/lib/db/migrations/0001_rls.sql
- Rules and conventions: AGENTS.md, CLAUDE.md
- Change log: HISTORY.md
- CI: .github/workflows/ci.yml

## Notes

_Your own notes. Unison adds to this section but never rewrites it._
