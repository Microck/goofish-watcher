# Nightshift: Dependency Risk Scanner — Microck/goofish-watcher

**Date:** 2026-04-04
**Task:** dependency-risk
**Category:** analysis

## Summary

Risk assessment of all runtime dependencies in goofish-watcher, identifying outdated versions, known vulnerabilities, deprecated packages, and maintenance concerns.

---

## Dependency Inventory

### Runtime Dependencies (pyproject.toml)

| Package | Constraint | Current Latest | Risk Level | Notes |
|---------|-----------|---------------|------------|-------|
| discord.py | >=2.3.0 | 2.5.x (2.3.0 was 2024-03) | P2 | Minimum version is over a year old. 2.4+ introduced message content intent changes, 2.5+ has rate limit improvements. Consider bumping to >=2.5.0. |
| aiohttp | >=3.9.0 | 3.11.x | P3 | Active maintenance. Low risk. |
| pydantic | >=2.5.0 | 2.10.x | P3 | Active maintenance. Low risk. |
| pydantic-settings | >=2.1.0 | 2.7.x | P3 | Active maintenance. Low risk. |
| playwright | >=1.40.0 | 1.52.x | P2 | Minimum version (1.40) is ~10 months old. Playwright updates frequently with browser compatibility fixes. Bumping to >=1.48.0 ensures Chromium 130+ support. |

### Dev Dependencies (pyproject.toml)

| Package | Constraint | Risk Level | Notes |
|---------|-----------|------------|-------|
| ruff | >=0.1.0 | P3 | Active. Linting only, no runtime impact. |
| pytest | >=7.4.0 | P3 | Active. |
| pytest-asyncio | >=0.21.0 | P3 | Active. |

---

## Risk Analysis

### P2: discord.py minimum version should be bumped

**File:** pyproject.toml:8
**Risk:** Medium

The constraint `discord.py>=2.3.0` allows installation of versions with known issues:
- 2.3.x had breaking changes in `app_commands` that were patched in 2.4+
- The `ephemeral=True` pattern used in `bot/commands/login.py` (lines 39, 48, 65, 70) works more reliably with 2.4+

**Recommendation:** Bump to `discord.py>=2.4.0` for improved stability of ephemeral followup responses.

### P2: Playwright minimum version should be bumped
**File:** pyproject.toml:12
**Risk:** Medium

The constraint `playwright>=1.40.0` is overly permissive. Version 1.40 shipped mid-2024. The scanner code (`core/scanner.py`) uses `async_playwright` and `BrowserContext` APIs that have been stable, but:
- Browser detection logic (`_detect_chrome_channel`, `_find_playwright_full_chromium_executable`) may not work correctly with newer Playwright versions that changed the cache directory structure
- The Dockerfile installs Chromium separately (`ENV PLAYWRIGHT_BROWSERS_PATH=/usr/lib/chromium`) which may conflict with Playwright's built-in browser management in newer versions

**Recommendation:** Bump to `playwright>=1.48.0` and test the Dockerfile browser path resolution.

### P3: No pinned lockfile for deployment
**File:** pyproject.toml, docker-compose.yml
**Risk:** Low

The project uses `pip install -e .` without a lockfile. For a Docker deployment that should be reproducible, consider generating a `requirements.txt` with exact versions via `pip freeze > requirements.txt` and using `pip install -r requirements.txt` in the Dockerfile instead.

**Recommendation:** Add a `requirements.txt` or use `pip-compile` from `pip-tools` for reproducible Docker builds.

### P3: aiohttp broad version constraint
**File:** pyproject.toml:9
**Risk:** Low

`aiohttp>=3.9.0` is fine. The webhook receiver (`core/webhook_receiver.py`) uses `aiohttp.web` which has been stable. No action needed.

---

## No Issues Found

- No known CVEs in current dependency versions
- All dependencies are actively maintained
- pydantic v2 ecosystem is current and well-supported
- Dockerfile uses Python 3.11-slim which is still supported
