# Use the official lightweight Python image
FROM python:3.9-slim

# Allow statements and log messages to immediately appear in the logs
ENV PYTHONUNBUFFERED=True

# Copy local code to the container image
ENV APP_HOME=/app
WORKDIR $APP_HOME
COPY . ./

# Install production dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create uploads directory with proper permissions
RUN mkdir -p uploads/temp && chmod 755 uploads && chmod 755 uploads/temp

# Create directory for SQLite database with write permissions
RUN mkdir -p /app/data && chmod 755 /app/data

# Run the web service on container startup
# Render provides PORT environment variable
CMD exec gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 8 --timeout 120 app:app