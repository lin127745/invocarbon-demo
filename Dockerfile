FROM node:20-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN NEXT_TELEMETRY_DISABLED=1 npx next build

FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends postgresql && rm -rf /var/lib/apt/lists/*
# Hugging Face Spaces run the container as uid 1000
RUN useradd -m -u 1000 user
WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/*.py ./
COPY backend/demo ./demo
COPY --from=web /web/out ./static
COPY start.sh ./
RUN chmod +x start.sh && chown -R user /app
USER user
ENV STATIC_DIR=/app/static PGDATA=/tmp/pgdata
EXPOSE 7860
CMD ["./start.sh"]
