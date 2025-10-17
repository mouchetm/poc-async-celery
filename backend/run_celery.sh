#!/bin/bash

# Script to run Celery worker for chat tasks

echo "Starting Celery worker for chat tasks..."
echo "Make sure Redis is running on localhost:6379"
echo ""

cd "$(dirname "$0")"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run Celery worker
celery -A celery_config worker --loglevel=info --pool=solo

