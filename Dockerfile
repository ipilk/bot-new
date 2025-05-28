FROM python:3.9-slim

WORKDIR /app

# Install system dependencies and FFmpeg
RUN apt-get update && \
    apt-get install -y \
    ffmpeg \
    opus-tools \
    libopus0 \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && which ffmpeg && \
    ln -sf $(which ffmpeg) /usr/local/bin/ffmpeg && \
    ln -sf $(which ffprobe) /usr/local/bin/ffprobe && \
    ffmpeg -version

# Set FFmpeg path in environment
ENV PATH="/usr/local/bin:${PATH}" \
    FFMPEG_PATH="/usr/local/bin/ffmpeg"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Make scripts executable
RUN chmod +x start.sh entrypoint.sh

# Verify FFmpeg installation
RUN ffmpeg -version && \
    echo "FFmpeg path: $FFMPEG_PATH" && \
    ls -l $FFMPEG_PATH

# Run health checks in build mode
ENV DOCKER_BUILD=true
RUN python healthcheck.py

# Set environment variables for runtime
ENV DOCKER_BUILD=false \
    RAILWAY_ENVIRONMENT=production

# Use entrypoint script
ENTRYPOINT ["./entrypoint.sh"] 