# Local Home Devices MCP
# Model Context Protocol server for IoT device management
# Supports OpenBK (OpenBeken), Tasmota, and Tuya devices

FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    nmap \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -r appuser && useradd -r -g appuser -m -d /app appuser

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[mqtt,tuya]"

COPY server.py .
COPY tools/ ./tools/

RUN mkdir -p /app/data \
    && chown -R appuser:appuser /app

RUN printf '#!/bin/bash\npython server.py\n' > /app/start.sh && chmod +x /app/start.sh

USER appuser

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:9100/health || exit 1

EXPOSE 9100 9101 9102

CMD ["/app/start.sh"]
