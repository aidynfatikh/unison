# chat-analytics
<!-- unison bucket=forte project=chat-analytics updated=1792654807 -->

## Overview
- chat-analytics is a Go service (Go 1.25, pgx/v5, cleanenv, godotenv, fpdf) in the Forte work area. It analyzes Chat2Desk operator chats with GPT and stores results in Postgres (`dl_results`).
- It runs as a daily worker plus an HTTP API and dashboard (`frontend/`), via Docker Compose (container :8080, host :8888). It is for the developer and the Forte frontend team.

## Current state
- CSI ratings and repeat-contact (FCR) work (spec items 2.1 and 2.2) is finished, tested on dev, and pushed. Last code commit: refactor(csi) 2026-10-16.
- The frontend guide `docs/csi-fcr-frontend.md` was rewritten on 2026-10-21: CSAT is removed and the ratings report is an existing tab. These edits are not yet reviewed or committed.
- Repeat-contact flag is maintained by DB triggers on `dialog_messages`. Ratings are copied into `client_rating` and linked to dialogs by triggers.

## Open threads
- Review `docs/csi-fcr-frontend.md` and decide whether to commit and push it. It includes the uncommitted 2026-10-21 edits and the 2026-10-16 update.
- Prod rollout, not confirmed as done: run `check_schema.sql`, run `repeat_contact.sql` if `is_repeat_contact` is missing, and run `client_rating.sql`. All of these run outside the 07:30 daily run. Then deploy.
- Run `check_csi_fcr.sql` on dev in DBeaver (Alt+X). Not run yet.
- Confirm CI passes for the 2026-09-28 commits. The code was not compiled in that session.

## Decisions
- 2026-09-24: Repeat-contact flag is set by DB triggers, and the script creates only the column and triggers. Why: data engineers own the mart.
- 2026-09-25: The repeat rule counts conversations from message history in `dialog_messages`. Why: not recorded.
- 2026-10-01: Ratings are copied into `client_rating` and linked to dialogs by triggers, with the Chat2Desk score in its own `rating_score` field. Why: not recorded.
- 2026-10-01: CSI and repeat-contact get separate filters, and the report and extra fields were moved out of the first iteration. Why: not recorded.
- 2026-10-16: Bot IDs are constants, and `rating_at` is shown in the card. Why: not recorded.
- 2026-10-21: CSAT is removed from the frontend spec, and the ratings report is treated as an existing tab. Why: not recorded.

## Gotchas
- GPDB (Greenplum) is optional via `GPDB_ENABLED`. When it is off, messages come from the local `dialog_messages` table in Postgres.
- Config is in `config/config.dev.yaml`. Secrets and overrides are in `.env`, which is not committed. Override the config path with `CONFIG_PATH`.
- Local run: `go run ./cmd/app`. Docker: `docker compose up --build`.
- The `dialogs/{id}` endpoint is proxied by `forte/cch-backend`, which sends two new fields that the frontend must use.
- SQL scripts to run by hand: `check_schema.sql`, `repeat_contact.sql`, `client_rating.sql`, `check_csi_fcr.sql`, `repeat_contact_test.sql`. Run them outside the 07:30 daily run.

## Links
- Repo: /home/fatikh/forte/chat-analytics
- Frontend guide: docs/csi-fcr-frontend.md
- Plan: FEATURE_IMPLEMENTATION_PLAN.md
- Spec: №2_CSI оценку чат-бота 1.docx / .pdf
- Backend proxy: forte/cch-backend
- Config: config/config.dev.yaml, docker-compose.yaml
- Commit aeae62d: repeat-contact trigger (message-based)

## Notes

_Your own notes. Unison adds to this section but never rewrites it._
