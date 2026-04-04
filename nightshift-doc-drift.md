# Nightshift: Documentation Drift Analysis — Goofish Watcher

**Repo:** Microck/goofish-watcher  
**Date:** 2026-04-04  
**Task:** doc-drift  
**Category:** analysis

---

## Summary

**Overall doc health: 68%** — README and USAGE are reasonably accurate but DEPLOY.md contains significant drift. Several code features are undocumented.

---

## Drift Findings

### P1: `/login export_state_file` command undocumented

- **Severity:** P1 (High)
- **Source:** `bot/commands/login.py:128-155`
- **Docs affected:** README.md, USAGE.md
- **Description:** A fourth command `export_state_file` exists in the codebase that exports the state as a Discord file attachment (not just saves to disk). This is a separate slash command from `export_state`, specifically designed for panel import workflows. Neither README nor USAGE.md document it.
- **Code evidence:**
  ```python
  @app_commands.command(
      name="export_state_file",
      description="Export login state and attach xianyu_state.json (for panel import)",
  )
  ```

### P1: `superbuy_link_template` config undocumented

- **Severity:** P1 (High)
- **Source:** `config.py:39`
- **Docs affected:** README.md, USAGE.md, DEPLOY.md
- **Description:** The `superbuy_link_template` setting is defined in `config.py` and used extensively in `webhook_receiver.py` (`_build_superbuy_url()`), but no documentation mentions it. Users cannot configure custom Superbuy link templates.

### P2: CNY-to-EUR conversion and price display undocumented

- **Severity:** P2 (Medium)
- **Source:** `core/webhook_receiver.py:370-419`, `config.py:36`
- **Docs affected:** All docs
- **Description:** The webhook receiver fetches live CNY/EUR rates from ECB, parses listing prices from webhook payloads, and displays converted prices in Discord embeds. The `cny_to_eur_rate` config provides a fallback. None of this is documented — users won't know the bot does price conversion or that it needs internet access to the ECB feed.

### P2: Auto-translation of Chinese text undocumented

- **Severity:** P2 (Medium)
- **Source:** `core/webhook_receiver.py:257-321`
- **Docs affected:** All docs
- **Description:** The bot auto-translates Chinese listing text to English via Google Translate API (`translate.googleapis.com`). The feature is cached (200 entries max, `_TRANSLATION_CACHE_MAX`). Undocumented dependency and behavior — users may not expect external Google API calls.

### P2: Listing image carousel undocumented

- **Severity:** P2 (Medium)
- **Source:** `core/webhook_receiver.py:101-175`
- **Docs affected:** README.md
- **Description:** Discord notifications include a multi-image carousel with Prev/Next buttons (1-hour timeout). This is a significant UX feature that's not mentioned in any doc. The carousel deduplicates image URLs and falls back to the dialog screenshot if no images are found.

### P2: Notification filtering (auth expiry messages) undocumented

- **Severity:** P2 (Medium)
- **Source:** `core/webhook_receiver.py:22-25, 203-207`
- **Docs affected:** All docs
- **Description:** The bot silently drops notifications containing auth-expired patterns (`_AUTH_EXPIRED_MESSAGE_PATTERNS`). Users won't understand why some webhooks don't produce DMs.

### P3: `GOOFISH_COOKIES_JSON_PATH` supports Cookie-Editor format

- **Severity:** P3 (Low)
- **Source:** `core/scanner.py:142-144`
- **Docs affected:** USAGE.md
- **Description:** The cookie loader supports both a flat list and the Cookie-Editor browser extension format (`{"url": "...", "cookies": [...]}`). This is useful for users importing cookies manually but isn't documented.

### P3: Chrome channel detection undocumented

- **Severity:** P3 (Low)
- **Source:** `core/scanner.py:44-60`
- **Docs affected:** DEPLOY.md
- **Description:** The scanner auto-detects system Chrome installations (Chrome, Chromium, etc.) and prefers them over bundled Chromium unless `USE_BUNDLED_CHROMIUM` is set. DEPLOY.md mentions `USE_BUNDLED_CHROMIUM` but doesn't explain the auto-detection behavior.

### P3: `USE_BUNDLED_CHROMIUM` env var only in DEPLOY.md

- **Severity:** P3 (Low)
- **Source:** `config.py` (not in config), `core/scanner.py:45`
- **Docs affected:** USAGE.md, README.md
- **Description:** `USE_BUNDLED_CHROMIUM` is checked via `os.environ.get()` in scanner.py but not defined as a pydantic field in `config.py`. Only DEPLOY.md mentions it. Should be added to config.py for consistency.

---

## Missing Documentation

| Feature | Source | Priority |
|---------|--------|----------|
| `export_state_file` slash command | `bot/commands/login.py:128` | P1 |
| Superbuy link generation | `webhook_receiver.py:438-461` | P1 |
| CNY/EUR price conversion | `webhook_receiver.py:370-419` | P2 |
| Chinese-to-English auto-translation | `webhook_receiver.py:257-321` | P2 |
| Image carousel in Discord embeds | `webhook_receiver.py:101-175` | P2 |
| Auth expiry notification suppression | `webhook_receiver.py:203-207` | P2 |
| Cookie-Editor format support | `scanner.py:142-144` | P3 |
| Chrome auto-detection logic | `scanner.py:44-60` | P3 |

---

## Stale References

### DEPLOY.md: References `data/goofish.db` database

- **File:** DEPLOY.md:251  
- **Severity:** P2  
- **Description:** Backup section mentions `data/goofish.db` and a "Database (queries, listings, history)". No such database file or directory exists in the codebase. The project uses JSON files for cookies and Playwright storage state, not SQLite. This section appears to be aspirational or copied from another project.

### DEPLOY.md: References `/stats health` Discord command

- **File:** DEPLOY.md:223  
- **Severity:** P1  
- **Description:** Monitoring section mentions `/stats health` command. No such command exists — the only registered commands are in the `/login` group (`qr`, `status`, `export_state`, `export_state_file`). There is no `stats` group or `health` command anywhere in the codebase.

### DEPLOY.md: Health check description is fabricated

- **File:** DEPLOY.md:219-223  
- **Severity:** P1  
- **Description:** Claims "built-in health monitoring" with "Cookie check (every 6h)" and "Failure tracking: Alerts after 3 consecutive scan failures". No such health monitoring system exists in the code. There's no background task, no periodic check, and no failure counter.

### README.md: Project description is incomplete

- **File:** README.md:7  
- **Severity:** P3  
- **Description:** Says "Small add-on: Goofish QR login + export Playwright state + Discord DM webhook forwarding". The webhook receiver actually does significant processing: price extraction, currency conversion, translation, image carousel, listing preview fetching, Superbuy link generation. The description undersells the bot's capabilities.

---

## Recommendations

| Priority | Action | Effort |
|----------|--------|--------|
| P1 | Remove fabricated `/stats health` and health monitoring from DEPLOY.md | Low |
| P1 | Remove `data/goofish.db` references from DEPLOY.md | Low |
| P1 | Document `export_state_file` command in README and USAGE | Low |
| P2 | Add webhook processing features to README description | Medium |
| P2 | Document `superbuy_link_template` and `cny_to_eur_rate` in USAGE.md | Low |
| P2 | Document auto-translation and price conversion behavior | Medium |
| P3 | Add `USE_BUNDLED_CHROMIUM` to `config.py` as a proper field | Low |
| P3 | Document Cookie-Editor format support in USAGE.md | Low |
