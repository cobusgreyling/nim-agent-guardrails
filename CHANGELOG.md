# Changelog

All notable changes to nim-agent-guardrails.

## [0.2.0] - 2026-02-xx

### Added
- Interactive showcase landing page at `docs/index.html` (self-contained, Tailwind + full JS port of guardrails)
- GitHub Actions CI workflow testing on Python 3.10–3.12
- Prominent "View interactive showcase" link in README
- Support for installing via `pip install git+https...[nim,demo]`
- New project URLs in pyproject.toml

### Changed
- Core guardrails are now zero-dependency (`openai` moved to optional `[nim]` extra)
- Fixed pyproject build backend for proper pip/git installs
- Improved README: better install instructions, badges, clearer requirements
- Bumped version to 0.2.0
- Minor: updated examples install commands

### Fixed
- Packaging now works cleanly for `pip install -e .[nim,dev]`

## [0.1.0] - Initial release
- 6 composable guardrails
- GuardedAgent with full audit trail
- NimClient (OpenAI SDK + urllib fallback)
- Travel agent + guardrails-only demos
- 37 passing tests
