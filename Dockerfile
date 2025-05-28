FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y \
    ffmpeg \
    opus-tools \
    libopus0 \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Set environment for build phase
ENV DOCKER_BUILD=true \
    PYTHONUNBUFFERED=1

# Run health checks in build mode
RUN python healthcheck.py

# Reset environment for runtime
ENV DOCKER_BUILD=false \
    RAILWAY_ENVIRONMENT=production

# Start the bot
CMD ["python", "main.py"] 