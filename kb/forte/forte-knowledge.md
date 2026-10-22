# forte-knowledge
<!-- unison bucket=forte project=forte-knowledge updated=1792654855 -->

## Overview
- forte-knowledge: the knowledge base service for Forte, covering categories, topics and segments that feed the vector store read by the bots (Ai-nur, Guide, BSC). Backend and frontend run on the DEV server; owner is a developer (fatikh).

## Current state
- BSC is a channel alongside Guide and Ai-nur, and segments propagate to vectors (2026-10-02 feature, 2026-10-05 collection migration fixes).
- Premier was moved from being a segment to its own channel; pushed as backend 1.5.0 (2026-10-09 commit), with images still being transferred to DEV.
- Last session (2026-10-16) reviewed recent commits; the next check is per-channel vector counts for BSC and Premier to confirm they have data.
- Known open bug: enabling Ai-nur or Guide for a category creates no vectors.
- `/knowledge/categories` endpoint got noticeably slower after the BSC change; not yet confirmed.

## Open threads
- Finish loading the 1.5.0 images on DEV and run the Premier channel migration.
- Run per-channel count queries in the knowledge schema to check BSC and Premier vectors exist.
- Decide whether to fix the category-enable bug that creates no vectors.
- Confirm the `/knowledge/categories` slowdown by timing the endpoint while the server is quiet (suspected Weaviate contention or long BSC cascades).
- Frontend: a separate frontend (not in this repo) needs the BSC segment filter and edits per `docs/bsc-segments-requirements.md`; confirm it is updated.

## Decisions
- 2026-10-02: Add BSC as a new channel and propagate segments to vectors, so segments reach bot retrieval.
- 2026-10-05: Keep integration requirements and deployment order in separate docs to keep each concern clear.
- 2026-10-06: Retrieval for bots needs only a segment filter; no bot endpoint changes, only the vector data they read.
- 2026-10-06: Make the localization release gate cheap and cached to avoid slow app load.
- 2026-10-09: Premier becomes a separate channel instead of a segment, because segmenting should work the same for mass and solo; Premier is removed from the segment set.

## Gotchas
- Migrations and backfill for BSC/segments were already applied on DEV; Premier migration is still pending on DEV.
- BSC collection migration needed a unique revision id (fixed 2026-10-05); reuse of a revision id breaks it.
- Hierarchy list order must stay stable after updates (fixed 2026-10-06); check ordering when changing hierarchy code.
- Backend image deploys go through copying an archive to the DEV server and recreating backend containers.
- Frontend specs were split into two docs (cch-backend and frontend); check the right one before editing.

## Links
- Repo: /home/fatikh/forte/forte-knowledge
- docs/bsc-segments-requirements.md (BSC and segments integration requirements)
- BSC and segments deployment order doc (added 2026-10-05; path not recorded)
- Frontend guide for BSC segments endpoints (written 2026-10-06; path not recorded)
- Endpoint: /knowledge/categories

## Notes

_Your own notes. Unison adds to this section but never rewrites it._
