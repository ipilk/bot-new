#!/bin/bash

echo "=== Starting Discord Music Bot ==="

# Run health check first
echo "Running health check..."
python healthcheck.py
if [ $? -ne 0 ]; then
    echo "Health check failed! Please check the logs above."
    exit 1
fi

# Start the bot
echo "Starting bot..."
python main.py 