# konak
<!-- unison bucket=arqamed project=konak updated=1792654937 -->

## Overview
konak is a hotel PMS (property management system) built on Next.js, with Better Auth for authentication, Prisma on Postgres for data, and tRPC for the typed API. It runs as a release-based deploy to /srv behind nginx and pm2, with production at konaq.kz and a dev instance at dev.konaq.kz. Work area is ArqaMed; the product is for hotel staff, including the front desk, rates, and analytics.

## Current state
- Booking-form dates, the шахматка numbers, and the header scrollbar are fixed and live on konaq.kz (2026-09-26).
- The interface is simplified: one Настройки entry, tabs in the top bar, one hotel switcher, and more of the UI in Russian (live on konaq.kz).
- CRM deals connect to bookings both ways, live on konaq.kz and dev (2026-09-22).
- Kontur.Отель parity work for rates is through Stage A (A.14–A.21), with price screen and restrictions in place.
- dev.konaq.kz is still running an older build than konaq.kz.

## Open threads
- Redeploy dev.konaq.kz to the latest version (it still runs the previous build).
- Decide the next step on the calendar UI design (Image #5) — the last session ended with /clear, so no recorded follow-up.
- Pick the next small item: fix the «Отменить» cancel toast wording, or sort the CRM attach list by arrival date.
- Merge /desk and /dashboard into one ArqaMed-style interface: the plan is in docs/plans/one-dashboard.md, no code yet; needs a go-ahead or requested changes to the plan.
- Verify a manual prod check remains needed: there is no CI/CD pipeline left, so deploys are checked by hand over ssh.

## Decisions
- 2026-09-18: Release-based deploys to /srv with nginx and pm2, with CI/CD — chosen as the deploy path.
- 2026-09-19: Kontur.Отель parity is tracked as a plan with screen specs and a checklist — to measure progress against the reference product.
- 2026-09-20: Prices are per stated number of guests, and children carry ages that the bands price — to match Kontur's rate model.
- 2026-09-21: The CRM funnel is on by default — to expose the CRM without an opt-in step.
- 2026-09-21: The desk uses Kontur's grid and rail layout, with money on the chip and a single Бронирования entry — to match the reference interface.
- 2026-09-24: Analytics are presented as ArqaMed's reports — to fit the product's own reporting style.
- 2026-09-24: Interface is simplified toward one Настройки entry, tabs in the top bar, and one hotel switcher — to reduce navigation clutter.

## Gotchas
- `toast.error(e.message)` must not be used: `authClient` returns `{ data, error }` instead of throwing, so failures look like success. Use `handleFormError` or `handleError` from `lib/errors.ts`.
- A schema `.default()` combined with `useForm` `defaultValues` silently resets the field; strip the default when deriving a form schema.
- `server/auth.ts` and anything it imports must use relative imports only (no `@/` aliases), because `auth:generate` loads it through jiti.
- Only `env.mjs`, `next.config.ts`, and `getBaseUrl()` in `server/provider.tsx` read `process.env`.
- A dialog without `<FormError />` fails silently on `form.setError("root")`.
- Generated migrations may drop hand-written constraints (exclusions, `room_stays_property_matches_reservation`); use `migrate dev --create-only`, remove the unintended drops, then apply.
- `styles/globals.css` is shadcn's and gets rewritten by the CLI; put custom styles in `styles/` beside it.
- `@/lib/storage` is `server-only`; client code imports `@/lib/storage/provider` for types and `@/lib/upload` to send bytes.
- Before finishing work, run everything in `package.json`; also run `test:server` when a router or schema changed, and `build` when routing or config changed.
- Seed script refuses to run with `NODE_ENV=production`; demo logins use a development password (see README, not recorded here).
- Commands: `npm run db:migrate`, `npm run db:seed`, `npm run dev`, `npm test`, `npm run test:server`, `npm run db:studio`, `npm run auth:generate`.
- Postgres runs via `docker compose -f docker/compose/db.yml up -d` (development only).

## Links
- docs/handoff.md (read first)
- docs/todo.md
- docs/plans/roadmap.md
- docs/plans/hotel-pms.md
- docs/plans/one-dashboard.md
- docs/guides/architecture.md
- docs/guides/ui-patterns.md
- docs/guides/local-development.md
- docs/history.md
- docs/kontur (parity plans and screen specs; path as referenced in commits)
- https://konaq.kz (production)
- https://dev.konaq.kz (dev)
- docker/compose/db.yml
- prisma/schema/identity.prisma

## Notes

_Your own notes. Unison adds to this section but never rewrites it._
