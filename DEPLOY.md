# Deployment Guide

## Local Development

```bash
cd goofish-watcher
pip install -e .
python -m bot.main
```

## Docker (Recommended for Production)

### Quick Start

```bash
# 1. Configure
cp .env.example .env
nano .env  # Add your credentials

# 2. Add cookies.json
# Export from browser (see USAGE.md)

# 3. Build and run
docker-compose up -d

# 4. View logs
docker-compose logs -f
```

### docker-compose.yml

```yaml
services:
  goofish-watcher:
    build: .
    container_name: goofish-watcher
    restart: unless-stopped
    env_file:
      - .env
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
      - ./cookies.json:/app/cookies.json:ro
    environment:
      - DATABASE_PATH=/app/data/goofish.db
      - GOOFISH_COOKIES_JSON_PATH=/app/cookies.json
```

### Commands

```bash
# Start
docker-compose up -d

# Stop
docker-compose down

# Rebuild after code changes
docker-compose up -d --build

# View logs
docker-compose logs -f

# Shell access
docker exec -it goofish-watcher bash
```

### Updating Cookies in Docker

```bash
# 1. Export new cookies from browser to cookies.json
# 2. Restart container
docker-compose restart
```

## Systemd (Linux VPS)

### Setup

```bash
# 1. Create system user
sudo useradd -r -s /bin/false goofish

# 2. Create directory
sudo mkdir -p /opt/goofish-watcher
sudo chown goofish:goofish /opt/goofish-watcher

# 3. Clone/copy project
cd /opt/goofish-watcher
sudo -u goofish git clone https://github.com/youruser/goofish-watcher.git .

# 4. Create virtual environment
sudo -u goofish python3 -m venv .venv
sudo -u goofish .venv/bin/pip install -e .
sudo -u goofish .venv/bin/playwright install chromium

# 5. Configure
sudo -u goofish cp .env.example .env
sudo nano .env  # Add credentials

# 6. Add cookies.json
sudo nano /opt/goofish-watcher/cookies.json

# 7. Install service
sudo cp goofish-watcher.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable goofish-watcher
sudo systemctl start goofish-watcher
```

### goofish-watcher.service

```ini
[Unit]
Description=Goofish Watcher Discord Bot
After=network.target

[Service]
Type=simple
User=goofish
Group=goofish
WorkingDirectory=/opt/goofish-watcher
ExecStart=/opt/goofish-watcher/.venv/bin/python -m bot.main
Restart=always
RestartSec=10

# Environment
Environment=PYTHONUNBUFFERED=1

# Hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/goofish-watcher/data /opt/goofish-watcher/logs /opt/goofish-watcher/chrome_profile

[Install]
WantedBy=multi-user.target
```

### Commands

```bash
# Start
sudo systemctl start goofish-watcher

# Stop
sudo systemctl stop goofish-watcher

# Restart
sudo systemctl restart goofish-watcher

# Status
sudo systemctl status goofish-watcher

# View logs
sudo journalctl -u goofish-watcher -f

# View app logs
tail -f /opt/goofish-watcher/logs/goofish-watcher.log
```

### Updating Cookies

```bash
# 1. Edit cookies
sudo nano /opt/goofish-watcher/cookies.json

# 2. Clear browser profile (optional, if auth issues persist)
sudo rm -rf /opt/goofish-watcher/chrome_profile

# 3. Restart
sudo systemctl restart goofish-watcher
```

## VPS Recommendations

### Minimum Requirements

- 1 CPU core
- 1 GB RAM (2 GB recommended for Playwright)
- 10 GB disk
- Ubuntu 22.04 LTS or Debian 12

### Recommended Providers

| Provider | Plan | Price |
|----------|------|-------|
| Hetzner | CX11 | ~$4/mo |
| DigitalOcean | Basic Droplet | $6/mo |
| Vultr | Cloud Compute | $5/mo |
| Oracle Cloud | Free Tier | Free |

### Initial VPS Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y python3 python3-pip python3-venv git

# Install Chrome dependencies (for Playwright)
sudo apt install -y libnss3 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libxcomposite1 \
    libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2

# Install Google Chrome (optional, Playwright can use bundled Chromium)
wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" | sudo tee /etc/apt/sources.list.d/google-chrome.list
sudo apt update
sudo apt install -y google-chrome-stable
```

## Monitoring

### Health Checks

The bot has built-in health monitoring:

- **Cookie check** (every 6h): Alerts if authentication expires
- **Failure tracking**: Alerts after 3 consecutive scan failures
- **Discord command**: `/stats health` for manual check

### External Monitoring (Optional)

**UptimeRobot / Healthchecks.io**

Add a healthcheck endpoint or use the Discord status as indicator.

**Log Aggregation**

Forward logs to external service:
```bash
# In docker-compose.yml
services:
  goofish-watcher:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

## Backup

### What to Back Up

| File/Folder | Purpose | Frequency |
|-------------|---------|-----------|
| `data/goofish.db` | Database (queries, listings, history) | Daily |
| `cookies.json` | Authentication | After each re-login |
| `.env` | Configuration | After changes |

### Backup Script

```bash
#!/bin/bash
BACKUP_DIR=/backup/goofish-watcher
DATE=$(date +%Y%m%d)

mkdir -p $BACKUP_DIR
cp /opt/goofish-watcher/data/goofish.db $BACKUP_DIR/goofish-$DATE.db
cp /opt/goofish-watcher/.env $BACKUP_DIR/env-$DATE
cp /opt/goofish-watcher/cookies.json $BACKUP_DIR/cookies-$DATE.json

# Keep last 7 days
find $BACKUP_DIR -mtime +7 -delete
```

Add to crontab:
```bash
0 3 * * * /opt/goofish-watcher/backup.sh
```

## Troubleshooting Production Issues

### Bot not starting

```bash
# Check logs
sudo journalctl -u goofish-watcher -n 100

# Common issues:
# - Missing .env variables
# - Invalid cookies.json format
# - Chrome/Chromium not installed
```

### High memory usage

Playwright/Chrome can use significant memory. Solutions:

1. Add swap space:
```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

2. Use bundled Chromium (lighter than Chrome):
```bash
# In .env
USE_BUNDLED_CHROMIUM=1
```

### Cookies expiring frequently

The keep-alive job should maintain cookies. If they still expire:

1. Check bot is actually running: `systemctl status goofish-watcher`
2. Check logs for keep-alive errors
3. Try re-exporting cookies from a fresh browser session
4. Delete `chrome_profile/` and restart

### Scans returning 0 results in production but working locally

1. Check if IP is blocked (try from different IP)
2. Verify cookies were exported from same region
3. Check Goofish isn't blocking headless browsers
4. Try adding delays between requests in scanner.py
