# saq
<!-- unison bucket=arqamed project=saq updated=1792654901 -->

## Overview
SAQ is a DNS-based network activity monitor for a clinic (ArqaMed work area). It runs as Docker services (Unbound recursive resolver, SAQ DNS server, dashboard on :8080) on a machine the router points clinic devices to, logs lookups for registered clinic devices, translates them into readable activity, and blocks malware/phishing domains. Stack and project path: /home/fatikh/projects/saq.

## Current state
- Stage 1 (DNS) is implemented: resolver, activity reports, and dashboard are committed.
- Latest commit (2026-10-10): only clinic devices are logged, raw retention is 30 days, local recursive DNS via Unbound.
- Session of 2026-10-06 produced DNS-only SAQ code committed on top of the team's research (not pushed); the research has three conflicts with the design.
- Retention defaults follow `research/03-compliance.md` (§8.2, §8.3).

## Open threads
- Fix the three conflicts between the team's research and the committed code. Pending decision: whether the fix should start with logging only clinic-owned devices instead of every phone (the 2026-10-10 commit appears to already do this, so verify whether it resolves the conflict).
- Push the DNS-only SAQ commits (currently local only).
- Confirm the upstream resolver check on the clinic host: `docker compose logs dns | grep upstream` should show `upstream 127.0.0.1:5335 OK`.
- Router setup at the clinic is not confirmed: fixed IP for SAQ host, DNS server set to SAQ, outbound port 53 blocked except to SAQ, DHCP reservations for clinic PCs.

## Decisions
- 2026-10-10: Log only clinic devices (registered in dashboard or inside `SAQ_MONITORED_NETWORKS`), because non-clinic devices (staff phones, guests) are protected but not recorded beyond "threat blocked" without IP, for consent and privacy reasons.
- 2026-10-10: Keep raw lookups for 30 days, then roll up finished days into per-device, per-site daily totals kept 365 days, because it limits detail while still allowing pattern review.
- 2026-10-10: Use local recursive DNS (Unbound on 127.0.0.1:5335) as primary upstream, with optional ISP resolver fallback, because ISPs may block direct DNS and one broken resolver should not take the clinic offline.

## Gotchas
- Ubuntu's `systemd-resolved` occupies port 53; disable its stub listener before starting (`DNSStubListener=no` in `/etc/systemd/resolved.conf`, then restart `systemd-resolved`).
- The container runs as uid 1000: `mkdir -p data && sudo chown 1000 data` before first start.
- Admin password is set in `.env` as `SAQ_ADMIN_PASSWORD` (copy from `.env.example`); do not commit `.env`.
- Keep only one DNS server in the router's DHCP settings; a second entry lets devices bypass SAQ.
- Upstream fallback is configured via `SAQ_UPSTREAMS=127.0.0.1:5335,<isp-dns-ip>`; SAQ falls through on SERVFAIL.
- "Stop monitoring" on a device deletes its stored data and excludes it even inside monitored ranges; lookups queued in the last ~10 seconds may still be written once.
- Time per site is an estimate (DNS caching, background tabs); do not treat it as proof.
- Apps with hard-coded DNS, VPNs, and mobile data are not visible to SAQ.
- Start: `docker compose up -d --build`. Dashboard: `http://<saq-ip>:8080`.

## Links
- Repo: /home/fatikh/projects/saq
- Compliance research: research/03-compliance.md (§8.2, §8.3)
- Config template: .env.example
- Commits: "feat: add stage-1 DNS resolver, activity reports and dashboard" (2026-10-10); "feat: log only clinic devices, 30-day raw retention, local recursive DNS" (2026-10-10)

## Notes

_Your own notes. Unison adds to this section but never rewrites it._
