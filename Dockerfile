# Tasmota-OpenBK-MCP
# Model Context Protocol server for IoT device management
# Supports OpenBK (OpenBeken) and Tasmota devices

FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    nmap \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .
COPY tools/ ./tools/

RUN mkdir -p /app/data

RUN printf '#!/bin/bash\npython server.py\n' > /app/start.sh && chmod +x /app/start.sh

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:9100/health || exit 1

EXPOSE 9100 9101 9102

CMD ["/app/start.sh"]
