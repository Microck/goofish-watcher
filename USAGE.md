# Usage Guide

## Prerequisites

### 1. Discord Bot Setup

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application", name it (e.g., "Goofish Watcher")
3. Go to "Bot" tab, click "Add Bot"
4. Copy the **Bot Token** (keep it secret)
5. Enable "Message Content Intent" under Privileged Gateway Intents
6. Go to "OAuth2" > "URL Generator":
   - Select `bot` scope
   - Select permissions: `Send Messages`, `Embed Links`
   - Copy generated URL
7. Open URL in browser, invite bot to your server

**CRITICAL**: The bot must share a server with you to send DMs. Discord blocks DMs between users/bots without mutual servers.

### 2. Get Your Discord User ID

1. Enable Developer Mode: User Settings > Advanced > Developer Mode
2. Right-click your username anywhere in Discord
3. Click "Copy User ID"

### 3. NVIDIA NIM API Key

1. Go to [NVIDIA NGC](https://catalog.ngc.nvidia.com/)
2. Create account / Sign in
3. Go to your profile > Setup > Generate API Key
4. Copy the API key

### 4. Goofish Cookies

The bot needs authentication cookies from Goofish/Xianyu to search listings.

**Method 1: Browser Extension (Recommended)**

1. Install [Cookie-Editor](https://cookie-editor.cgagnier.ca/) browser extension
2. Log in to [goofish.com](https://www.goofish.com) or [xianyu.com](https://www.xianyu.com)
3. Click Cookie-Editor icon
4. Click "Export" > "Export as JSON"
5. Save as `cookies.json` in project root

**Method 2: DevTools**

1. Log in to Goofish
2. Open DevTools (F12) > Application > Cookies
3. Copy all cookies manually to JSON format:
```json
[
  {"name": "cookie_name", "value": "cookie_value", "domain": ".goofish.com"},
  ...
]
```

**Important cookies**: `_m_h5_tk`, `_m_h5_tk_enc`, `cookie2`, `sgcookie`, `unb`

## Installation

```bash
# Clone repository
git clone https://github.com/youruser/goofish-watcher.git
cd goofish-watcher

# Install dependencies
pip install -e .

# Install Playwright browsers
playwright install chromium

# Copy environment template
cp .env.example .env
```

## Configuration

Edit `.env` file:

```bash
# Required
DISCORD_BOT_TOKEN=your_bot_token_here
DISCORD_USER_ID=your_user_id_here
NVIDIA_API_KEY=your_nvidia_api_key_here

# Goofish Auth - choose one:
GOOFISH_COOKIES_JSON_PATH=./cookies.json
# OR
GOOFISH_COOKIE=your_cookie_string_here

# Optional
DATABASE_PATH=./data/goofish.db
LOG_LEVEL=INFO
MAX_LISTINGS_PER_SCAN=100
JITTER_MINUTES=5
SEEN_STREAK_STOP=10
```

### Configuration Options

| Variable | Description | Default |
|----------|-------------|---------|
| `DISCORD_BOT_TOKEN` | Discord bot token | Required |
| `DISCORD_USER_ID` | Your Discord user ID for DMs | Required |
| `NVIDIA_API_KEY` | NVIDIA NIM API key | Required |
| `GOOFISH_COOKIES_JSON_PATH` | Path to cookies.json | `./cookies.json` |
| `DATABASE_PATH` | SQLite database path | `./data/goofish.db` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `MAX_LISTINGS_PER_SCAN` | Max listings per scan | `100` |
| `JITTER_MINUTES` | Random interval variance | `5` |
| `SEEN_STREAK_STOP` | Stop after N consecutive seen | `10` |

## Running the Bot

```bash
python -m bot.main
```

Expected output:
```
INFO discord.client: logging in using static token
INFO __main__: Database connected
INFO bot.cogs.watcher: Scheduled query #1 every 60m
INFO __main__: Watcher started
INFO __main__: Commands synced
INFO __main__: Logged in as GoofishWatcher#1234
```

## Discord Commands

### Query Management

**Add a new query:**
```
/query add keyword:Raf Simons
/query add keyword:Nike Dunk include:Low,Retro exclude:fake,rep min_price:100 max_price:500
```

Options:
- `keyword` (required) - Search term
- `include` - Comma-separated terms that MUST appear in title
- `exclude` - Comma-separated terms to filter OUT
- `min_price` - Minimum price in CNY
- `max_price` - Maximum price in CNY
- `interval` - Scan frequency: 60, 180, or 360 minutes (default: 60)
- `ai_threshold` - AI relevance threshold 0.0-1.0 (default: 0.7)

**List queries:**
```
/query list
```
Output: `#1 [✓] Nike Dunk (60m)`

**Enable/Disable:**
```
/query enable 1
/query disable 1
```

**Test immediately:**
```
/query test 1
```
Runs scan right now, bypassing interval schedule.

**Remove:**
```
/query remove 1
```

### Alert Labels

Mark notifications with custom labels:
```
/alert mark 123 interested
/alert mark 123 bought
/alert labels 123
```

### Statistics

**Query stats:**
```
/stats query 1
```
Shows: total scans, listings found, notifications sent

**Overview:**
```
/stats overview
```
Shows: all queries, recent scans, total notifications

**Health check:**
```
/stats health
```
Shows: cookie status, recent failures, scheduler status

## How It Works

1. **Scheduler** triggers scan every N minutes (with jitter)
2. **Scanner** uses Playwright to search Goofish with your cookies
3. **Parser** normalizes raw listing data
4. **Filter** applies price/include/exclude rules
5. **Dedup** checks if listing was seen before
6. **AI Verifier** (optional) confirms relevance via NVIDIA NIM
7. **Notifier** sends Discord DM with listing embed

### Notification Format

```
[Query: Raf Simons]
------------------
Title: Raf Simons Redux 2005 Archive Jacket
Price: ¥2,500
Location: Shanghai
AI Confidence: 0.92
[View Listing]
```

## Troubleshooting

### Bot not responding to commands

1. Wait 1-2 minutes after startup for commands to sync
2. Check bot has proper permissions in server
3. Try `/stats health` to verify bot is working

### Not receiving DMs

1. **Must have mutual server** - Bot and you must share a server
2. Check privacy settings: User Settings > Privacy & Safety > Allow DMs from server members
3. Verify `DISCORD_USER_ID` is correct in `.env`

### Cookies expired

Symptoms: Scans return 0 listings, health check shows auth failed

Fix:
1. Re-login to Goofish in browser
2. Export new cookies to `cookies.json`
3. Delete `chrome_profile/` folder
4. Restart bot

The bot auto-refreshes cookies every 2 hours while running. Cookies only expire when bot is stopped for extended periods.

### Scans finding 0 listings

1. Check cookies are valid: `/stats health`
2. Test manually: `/query test <id>`
3. Check logs in `logs/goofish-watcher.log`
4. Verify keyword actually has results on Goofish website

### AI verification failing

1. Check NVIDIA API key is valid
2. Check API endpoint is reachable
3. Disable AI for query: set `ai_threshold:0` when adding query

### Windows console showing garbled text

Chinese characters don't display correctly on Windows (cp1252 encoding). This is display-only - data is correct internally. Use Docker or Linux for proper display.

## Cookie Maintenance

Goofish cookies expire after 6-12 hours of inactivity. The bot handles this automatically:

1. **Keep-alive job** (every 2h): Visits homepage to refresh session
2. **Cookie refresh** (every 2h): Exports current browser cookies back to `cookies.json`
3. **Auth check** (every 6h): Verifies cookies still work, alerts if expired

If you stop the bot for more than ~12 hours, you'll need to re-export cookies.
