# Multi-stage Dockerfile for FL-Fog
# Optimized for production deployment with minimal image size

# Build stage
FROM python:3.10-slim as builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create application directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Install the package
RUN pip install --no-cache-dir -e .

# Production stage
FROM python:3.10-slim as production

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    FL_FOG_CONFIG_PATH=/app/config/fog_config.yaml

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r flfog && useradd -r -g flfog flfog

# Create application directory
WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY --chown=flfog:flfog . .

# Create necessary directories
RUN mkdir -p logs data cache config && \
    chown -R flfog:flfog /app

# Create default config if not present
RUN if [ ! -f config/fog_config.yaml ]; then \
        cp config/fog_config.yaml.example config/fog_config.yaml 2>/dev/null || \
        echo "# Default fog config will be generated at runtime" > config/fog_config.yaml; \
    fi

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Switch to non-root user
USER flfog

# Expose ports
EXPOSE 8080 1883 9090

# Default command
CMD ["python", "-m", "fog_node.main", "--config", "/app/config/fog_config.yaml"]

# Development stage
FROM production as development

# Switch back to root for development tools
USER root

# Install development dependencies
RUN pip install --no-cache-dir pytest pytest-asyncio pytest-cov black flake8 mypy isort

# Switch back to flfog user
USER flfog

# Override command for development
CMD ["python", "-m", "fog_node.main", "--config", "/app/config/fog_config.yaml", "--dev"]
