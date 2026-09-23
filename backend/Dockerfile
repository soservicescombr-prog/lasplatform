# netguard/backend/Dockerfile
FROM python:3.12-slim

LABEL maintainer="NetGuard Team"
LABEL description="NetGuard Backend - Network Security & Monitoring Platform"

# System dependencies (nmap, net-tools for network scanning)
RUN apt-get update && apt-get install -y --no-install-recommends \
    nmap \
    net-tools \
    iputils-ping \
    snmp \
    snmp-mibs-downloader \
    libsnmp-dev \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Download SNMP MIBs
RUN download-mibs || true

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -r netguard && chown -R netguard:netguard /app
USER netguard

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
