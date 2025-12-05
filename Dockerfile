# Multi-stage build for production-ready Django app

# Stage 1: Build stage
FROM python:3.11-slim as builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create and set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt

# Stage 2: Runtime stage
FROM python:3.11-slim

# Create app user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/home/appuser \
    APP_HOME=/home/appuser/web

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libpq-dev \
    netcat-traditional \
    && rm -rf /var/lib/apt/lists/*

# Create directories
RUN mkdir -p $APP_HOME/staticfiles $APP_HOME/media $APP_HOME/logs
WORKDIR $APP_HOME

# Install Python dependencies from build stage
COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements.txt .
RUN pip install --no-cache /wheels/*

# Copy project files
COPY ./ecommerceBook $APP_HOME/
COPY ./.env $APP_HOME/
COPY ./entrypoint.sh $APP_HOME/

# Change ownership to app user
RUN chown -R appuser:appuser $APP_HOME

# Switch to app user
USER appuser

# Make entrypoint executable
RUN chmod +x $APP_HOME/entrypoint.sh

# Run entrypoint
ENTRYPOINT ["/home/appuser/web/entrypoint.sh"]
