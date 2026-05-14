#!/bin/bash

echo "🔄 Restarting Celery Worker..."
echo ""

# Kill existing Celery processes
echo "1. Stopping existing Celery workers..."
pkill -f "celery.*worker"
sleep 2

# Check if any still running
if ps aux | grep -i "celery.*worker" | grep -v grep > /dev/null; then
    echo "   ⚠️  Force killing remaining processes..."
    pkill -9 -f "celery.*worker"
    sleep 1
fi

echo "   ✅ Stopped"
echo ""

# Start Celery worker
echo "2. Starting Celery worker..."
cd "$(dirname "$0")/.."

# Start in background
nohup .venv/bin/celery -A app.celery_app:celery_app worker --pool=prefork --concurrency=10 -l info > celery_worker.log 2>&1 &

sleep 3

# Check if started
if ps aux | grep -i "celery.*worker" | grep -v grep > /dev/null; then
    echo "   ✅ Celery worker started"
    echo ""
    echo "📊 Worker Status:"
    ps aux | grep -i "celery.*worker" | grep -v grep | head -3
else
    echo "   ❌ Failed to start Celery worker"
    echo ""
    echo "Check logs:"
    echo "  tail -f celery_worker.log"
fi

echo ""
echo "Logs: tail -f celery_worker.log"
