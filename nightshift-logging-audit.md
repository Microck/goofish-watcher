# Nightshift: Logging Quality Audit

**Repo:** Microck/goofish-watcher
**Date:** 2026-04-05
**Task:** logging-audit
**Lines of code:** 1,727 (10 Python files)

## Summary

The codebase has reasonable logging coverage for its size (18 log calls across 5 source files), but several patterns reduce observability. No `log.debug` calls exist, structured context is missing, and some error paths lack stack traces. The logging setup in `bot/main.py` is functional but lacks request correlation IDs.

---

## Findings

### P2 — No debug-level logging anywhere

**Files:** `core/scanner.py`, `core/webhook_receiver.py`, `bot/main.py`

Zero `log.debug()` calls in the entire codebase. Important diagnostic information like browser launch args, cookie details, and webhook request payloads is unavailable when debugging issues in production.

**Recommendation:** Add `log.debug()` for:
- Browser launch configuration (channel, args, profile dir) in `scanner.py:85-121`
- Cookie loading details (domain, count per domain) in `scanner.py:134-184`
- Incoming webhook request headers/content type in `webhook_receiver.py:768-788`
- FX rate cache hits/misses in `webhook_receiver.py:370-395`

---

### P2 — Inconsistent f-string vs % formatting in log calls

**Files:** `core/scanner.py`, `core/webhook_receiver.py`

Most log calls use f-strings (`log.info(f"Loaded {len(cookies)} auth cookies")`), but `webhook_receiver.py` uses `%s` formatting in two places:
- Line 391: `log.warning("Failed to fetch live FX rate, using fallback: %s", e)`
- Line 793: `log.info("Dropped auth-expired webhook notification: %s", _truncate(content, 200))`

While both work, mixing styles is inconsistent. The `%s` style is technically preferred for logging (lazy evaluation avoids string formatting when the log level is disabled), but f-strings are acceptable for INFO+ levels that are rarely disabled.

**Recommendation:** Pick one style project-wide. If performance matters, use `%s` everywhere. If readability matters, use f-strings everywhere. Current mix is fine for this codebase size but would be confusing in a larger project.

---

### P2 — Missing exc_info on most exception log calls

**Files:** `core/scanner.py`, `core/webhook_receiver.py`

Only 2 of 7 `log.error()` calls include `exc_info=True`:
- `scanner.py:448` — `log.error(f"QR login start failed: {e}", exc_info=True)` ✅
- `scanner.py:528` — `log.error(f"QR login wait failed: {e}", exc_info=True)` ✅

Missing stack traces:
- `scanner.py:183` — `log.error(f"Failed to load cookies: {e}")` — file I/O failure, no traceback
- `scanner.py:278` — `log.error(f"Auth check failed: {e}")` — browser failure, no traceback
- `scanner.py:514` — `log.warning(f"Failed to save cookies after QR login: {e}")` — file write failure
- `webhook_receiver.py:713` — `log.error(f"Failed to fetch Discord user {user_id}: {e}")` — API failure
- `webhook_receiver.py:728` — `log.error(f"Failed to send DM: {e}")` — Discord API failure

**Recommendation:** Add `exc_info=True` to all `log.error()` calls. For `log.warning`, add it when the exception is unexpected (not just a timeout).

---

### P2 — Module-level singleton makes testing/logging hard to isolate

**File:** `core/scanner.py:552`

```python
goofish_client = GoofishClient()
```

This module-level instantiation means the object is created at import time. Any logging during `__init__` fires during import, before the logging system may be fully configured. Currently `__init__` doesn't log, but future changes could introduce subtle ordering bugs.

**Recommendation:** Use a factory function or lazy initialization pattern instead of module-level singleton.

---

### P3 — No request correlation in webhook handling

**File:** `core/webhook_receiver.py:768-797`

The webhook handler processes requests asynchronously via `asyncio.create_task()` (line 796). There is no request ID or correlation token, making it impossible to trace a webhook from receipt to DM delivery in logs.

**Recommendation:** Generate a short request ID (e.g. `uuid4().hex[:8]`) at the start of `_handle()`, pass it through to `_send_discord_dm()`, and include it in all log messages for that request.

---

### P3 — Auth expiry detection relies on string matching without logging the raw payload

**File:** `core/webhook_receiver.py:792-794`

```python
if _should_drop_notification(title, content):
    log.info("Dropped auth-expired webhook notification: %s", _truncate(content, 200))
```

The truncated content is logged, but the original `raw` payload is discarded. If the auth expiry patterns change or new patterns emerge, debugging requires the full payload.

**Recommendation:** Log the full payload at DEBUG level before dropping.

---

### P3 — Logging setup uses basicConfig plus manual handler

**File:** `bot/main.py:17-30`

The logging configuration calls `basicConfig()` (which configures the root logger with a StreamHandler) then adds a `RotatingFileHandler` to the root logger. This works but:
- The root logger has two handlers (stream + file) with the same formatter configured differently
- `basicConfig` sets the root logger level, but the file handler also has its own level set to `log_level` — this is redundant
- No named logger hierarchy (all loggers use `__name__` which creates flat `core.scanner`, `core.webhook_receiver`, etc.)

**Recommendation:** Not urgent for this codebase size. If it grows, consider using `dictConfig` or `fileConfig` for cleaner setup.

---

### P3 — Translation cache eviction uses FIFO, not LRU

**File:** `core/webhook_receiver.py:318-320`

```python
if len(_TRANSLATION_CACHE) >= _TRANSLATION_CACHE_MAX:
    _TRANSLATION_CACHE.pop(next(iter(_TRANSLATION_CACHE)))
```

The cache evicts the first-inserted entry (FIFO). For a translation cache where the same listing titles may repeat, LRU eviction would be more efficient. There's no logging of cache hit/miss rates.

**Recommendation:** Either use `functools.lru_cache` or `collections.OrderedDict.move_to_end()` for LRU. Add debug logging for cache hit rate.

---

### P3 — No structured logging or JSON format option

**Files:** `bot/main.py`, `config.py`

Logs are plain text with a simple format (`%(asctime)s [%(levelname)s] %(name)s: %(message)s`). For production monitoring (e.g. sending to Datadog, Loki, or CloudWatch), structured JSON logging would be more useful.

**Recommendation:** Add a `LOG_FORMAT=json|text` config option. When `json`, use `python-json-logger`.

---

## Metrics

| Metric | Value |
|--------|-------|
| Total log calls | 18 |
| `log.debug` | 0 |
| `log.info` | 6 |
| `log.warning` | 4 |
| `log.error` | 5 |
| `log.critical` | 0 |
| `exc_info=True` | 2/7 (29%) |
| f-string formatting | 14/18 (78%) |
| `%s` formatting | 4/18 (22%) |
| Files with logging | 5/10 (50%) |
| Module-level loggers | 5 |

## Priority Summary

| Severity | Count | Category |
|----------|-------|----------|
| P0 Critical | 0 | — |
| P1 High | 0 | — |
| P2 Medium | 4 | Missing debug logs, inconsistent formatting, missing stack traces, singleton init |
| P3 Low | 4 | No request correlation, dropped payload, basicConfig quirks, FIFO cache |

Overall the logging is functional for a small bot project. The main improvements would be adding debug-level logging for development and ensuring all error paths include stack traces.
