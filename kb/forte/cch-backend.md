# cch-backend
<!-- unison bucket=forte project=cch-backend updated=1792654821 -->

## Overview
- cch-backend is the BFF (backend-for-frontend) for the Contact Center Hub platform, built on Python 3.12, Django 5, django-ninja, PostgreSQL and Redis, on port 8000. It handles JWT/LDAP auth, role-based access, and proxies to Speech Analytics, ForteGuide, ForteKnowledge and Announcements.
- Serves the Vue 3 SPA only; the frontend never calls downstream services directly. Work area: Forte.

## Current state
- Speech analytics auto evaluation permissions were restored on 2026-10-20 (`fix(core)` commit).
- Knowledge base per-category access for groups is built and pushed on `feat/AI-3807-knowledge-permissions` (branch `feature/knowledge-category-access` also has the frontend guide).
- Knowledge proxy forwards BSC/segment and Premier params, pushed on `forte-knowledge-proxy`.
- Chat analytics CSI ratings report proxy (`GET /analytics/csi`) was committed on 2026-10-16.
- Auto evaluation proxy endpoints for Forte Rangers are on `feature/AI-3619-rangers-analysis`; the Docker image still needs rebuilding from that branch.

## Open threads
- Deploy cch-backend, then the frontend, for the Premier channel changes.
- Open the PR for `forte-knowledge-proxy` and test the endpoints against the knowledge service.
- Decide whether to add tests for the remaining knowledge endpoints or verify end-to-end against the dev ForteKnowledge.
- Rebuild the Docker image from `feature/AI-3619-rangers-analysis`.
- Investigate why regular users get "NLP server error 404" on speech analytics audio while admins don't. No branch has an audio permission yet. Next step: request the failing `audio_id` as admin to check whether the recording exists.

## Decisions
- 2026-09-18: Topic access grants restricted to superadmins and business owners, because only they should manage access grants.
- 2026-09-21: Topic access management moved under the speech analytics service, and scopes were simplified, to keep topic permissions in one place.
- 2026-09-21: Frontend topic access guide removed from the repo, so it no longer lives alongside the code.
- 2026-10-08: Knowledge base category access follows the same design and endpoints as topic permissions, so the frontend can reuse one pattern.
- 2026-10-14: `view_auto_evaluation` (id 77) is granted explicitly to the `Portal_Users` group, because it is not granted by default to groups with full speech analytics permission.

## Gotchas
- Refresh token is an HttpOnly cookie (1 day); access token lasts 5 hours. Both are JWT HS256.
- Rate limits are per user in Redis: 300 req/min for analytics, 100 req/min for chatbot/knowledge.
- Request bodies are forwarded whole by the knowledge proxy (`apps/services/knowledge_router.py`), so new body fields usually need no code change.
- Project lookups in speech analytics must run off the event loop (`fix(speech-analytics)` commit), otherwise they block requests.
- Permission grant via Swagger: `PATCH /api/admin/groups/10` with `{"permission_ids": [22, 77]}` keeps the other fields unchanged. Confirm the current `permission_ids` before sending, since the body replaces the list.
- Auth and audit: every login and CRUD action is logged with IP and user agent. The `X-Correlation-ID` header is forwarded to all downstream services.

## Links
- Repo: /home/fatikh/forte/cch-backend
- Branches: `feat/AI-3807-knowledge-permissions`, `feature/knowledge-category-access`, `forte-knowledge-proxy`, `feature/AI-3619-rangers-analysis`
- Code: `apps/services/knowledge_router.py`, `apps/core/models.py`, `config/settings.py`, `config/urls.py`
- Docs: `@cch-rangers.md` (Forte Rangers endpoints spec)
- Endpoints: `/api/admin/groups/{id}`, `/api/speech_analytics/v1/*`, `/api/knowledge/v1/*`, `/api/forteguide/v1/*`, `/api/announcements/v1/*`

## Notes

_Your own notes. Unison adds to this section but never rewrites it._
