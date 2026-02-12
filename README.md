<p align="center">
  <a href="https://github.com/Microck/goofish-watcher">
    <img src="logo.png" alt="Goofish Watcher" width="100">
  </a>
</p>

<p align="center">discord bot that monitors Xianyu/Goofish for listings and sends DM alerts</p>

<p align="center">
  <a href="LICENSE"><img alt="license" src="https://img.shields.io/badge/license-MIT-green.svg" /></a>
  <img alt="python" src="https://img.shields.io/badge/python-3.11+-blue.svg" />
  <img alt="discord.py" src="https://img.shields.io/badge/discord.py-2.0+-7289da.svg" />
</p>

---

### tl;dr

```bash
# docker (recommended)
docker compose up -d

# manual
pip install -e .
cp .env.example .env  # edit with credentials
python -m bot.main
```

### features

- **configurable queries** - keyword search with include/exclude term filters
- **price filtering** - min/max price range support
- **enhanced filtering** - free shipping, region, publish time filters
- **ai verification** - openai-compatible api (or nvidia nim fallback) filters irrelevant listings
- **seller reputation** - registration age, rating, transaction count analysis
- **discord notifications** - real-time dm alerts with listing details
- **multi-channel notifications** - ntfy, telegram, bark, webhook support
- **deduplication** - won't notify same listing twice
- **flexible intervals** - 60/180/360 minute scan cycles or cron expressions
- **health monitoring** - auto-alerts for auth failures, scan errors
- **sqlite persistence** - queries, listings, scan history stored locally
- **api-interception scraping** - reliable api-based data extraction

### requirements

| Requirement | Description |
|-------------|-------------|
| Python 3.11+ | Runtime |
| Discord bot token | Bot authentication |
| OpenAI API key (or NVIDIA NIM) | AI verification |
| Goofish cookies | Marketplace authentication |
| Chromium | Browser automation (bundled in Docker) |

### commands

| Command | Description |
|---------|-------------|
| `/query add <keyword>` | Add watch query |
| `/query list` | List all queries |
| `/query enable <id>` | Enable query |
| `/query disable <id>` | Disable query |
| `/query remove <id>` | Delete query |
| `/query test <id>` | Run query immediately |
| `/alert mark <id> <label>` | Label a notification |
| `/stats query <id>` | Query statistics |
| `/stats overview` | Global statistics |
| `/stats health` | System health check |

### new features (v0.2.0)

#### openai-compatible ai
Supports any OpenAI-compatible API endpoint:
- OpenAI (GPT-4o, GPT-4)
- Local Ollama instances
- ModelScope, Together AI, etc.

Configure in `.env`:
```
OPENAI_API_KEY=your_key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL_NAME=gpt-4o
```

#### multi-channel notifications
Configure multiple notification channels in `.env`:
```
# ntfy.sh
NTFY_TOPIC_URL=https://ntfy.sh/your-topic

# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Bark (iOS)
BARK_URL=https://api.day.app/your_key

# Generic Webhook
WEBHOOK_URL=https://your-webhook.com/notify
```

#### enhanced filtering
New per-query filters:
- `free_shipping` - Only items with free shipping (包邮)
- `new_publish_hours` - Only items published within N hours
- `region` - Filter by province/city (e.g., "上海", "北京")
- `cron_expression` - Schedule with cron syntax

#### seller reputation analysis
Discord notifications now include:
- Seller registration age (e.g., "2年")
- Positive rating percentage
- Transaction count
- Overall reputation score

### project structure

```
goofish-watcher/
├── bot/
│   ├── main.py              # discord client entry
│   ├── commands/            # slash commands (query, alert, stats)
│   └── cogs/watcher.py      # scheduler + scan logic
├── core/
│   ├── scanner.py           # api-interception scraper (replaces dom-based)
│   ├── parsers.py           # json parsers for api responses
│   ├── parser.py            # listing normalization
│   ├── filter.py            # price/term/region/shipping filters
│   ├── verifier.py          # openai-compatible ai verification
│   ├── notifier.py          # discord dm + multi-channel sender
│   ├── rotation.py          # account/proxy rotation
│   └── notifications/       # notification clients
│       ├── base.py
│       ├── ntfy.py
│       ├── telegram.py
│       ├── bark.py
│       └── webhook.py
├── db/
│   ├── models.py            # data models with new fields
│   └── store.py             # sqlite crud operations
├── config.py                # pydantic-settings config
├── Dockerfile
├── docker-compose.yml
└── goofish-watcher.service  # systemd unit file
```

### troubleshooting

| Issue | Solution |
|-------|----------|
| Cookie expired | Re-export cookies from browser, update `cookies.json` |
| No listings found | Check debug screenshots in `debug/`, verify cookies |
| AI verification fails | Check OpenAI/NVIDIA API key and quota |
| Bot not responding | Verify `DISCORD_TOKEN` and bot permissions |
| Docker ARM64 issues | Use provided Dockerfile with Chromium (not Chrome) |

### documentation

- [USAGE.md](USAGE.md) - setup guide, configuration, commands
- [DEPLOY.md](DEPLOY.md) - production deployment (docker, systemd, vps)

### license

MIT
