---
active: true
iteration: 6
max_iterations: 50
completion_promise: "INTEGRATION COMPLETE"
started_at: "2025-02-12T00:10:00Z"
---

# Integration Task: Merge ai-goofish-monitor into goofish-watcher

## Objective

Integrate the superior features from [Usagi-org/ai-goofish-monitor](https://github.com/Usagi-org/ai-goofish-monitor) into this project (goofish-watcher), while preserving the existing Discord bot interface and SQLite storage layer.

## Source Repository

Clone or fetch from: `https://github.com/Usagi-org/ai-goofish-monitor` (branch: `master`)

If not already cloned, clone it to `/tmp/ai-goofish-monitor` as a reference. Do NOT copy files wholesale — read, understand, and adapt code to fit goofish-watcher's architecture.

## What to Integrate (Priority Order)

### P0 — Critical (must complete)

1. **API-interception scraping** — Replace the current DOM-based Playwright scraping in `core/scanner.py` with ai-goofish-monitor's approach: intercept `h5api.m.goofish.com/h5/mtop.taobao.idlemtopsearch.pc.search` API responses via Playwright's `page.on("response")`. This is far more reliable than DOM extraction. Port the JSON parsing logic from `src/parsers.py:_parse_search_results_json()`. Keep the existing `GoofishClient` class interface but rewrite the internals.

2. **OpenAI-compatible AI client** — Replace the NVIDIA NIM-specific AI verification in `core/verifier.py` with an OpenAI-compatible client (using the `openai` Python package's `AsyncOpenAI`). This allows any OpenAI-compatible endpoint (OpenAI, local Ollama, ModelScope, etc.). Add config vars: `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL_NAME`. Keep the existing `AIVerifier` interface but swap httpx calls for openai client. Keep vision support for image analysis.

3. **Seller reputation analysis** — Port the seller/user detail scraping from ai-goofish-monitor (`DETAIL_API_URL_PATTERN`, `parse_ratings_data`, `parse_user_head_data`, `calculate_reputation_from_ratings`). Add seller reputation data (registration age, positive rating %, transaction count) to the AI verification context and to the Discord notification embeds.

4. **Enhanced filtering** — Add these filters to the `Query` model and `filter.py`:
   - Free shipping filter (`free_shipping: bool`)
   - Publish time range filter (`new_publish_hours: Optional[int]` — only items published within N hours)
   - Region filter (`region: Optional[str]` — province/city format)
   - These should be configurable per-query via Discord slash commands

### P1 — Important

5. **Multi-channel notifications** — Add notification channels alongside Discord DMs. Port the notification client architecture from `src/infrastructure/external/notification_clients/`. Support:
   - ntfy.sh (`NTFY_TOPIC_URL`)
   - Bark (`BARK_URL`)
   - Telegram (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`)
   - Generic Webhook (`WEBHOOK_URL`, `WEBHOOK_METHOD`, `WEBHOOK_HEADERS`, `WEBHOOK_BODY`)
   - WeChat Work bot (`WX_BOT_URL`)
   
   Make each channel optional (enabled only if its env var is set). Discord DM remains the default and always-on channel.

6. **Account & proxy rotation** — Port the rotation system from `src/rotation.py`. Support:
   - Multiple Goofish account state files in a `state/` directory
   - Per-task or on-failure account switching
   - Proxy pool with rotation and blacklisting
   - Config via env vars: `PROXY_ROTATION_ENABLED`, `PROXY_POOL`, etc.
   - Integrate with `GoofishClient` so it can switch browser contexts on failure

7. **Product detail fetching** — Intercept `h5api.m.goofish.com/h5/mtop.taobao.idle.pc.detail` to get full product details (all images, full description) before AI analysis. Download product images for vision AI. Clean up images after processing (per-task image directories like ai-goofish-monitor does).

### P2 — Nice to have

8. **Web UI** — Add an optional FastAPI web interface (on a configurable port, default 8000) for task management, result browsing and log viewing. Port the FastAPI app structure from `src/app.py` and API routes from `src/api/routes/`. The Vue 3 frontend from `web-ui/` can be built and served as static files. This should be an opt-in feature (`ENABLE_WEB_UI=true`), not breaking the Discord-only workflow.

9. **Cron scheduling** — Add cron expression support for scan scheduling alongside the current interval-based scheduling. Allow queries to use either `interval_minutes` (existing) or `cron_expression` (new).

## What to Preserve (Do NOT Break)

- Discord bot startup and slash command interface (`bot/main.py`, `bot/commands/*`)
- SQLite database schema and migrations (`db/models.py`, `db/store.py`) — extend, don't replace
- Existing `/query`, `/alert`, `/stats`, `/logs` command groups
- Docker and systemd deployment (`Dockerfile`, `docker-compose.yml`, `goofish-watcher.service`)
- Cookie management and keep-alive system in `WatcherCog`
- pydantic-settings based configuration (`config.py`)
- All existing env vars must keep working with their current semantics

## Architecture Rules

- Keep the existing package structure: `bot/`, `core/`, `db/`, `config.py`
- New notification clients go in `core/notifications/` (new subpackage)
- New rotation logic goes in `core/rotation.py`
- Web UI goes in `web/` (new package, only imported if `ENABLE_WEB_UI=true`)
- All new features must have sane defaults and work without configuration (graceful degradation)
- All new config vars go in `config.py` via pydantic-settings with proper defaults
- Update `pyproject.toml` with any new dependencies
- Update `.env.example` with all new env vars (with comments)
- Update `README.md` to document new features

## Database Schema Changes

- Add columns to `queries` table: `free_shipping`, `new_publish_hours`, `region`, `cron_expression`, `account_state_file`
- Add columns to `listings_seen` table: `seller_rating`, `seller_registration_days`, `wants_count`, `original_price`, `tags` (JSON)
- Add columns to `notifications` table: `channels_sent` (JSON — which channels received this notification)
- Handle migrations in `Store._migrate()` using the existing pattern (check if column exists, ALTER TABLE ADD COLUMN)

## Slash Command Updates

Update `/query add` to accept new optional parameters:
- `free_shipping: bool` (default False)
- `new_publish_hours: Optional[int]`
- `region: Optional[str]`

Update `/query list` to display new filter info.

Update `/stats health` to include proxy/account rotation status.

## Testing Requirements

- All existing functionality must continue to work
- Write tests in `tests/` for:
  - API response JSON parsing (use sample fixtures)
  - Filter logic (free shipping, region, publish time)
  - Seller reputation calculation
  - Notification channel dispatch (mock external APIs)
  - Account/proxy rotation logic
- Run `python -m pytest tests/ -v` and ensure all tests pass
- Run `python -m py_compile bot/main.py` and all source files to verify no syntax errors
- Run `python -c "from bot.main import GoofishBot; print('import OK')"` to verify imports work

## Completion Criteria

ALL of the following must be true before outputting the completion promise:

1. `python -m pytest tests/ -v` passes with 0 failures
2. `python -m py_compile bot/main.py` succeeds
3. All P0 items are fully implemented and tested
4. All P1 items are fully implemented and tested  
5. Database migrations work (new columns added gracefully)
6. `.env.example` updated with all new vars
7. `pyproject.toml` updated with new dependencies
8. No import errors across the entire codebase
9. Existing Discord bot functionality is preserved (commands, scheduling, notifications)
10. `README.md` updated with new features documentation

When ALL criteria are met, output exactly:

<promise>INTEGRATION COMPLETE</promise>

Do NOT output the promise tag until every criterion is verified. If something is broken, fix it and re-verify.

## Iteration Strategy

Each iteration:
1. Check what's already been done (read files, check git log)
2. Pick the next unfinished item by priority
3. Implement it
4. Write/run tests for it
5. Fix any breakage
6. If all criteria are met, output promise. Otherwise, continue.
