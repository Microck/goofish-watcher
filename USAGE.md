# Usage

## Prerequisites

### Discord bot

1. Create an app + bot in the Discord Developer Portal
2. Copy the bot token
3. Invite the bot to a server you share (Discord generally blocks DMs without a mutual server)

### Playwright browser

```bash
python -m playwright install chromium
```

## Setup

```bash
pip install -e .
cp .env.example .env
```

Edit `.env`:

```env
DISCORD_BOT_TOKEN=...
DISCORD_USER_ID=...
GOOFISH_COOKIES_JSON_PATH=./cookies.json

WEBHOOK_HOST=127.0.0.1
WEBHOOK_PORT=8123
WEBHOOK_PATH=/webhook/ai-goofish-monitor
WEBHOOK_SECRET=
```

## QR login

In Discord, run:

- `/login qr` (scan with the 闲鱼 app)
- `/login status`
- `/login export_state` (writes `./xianyu_state.json` by default)

## ai-goofish-monitor webhook -> Discord DM

Point `ai-goofish-monitor` to this bot's webhook receiver:

```env
WEBHOOK_URL=http://<this-server>:8123/webhook/ai-goofish-monitor
WEBHOOK_METHOD=POST
WEBHOOK_HEADERS={"X-Webhook-Secret":"<optional secret>"}
WEBHOOK_BODY={"title":"{{title}}","content":"{{content}}"}
WEBHOOK_CONTENT_TYPE=JSON
```

If `WEBHOOK_SECRET` is set in this repo, the receiver accepts it either as:

- HTTP header `X-Webhook-Secret: ...`
- query string `?secret=...`
