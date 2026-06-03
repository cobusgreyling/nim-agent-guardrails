# Showcase Landing Page

This directory contains the official showcase landing page for **nim-agent-guardrails**.

## Files

- `index.html` — fully self-contained, modern single-file HTML + Tailwind (CDN) + vanilla JS
  - Live interactive demo that exactly mirrors the Python guardrail logic
  - All 6 guardrails testable with one-click failing scenarios
  - Code samples, architecture, features

## Viewing

**Easiest (recommended):**
Open the live version using GitHub's html preview service:

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

## Enabling GitHub Pages (optional)

1. Go to repo → **Settings** → **Pages**
2. Source: **Deploy from a branch**
3. Branch: `main` / `docs` folder
4. Save

Your landing page will then be available at:

`https://cobusgreyling.github.io/nim-agent-guardrails/`

## Notes

- No build step. Pure static asset.
- The JS demo implements the *exact* same rules as `nim_guardrails/guardrails.py` (lengths, regexes, short-circuit, etc).
- Great for sharing with stakeholders who don't want to install anything.

## Updating

Just edit `index.html` and commit. The preview link will update instantly.
