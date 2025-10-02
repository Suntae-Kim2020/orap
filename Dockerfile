# Multi-stage build for optimized image size
# Build stage
FROM python:3.9-slim AS builder

# Set environment variable to prevent interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libc6-dev \
    libpq-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.9-slim AS production

# Set environment variable to prevent interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libffi8 \
    curl \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd -g 1001 appgroup && \
    useradd -r -u 1001 -g appgroup appuser

# Copy Python packages from builder stage
COPY --from=builder /root/.local /home/appuser/.local

# Set environment variables
ENV PYTHONUNBUFFERED=True
ENV PATH=/home/appuser/.local/bin:$PATH
ENV APP_HOME=/app
ENV PORT=8080

# Set work directory and change ownership
WORKDIR $APP_HOME
RUN chown appuser:appgroup $APP_HOME

# Switch to non-root user
USER appuser

# Copy application code
COPY --chown=appuser:appgroup . ./

# Create uploads directory and set permissions
RUN mkdir -p uploads/temp && \
    mkdir -p /tmp && \
    chmod 755 uploads/temp

# Ensure jbnu.db exists and has proper permissions
RUN if [ ! -f jbnu.db ]; then \
        sqlite3 jbnu.db "CREATE TABLE IF NOT EXISTS test (id INTEGER);" && \
        rm -f jbnu.db; \
        sqlite3 jbnu.db ".schema"; \
    fi && \
    chmod 644 jbnu.db

# Expose port
EXPOSE 8080

# Run the web service on container startup with proper error handling
CMD ["sh", "-c", "\
    echo 'Starting JBNU ORAP application...' && \
    echo 'Environment:' && \
    echo \"PORT=$PORT\" && \
    echo 'Database check:' && \
    ls -la jbnu.db || echo 'No jbnu.db found' && \
    echo 'Starting gunicorn...' && \
    exec gunicorn \
        --bind 0.0.0.0:$PORT \
        --workers 1 \
        --threads 8 \
        --timeout 120 \
        --access-logfile - \
        --error-logfile - \
        --log-level info \
        --preload \
        app:app \
    "]