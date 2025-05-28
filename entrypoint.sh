#!/bin/bash

# Function to handle termination signals
handle_term() {
    echo "Received termination signal"
    kill -TERM "$child"
    wait "$child"
    exit 0
}

# Set up signal handlers
trap handle_term SIGTERM SIGINT

# Start the bot and store its PID
./start.sh & child=$!

# Wait for the bot process
wait "$child" 