# sekspaton
<!-- unison bucket=other project=sekspaton updated=1792654928 -->

## Overview
Oohla is a women's fitness and intimacy training platform, built with MediaPipe pose detection, Google Gemini chat scenarios, and JWT auth. The repo at `/home/fatikh/projects/sekspaton` holds the app and its landing page, which deploys to Vercel from `main`.

## Current state
- Landing page uses the non-18+ copy from `Oohla_non_18plus_copy_v1.pdf`, committed and pushed to `main` on 2026-09-28.
- Meta and OG descriptions and meta keywords were aligned with the non-18+ positioning in follow-up commits.
- The push triggered a Vercel deployment.

## Open threads
- Confirm the sample testimonials on the landing page are real, or remove them.
- Check that the non-18+ landing copy still matches the product, since the README describes intimacy coaching and Gemini chat scenarios.
- README lists cleanup of 21 redundant files (see CLEANUP_INSTRUCTIONS); status unknown.

## Decisions
- 2026-09-28: Repositioned the landing page to non-18+ body-skills copy, because the requirements doc in `Oohla_non_18plus_copy_v1.pdf` specifies it.
- 2026-09-28: Aligned meta and OG descriptions with the same non-18+ positioning, so search and link previews match the landing page.

## Gotchas
- Pushing to `main` triggers the Vercel deployment for the landing page.
- README also documents Azure VM and DigitalOcean deployment paths; the landing page deploys through Vercel.

## Links
- docs/INDEX.md
- docs/PROJECT_REVIEW.md
- docs/SUMMARY.md
- docs/QUICK_REFERENCE.md
- docs/CLEANUP_INSTRUCTIONS.md
- docs/AZURE_DEPLOYMENT.md
- docs/DIGITAL_OCEAN_DEPLOYMENT.md
- Oohla_non_18plus_copy_v1.pdf (requirements doc, location not recorded)
- GitHub `main` branch (repo for sekspaton)

## Notes

_Your own notes. Unison adds to this section but never rewrites it._
