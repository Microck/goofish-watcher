# Goofish Watcher

Discord bot that monitors Xianyu/Goofish (Chinese secondhand marketplace) for configurable search queries, filters listings using AI verification, and sends notifications via Discord DM.

## Features

- **Configurable Queries**: Keyword search with include/exclude term filters
- **Price Filtering**: Min/max price range support
- **AI Verification**: NVIDIA NIM API filters irrelevant listings
- **Discord Notifications**: Real-time DM alerts with listing details
- **Deduplication**: Won't notify same listing twice
- **Flexible Intervals**: 60/180/360 minute scan cycles
- **Health Monitoring**: Auto-alerts for auth failures, scan errors
- **SQLite Persistence**: Queries, listings, scan history stored locally

## Quick Start

```bash
git clone https://github.com/youruser/goofish-watcher.git
cd goofish-watcher
pip install -e .
cp .env.example .env
# Edit .env with credentials
python -m bot.main
```

See [USAGE.md](USAGE.md) for detailed setup and [DEPLOY.md](DEPLOY.md) for production deployment.

## Requirements

- Python 3.11+
- Discord bot token
- NVIDIA NIM API key (for AI verification)
- Goofish/Xianyu cookies
- Google Chrome (Playwright uses it for browser automation)

## Discord Commands

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

## Project Structure

```
goofish-watcher/
├── bot/
│   ├── main.py              # Discord client entry
│   ├── commands/            # Slash commands (query, alert, stats)
│   └── cogs/watcher.py      # Scheduler + scan logic
├── core/
│   ├── scanner.py           # Playwright-based Goofish scraper
│   ├── parser.py            # Listing normalization
│   ├── filter.py            # Price/term filters
│   ├── verifier.py          # NVIDIA NIM AI verification
│   └── notifier.py          # Discord DM sender
├── db/
│   ├── models.py            # Data models
│   └── store.py             # SQLite CRUD operations
├── config.py                # pydantic-settings config
├── cookies.json             # Goofish auth cookies
├── Dockerfile
├── docker-compose.yml
└── goofish-watcher.service  # Systemd unit file
```

## Documentation

- [USAGE.md](USAGE.md) - Setup guide, configuration, commands
- [DEPLOY.md](DEPLOY.md) - Production deployment (Docker, systemd, VPS)

## License

MIT
