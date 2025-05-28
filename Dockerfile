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
    && rm -rf /var/lib/apt/lists/* \
    && ffmpeg -version

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Make start script executable
RUN chmod +x start.sh

# Run health checks in build mode
ENV DOCKER_BUILD=true
RUN python healthcheck.py

# Set environment variables for runtime
ENV DOCKER_BUILD=false \
    RAILWAY_ENVIRONMENT=production

# Start the bot using the start script
CMD ["./start.sh"] 