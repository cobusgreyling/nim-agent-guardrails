# Showcase Landing Page

This directory contains the official showcase landing page for **nim-agent-guardrails**.

## Files

- `index.html` — fully self-contained, modern single-file HTML + Tailwind (CDN) + vanilla JS
  - Live interactive demo that exactly mirrors the Python guardrail logic
  - All 6 guardrails testable with one-click failing scenarios
  - Code samples, architecture, features

## Viewing

**Live (recommended):**
https://cobusgreyling.github.io/nim-agent-guardrails/

If you see a 404, GitHub Pages needs to be enabled (one-time setup, see below).

**Instant fallback (no setup required):**
https://htmlpreview.github.io/?https://raw.githubusercontent.com/cobusgreyling/nim-agent-guardrails/main/docs/index.html

**Locally:**
```bash
# From repo root
open docs/index.html
# or
python3 -m http.server 8080 --directory .
# then visit http://localhost:8080/docs/index.html
```

The page gracefully falls back to raw GitHub image URLs if local assets are missing.

## One-time GitHub Pages Setup (fixes 404)

1. Go to your repo on GitHub: https://github.com/cobusgreyling/nim-agent-guardrails
2. Click the **Settings** tab (top right).
3. In the left sidebar, click **Pages**.
4. Under "Build and deployment":
   - **Source**: select `Deploy from a branch`
   - **Branch**: select `main`
   - **Folder**: select `/docs`
5. Click **Save**.
6. Wait 1–3 minutes for the site to build (you'll see a green check or "Your site is published at..." message).
7. Visit https://cobusgreyling.github.io/nim-agent-guardrails/

**Why this works**:
- GitHub serves the contents of the `docs/` folder at the root of the Pages site.
- `docs/index.html` becomes the homepage.
- The empty `.nojekyll` file (present in this folder) prevents Jekyll from processing the static HTML.

After the first successful deploy, future commits to `docs/index.html` will automatically update the live site (usually within a minute).

## Notes

- No build step. Pure static asset.
- The JS demo implements the *exact* same rules as `nim_guardrails/guardrails.py` (lengths, regexes, short-circuit, etc).
- Great for sharing with stakeholders who don't want to install anything.

## Updating

Just edit `index.html` and commit. The preview link will update instantly.
