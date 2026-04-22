<p align="center">
  <a href="https://github.com/Microck/goofish-watcher">
    <img src="logo.png" alt="Goofish Watcher" width="100">
  </a>
</p>

<p align="center">Small add-on: Goofish QR login + export Playwright state + Discord DM webhook forwarding</p>

<p align="center">
  <a href="LICENSE"><img alt="license" src="https://img.shields.io/badge/license-MIT-green.svg" /></a>
  <img alt="python" src="https://img.shields.io/badge/python-3.11+-blue.svg" />
  <img alt="discord.py" src="https://img.shields.io/badge/discord.py-2.0+-7289da.svg" />
  <img alt="playwright" src="https://img.shields.io/badge/playwright-1.40+-orange.svg" />
</p>

---

### tl;dr

```bash
# Quick start (local)
pip install -e .
cp .env.example .env  # edit with credentials

# Playwright browser
python -m playwright install chromium

python -m bot.main
```

For production, see [DEPLOY.md](DEPLOY.md) for Docker and systemd instructions.

### what this repo does

- **QR login** on a headless server via Discord `/login qr` (screenshots the real QR modal)
- **Exports Playwright `storage_state`** via `/login export_state` (default: `./xianyu_state.json`) for [`Usagi-org/ai-goofish-monitor`](https://github.com/Usagi-org/ai-goofish-monitor)
- **Receives `ai-goofish-monitor` webhook notifications** and forwards them as Discord DMs with:
  - Title translation (Chinese → English via Google Translate)
  - CNY → EUR price conversion (live ECB rate with configurable fallback)
  - Multi-image carousel with Prev/Next buttons
  - Direct Goofish and Superbuy links

### architecture

```
┌─────────────────┐    QR scan     ┌──────────────────┐
│  Goofish/Xianyu  │◄──────────────│  Playwright       │
│  (闲鱼)          │               │  (headless)       │
└─────────────────┘               └────────┬─────────┘
                                           │ storage_state
                                           ▼
                                  ┌──────────────────┐
                                  │  ai-goofish-monitor│
                                  │  (listings bot)    │
                                  └────────┬─────────┘
                                           │ webhook POST
                                           ▼
┌──────────┐   DM    ┌──────────────────────────────┐
│  Discord  │◄───────│  goofish-watcher              │
│  User     │        │  (webhook receiver + bot)      │
└──────────┘        └──────────────────────────────┘
```

### configuration

All settings are configured via environment variables or a `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `DISCORD_BOT_TOKEN` | *(required)* | Discord bot token from the Developer Portal |
| `DISCORD_USER_ID` | *(required)* | Your Discord user ID (for DM forwarding) |
| `GOOFISH_COOKIES_JSON_PATH` | `./cookies.json` | Path to cookie JSON file (Cookie-Editor export supported) |
| `WEBHOOK_HOST` | `0.0.0.0` | Webhook listener bind address |
| `WEBHOOK_PORT` | `8123` | Webhook listener port |
| `WEBHOOK_PATH` | `/webhook/ai-goofish-monitor` | Webhook endpoint path |
| `WEBHOOK_SECRET` | *(empty)* | Optional shared secret (`X-Webhook-Secret` header or `?secret=` query) |
| `CNY_TO_EUR_RATE` | `0.13` | Fallback CNY→EUR rate (live ECB rate used when available) |
| `SUPERBUY_LINK_TEMPLATE` | `https://www.superbuy.com/en/page/buy/?url={url}` | Superbuy link template (`{url}` is replaced with URL-encoded Goofish link) |
| `LOG_LEVEL` | `INFO` | Python logging level |

### requirements

| Requirement | Description |
|-------------|-------------|
| Python 3.11+ | Runtime |
| Discord bot token | Bot authentication |
| Goofish/Xianyu account | Scan QR from the 闲鱼 app |
| Chromium | Playwright browser (or system Chrome/Chromium) |

### commands

| Command | Description |
|---------|-------------|
| `/login qr` | Start QR login and receive QR image in DM |
| `/login status` | Check whether the cookies/session are logged in |
| `/login export_state [path]` | Export `storage_state` JSON for `ai-goofish-monitor` |

### ai-goofish-monitor webhook config

In `ai-goofish-monitor`, configure the webhook to POST to this bot:

```env
WEBHOOK_URL=http://<this-server>:8123/webhook/ai-goofish-monitor
WEBHOOK_METHOD=POST
WEBHOOK_HEADERS={"X-Webhook-Secret":"<optional secret>"}
WEBHOOK_BODY={"title":"{{title}}","content":"{{content}}"}
WEBHOOK_CONTENT_TYPE=JSON
```

The webhook payload is flexible — it accepts:
- **JSON**: `{"title": "...", "content": "...", "meta": {...}}`
- **Form-encoded**: `title=...&content=...&meta_price=...`
- **Plain text**: body is used as-is

The `meta` field supports: `title`, `price`, `url`, `image_url`, `images` (JSON array of URLs).

### project structure

```
goofish-watcher/
├── bot/
│   ├── main.py              # discord client entry point
│   └── commands/
│       └── login.py         # /login slash commands
├── core/
│   ├── scanner.py           # QR login + Playwright browser management
│   └── webhook_receiver.py  # webhook receiver → Discord DM forwarder
├── config.py                # pydantic-settings configuration
├── tests/
│   └── test_webhook_receiver.py
├── Dockerfile
├── docker-compose.yml
└── goofish-watcher.service  # systemd unit file
```

### troubleshooting

| Issue | Solution |
|-------|----------|
| QR login says `非法访问` | Goofish blocked the IP/session; try another IP or wait |
| Bot can't DM you | Enable DMs, verify `DISCORD_USER_ID`, and ensure you share a mutual server with the bot |
| ai-goofish-monitor webhook not received | Check `WEBHOOK_HOST/PORT/PATH`, firewall rules, and optional secret |
| `playwright install` fails in Docker | Ensure the Docker image includes Chromium deps (see Dockerfile) |
| Cookie file not loading | Verify JSON format; Cookie-Editor export format is supported (`{"cookies": [...]}`) |

### documentation

- [USAGE.md](USAGE.md) — setup guide, configuration, commands
- [DEPLOY.md](DEPLOY.md) — production deployment (Docker, systemd, VPS)

### license

MIT
