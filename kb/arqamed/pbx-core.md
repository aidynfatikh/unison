# pbx-core
<!-- unison bucket=arqamed project=pbx-core updated=1792654747 -->

## Overview
Aikon (repo and systemd units still named `pbx-core`/`pbx-*`) is a self-hosted, multi-tenant Asterisk PBX with a bridge that sends call events to CRMs, running on a VPS at pbx.nabipro.kz. Its first job is replacing Sipuni for the ArqaMed clinic on the Altel SIP trunk; it also connects to the Senimai AI assistant. Stack: Asterisk, Python, shell scripts, PostgreSQL. Users are the developer and ArqaMed staff.

## Current state
- A workspace can now hold a second number without replacing the first; +7 700 062 1130 is registered and listed in the console (2026-10-21). Not yet confirmed with a live call.
- Call transfers, holds and conferences are not built as features (2026-10-22). Phones may do some transfers themselves, untested.
- Tele2 was rejecting all three trunks on the box as of 2026-10-16. No later resolution is recorded.
- The Senimai dev workspace is connected; prod is unchanged. AI calls only reach Senimai once the draft call flow with the AI step is published.

## Open threads
- Publish the draft call flow with the AI step, then place a test call (waiting on your decision).
- Push the Senimai streaming fixes (commit 337cde4 is local only) and check voice logs on real calls.
- Run `ssh -t pbx 'sudo /tmp/trunkdiag2.sh'` to get Tele2's reply code and when the rejections began.
- Fix outbound journal entries showing "s" instead of the dialled number (go-ahead pending).
- Check the missed-call "no-answer" status for a 52-second call (suspected CDR status logic; SQL query not yet run).
- Investigate why inbound calls to the clinic number dropped (no call reached Asterisk for about three days as of 2026-09-28).
- Decide recording retention: at 44 operators, recordings fill the disk in about 3–6 weeks.
- Mint the outbound-calls key on the Senimai integration page and paste it into senimai.kz (status unknown).
- Run `sudo ~/pbx-core/deploy/db/apply.sh` on the box to create the plans role (status unknown).
- Confirm the operator-deletion, schema-sync and integration-scope commits are deployed; the 2026-10-02 push status is unclear.
- Place a test call on the new second number and confirm it appears in the call journal.

## Decisions
- 2026-08-02: product renamed Aikon; repo and infrastructure keep the `pbx-*` names, since renaming the live paths needs a cutover on the VPS.
- 2026-09-29: stereo call recordings (clinic left, caller right); ArqaMed reads `recording_channels`. Chosen as the universal, cleaner option.
- 2026-10-01: the main number follows the provider account instead of copying it, so schemas always match a live number.
- 2026-10-02: integrations can be limited to chosen clinic numbers, and every event names its number; deleting an operator also unticks them in every call flow.
- 2026-10-05: allow unencrypted call audio for the kt-main Gigaset desk phone, because it cannot encrypt and was rejecting every call.
- 2026-10-10: ring-all uses one Local channel per operator, not one Dial string, so every operator is reached.
- 2026-10-12: the AI runtime can ask the box to ring a patient, but the console still cannot dial.
- 2026-10-21: a second number is a separate registration, inbound only; outgoing calls still leave on the main trunk, and the console cannot delete a second number.

## Gotchas
- Config that verifies green can still do nothing. Read `docs/gotchas.md` before touching `asterisk/`, `deploy/`, or any check.
- Device connection problems: check `/var/log/pbx-connections/` first (readable as `pbx`, no sudo). `grep -h <IP or account> /var/log/pbx-connections/*.log`. No line means the packets never reached the box.
- The `pbx-conn-capture.service` filter is a privacy boundary. Do not widen it to SIP, because the capture would be decryptable beside the private key.
- Pushing to main deploys the console via CI.
- Migration 0018 must be applied before the console container. Migration 0025 is `deploy/db/console/0025_extra_trunks.sql`.
- Live code runs from `/home/pbx/pbx-core`.
- Account kt@arqamed.com exists on its own workspace but is not verified. Its password was shared in chat and is not recorded here; rotate it.
- The arqamd console password was reset on 2026-10-13. Its value is not recorded here.
- Senimai dev workspace is `senimai-dev`. Prod is unchanged.

## Links
- Repo: /home/fatikh/projects/pbx-core
- Console: https://pbx.nabipro.kz/ (admin at /admin)
- Senimai: https://senimai.kz, https://dev.senimai.kz
- Senimai repo commit 337cde4 (local, unpushed)
- Repo docs: CLAUDE.md, README.md, HANDOFF.md, docs/state-of-the-box.md, docs/gotchas.md, docs/vps-runbook.md, docs/integration-guide.md, docs/ai-assistant-integration.md
- Senimai repo doc: docs/voice-operator-spec.md
- deploy/db/console/0012_trunk_release.sql, deploy/db/console/0025_extra_trunks.sql, deploy/bin/conn-log.py
- Box: /var/log/pbx-connections/, /tmp/trunkdiag2.sh (temporary)

## Notes

_Your own notes. Unison adds to this section but never rewrites it._
