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
</p>

---

### tl;dr

```bash
pip install -e .
cp .env.example .env  # edit with credentials

# Playwright browser
python -m playwright install chromium

python -m bot.main
```

### what this repo does

- QR login on a headless server via Discord `/login qr` (screenshots the real QR modal)
- Exports a Playwright `storage_state` JSON via `/login export_state` (default: `./xianyu_state.json`) for `Usagi-org/ai-goofish-monitor`
- Receives `ai-goofish-monitor` webhook notifications and forwards them as Discord DMs

### requirements

| Requirement | Description |
|-------------|-------------|
| Python 3.11+ | Runtime |
| Discord bot token | Bot authentication |
| Goofish/Xianyu account | Scan QR from the 闲鱼 app |
| Chromium | Playwright browser |

### commands

| Command | Description |
|---------|-------------|
| `/login qr` | Start QR login and receive QR image |
| `/login status` | Check whether the cookies/session are logged in |
| `/login export_state [path]` | Export `storage_state` JSON for `ai-goofish-monitor` |

### ai-goofish-monitor webhook config

In `ai-goofish-monitor`, set something like:

```env
WEBHOOK_URL=http://<this-server>:8123/webhook/ai-goofish-monitor
WEBHOOK_METHOD=POST
WEBHOOK_HEADERS={"X-Webhook-Secret":"<optional secret>"}
WEBHOOK_BODY={"title":"{{title}}","content":"{{content}}"}
WEBHOOK_CONTENT_TYPE=JSON
```

### project structure

```
goofish-watcher/
├── bot/
│   ├── main.py              # discord client entry
│   └── commands/            # slash commands (login)
├── core/
│   ├── scanner.py           # QR login + storage_state export
│   └── webhook_receiver.py  # webhook -> DM forwarder
├── config.py                # pydantic-settings config
├── Dockerfile
├── docker-compose.yml
└── goofish-watcher.service  # systemd unit file
```

### troubleshooting

| Issue | Solution |
|-------|----------|
| QR login says `非法访问` | Goofish blocked the IP/session; try another IP or wait |
| Bot can't DM you | Enable DMs, verify `DISCORD_USER_ID`, and allow the bot to message |
| ai-goofish-monitor webhook not received | Check `WEBHOOK_HOST/PORT/PATH`, firewall, and optional secret |

### documentation

- [USAGE.md](USAGE.md) - setup guide, configuration, commands
- [DEPLOY.md](DEPLOY.md) - production deployment (docker, systemd, vps)

### license

MIT
