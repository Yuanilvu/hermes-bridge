# ─── Hermes Bridge — Multi-stage Dockerfile ───
# Build stage
FROM python:3.11-slim AS builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Runtime stage
FROM python:3.11-slim AS runtime

# Install runtime deps: xdotool (key hold/release), ripgrep (vault search)
RUN apt-get update && apt-get install -y --no-install-recommends \
    xdotool \
    ripgrep \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

WORKDIR /app
COPY . .

# Create data directory
RUN mkdir -p /app/data

EXPOSE 8199

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8199/api/health', timeout=5)" || exit 1

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8199"]
