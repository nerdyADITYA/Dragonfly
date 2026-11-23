FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
WORKDIR /app
COPY requirements.txt .
# Playwright's bundled node needs libatomic before `--with-deps` can install the rest.
RUN apt-get update && apt-get install -y --no-install-recommends libatomic1 && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.txt \
 && playwright install --with-deps chromium \
 && useradd -m dragonfly && mkdir -p /data/artifacts && chown dragonfly /data/artifacts
COPY . .
USER dragonfly
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
