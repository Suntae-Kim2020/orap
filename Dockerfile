# Use Python slim image for smaller size
FROM python:3.9-slim

# Set environment variables
ENV PYTHONUNBUFFERED=True
ENV APP_HOME=/app
ENV PORT=8080

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libc6-dev \
    libpq-dev \
    libffi-dev \
    libpq5 \
    libffi8 \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR $APP_HOME

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . ./

# Create uploads directory
RUN mkdir -p uploads/temp

# Expose port
EXPOSE 8080

# Simple startup command
CMD exec gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 8 --timeout 300 app:app