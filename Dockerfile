# Multi-stage build for optimized image size
# Build stage
FROM python:3.9-alpine AS builder

# Install build dependencies
RUN apk add --no-cache \
    gcc \
    musl-dev \
    linux-headers \
    postgresql-dev \
    libffi-dev

# Set work directory
WORKDIR /app

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.9-alpine AS production

# Install runtime dependencies only
RUN apk add --no-cache \
    postgresql-libs \
    libffi

# Create non-root user for security
RUN addgroup -g 1001 -S appgroup && \
    adduser -S appuser -u 1001 -G appgroup

# Copy Python packages from builder stage
COPY --from=builder /root/.local /home/appuser/.local

# Set environment variables
ENV PYTHONUNBUFFERED=True
ENV PATH=/home/appuser/.local/bin:$PATH
ENV APP_HOME=/app

# Set work directory and change ownership
WORKDIR $APP_HOME
RUN chown appuser:appgroup $APP_HOME

# Switch to non-root user
USER appuser

# Copy application code
COPY --chown=appuser:appgroup . ./

# Create uploads directory
RUN mkdir -p uploads/temp

# Expose port
EXPOSE 8080

# Run the web service on container startup
# Cloud Run provides PORT environment variable
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 app:app