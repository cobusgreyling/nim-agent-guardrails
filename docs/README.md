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

**Locally:**
```bash
# From repo root
open docs/index.html
# or
python3 -m http.server 8080 --directory .
# then visit http://localhost:8080/docs/index.html
```

The page gracefully falls back to raw GitHub image URLs if local assets are missing.

GitHub Pages is configured to serve from the `docs/` folder on `main`.

## Notes

- No build step. Pure static asset.
- The JS demo implements the *exact* same rules as `nim_guardrails/guardrails.py` (lengths, regexes, short-circuit, etc).
- Great for sharing with stakeholders who don't want to install anything.

## Updating

Just edit `index.html` and commit. The preview link will update instantly.
