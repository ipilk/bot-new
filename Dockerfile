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

# Make scripts executable
RUN chmod +x start.sh entrypoint.sh

# Run health checks in build mode
ENV DOCKER_BUILD=true
RUN python healthcheck.py

# Set environment variables for runtime
ENV DOCKER_BUILD=false \
    RAILWAY_ENVIRONMENT=production \
    PORT=8080

# Expose port for health checks
EXPOSE 8080

# Start both the health check server and the bot
CMD ["sh", "-c", "python healthcheck.py --server & python main.py"] 