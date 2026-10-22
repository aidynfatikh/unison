# bt-assistant
<!-- unison bucket=forte project=bt-assistant updated=1792654936 -->

## Overview
- bt-assistant (Forte work area): FastAPI service that generates business requirements (BRD) from Jira issues via an LLM, renders BPMN diagrams to PNG, and publishes the result to Confluence with a link back to Jira.
- Stack: Python 3.11 + FastAPI/Uvicorn, Node.js + bpmn-js + Playwright/Chromium for rendering, SpaCy anonymization, n8n workflows, Docker/docker-compose. Runs on the bank's server; LLM via LiteLLM gateway (locally, direct OpenAI).
- Audience: ForteBank developers and the Jira ScriptRunner integration.

## Current state
- Latest activity 2026-09-24: working on moving the BPMN n8n workflow into a UI-only n8n editor (no server access); not yet resolved.
- Recent commits (2026-09-17): n8n workflows added, BPMN pipeline added, BPMN rendering improved.
- Core endpoints: `POST /jira/process-issue` (main), `/jira/process-issue/sync`, `/jira/download-brd`, `/health`.

## Open threads
- Import the BPMN n8n workflow into the UI-only n8n editor (via JSON import or canvas paste).
- Make the Python service publicly reachable so a ready-to-import n8n file can point at its URL.

## Decisions
- 2026-09-17: Use BPMN XML rendered to PNG via bpmn-js + Playwright, as the diagram pipeline (keeps diagrams as standard BPMN and produces images for Confluence).
- 2026-09-17: Route LLM calls through the bank's LiteLLM gateway on deploy, with direct OpenAI locally (keeps deployment inside bank infrastructure).
- 2026-09-17: Anonymize names and account numbers with SpaCy before sending to the LLM (protects personal data).

## Gotchas
- Two LLM calls per issue: BRD JSON (~30-40s), then BPMN XML (~25s); rendering adds ~10-15s.
- Confluence publish flow: create page, upload PNG as attachment, then update page with the image.
- Swagger UI at `http://SERVER_IP:8070/docs`.
- Files are stored under `/app/documents` and served via StaticFiles.
- Deploy: `scp` the image tar, `.env`, `docker-compose.yml`, and `deploy.sh` to the server, then run deploy.sh (README "first deploy" section; exact steps truncated in the source).
- Credentials live in `.env` on the server; never commit or share its values.

## Links
- Repo folder: /home/fatikh/forte/bt-assistant
- Service docs: http://SERVER_IP:8070/docs (replace SERVER_IP)
- Deploy target: dladmin@SERVER_IP:/home/dladmin/bt-as

## Notes

_Your own notes. Unison adds to this section but never rewrites it._
