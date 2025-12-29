FROM python:3.11-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

ENV PLAYWRIGHT_BROWSERS_PATH=/usr/lib/chromium
ENV USE_BUNDLED_CHROMIUM=1

COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

RUN playwright install chromium --with-deps || true

COPY . .

RUN mkdir -p /app/data /app/logs /app/chrome_profile

CMD ["python", "-m", "bot.main"]
