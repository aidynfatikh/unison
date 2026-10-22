# ZAP
<!-- unison bucket=zap project=ZAP updated=1792654780 -->

## Overview
ZAP is a monorepo for a friends-based challenge app: users take short real-life challenges together, record them, earn Zaps and spend them at partner businesses. Stack: Flutter app (`mobile/`, iOS first, Android from the same code), FastAPI modular monolith on Postgres (`backend/`), API contract in `contracts/`, infra in `infra/`, plus a web demo built from the Flutter app and hosted on Vercel. Owners: Рамазан (mobile), Фатих (backend), Даурен (infra).

## Current state
- Web demo is deployed to Vercel (`zap-demo`) from a copy of the build, and the demo feed opens with the live push-up challenge; MediaPipe pose counting runs in the browser.
- Live exercise checks are built end to end: the backend judges results on the server, and the phone counts reps with ML Kit pose detection and a 3-2-1 countdown.
- Your `exercise-checks` branch rebases cleanly onto `main`, but it stores checks differently from the new backend plan and ADR 0005.
- Demo deploy check fails only because the repo has no `VERCEL_TOKEN` secret; the code is fine.

## Open threads
- Add the `VERCEL_TOKEN` secret to the repo (owner: SuWh1), then re-run the demo deploy so it redeploys on each push to `main`.
- Decide with the backend plan's owner which check storage shape to use before writing backend code for `exercise-checks`, per ADR 0005.

## Decisions
- 2026-10-19: Build the web app from the Flutter app, not as a separate codebase, so the mobile UI and logic are shared.
- 2026-10-19: Keep a browser's refresh token in an HttpOnly cookie, so scripts on the page cannot read it.
- 2026-10-19: Give challenges a check type and have the server judge the app's results, so the phone's count is not trusted alone.
- 2026-10-20: Deploy the demo from a copy outside the repo, because Vercel refuses deploys whose last commit author is not on the Vercel account.

## Gotchas
- Vercel demo: run `make mobile-vercel SITE_URL=... VERCEL_API=...` and deploy from `/tmp/tryit-web/`, not from inside the repo.
- The cloudflared tunnel URL changes on every start; repeat the mobile-vercel and deploy steps after a restart.
- The dev API signs anyone in by name. Keep only demo data in that database and stop the tunnel when the demo ends.
- `API_HOST=0.0.0.0` exposes the dev API to the whole Wi-Fi network; never use it on a server.
- Figma token lives in `~/.figma-token`; never print or commit it. The free plan allows about 6 requests a month, and `make figma` costs 2 per pull.
- Local Postgres runs in Docker on host port 5433; never remove its volume.
- Commit messages follow `<type>: <subject>`; the `/clear` session does not affect the repo.

## Links
- Repo: /home/fatikh/projects/ZAP
- Branch: exercise-checks (your branch, rebased cleanly on main)
- Demo: https://zap-demo.vercel.app
- Docs: docs/architecture.md, docs/adr/ (incl. ADR 0005, ADR 0007), docs/deploy.md, docs/product/user-flow.md#lifecycles, docs/product/design.md, docs/product/design-<date>/
- Contract: contracts/openapi.json

## Notes

_Your own notes. Unison adds to this section but never rewrites it._
