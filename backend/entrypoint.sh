#!/bin/sh
set -e

echo "Starting deployment script..."
python -u -m app.deploy

echo "Starting uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1
