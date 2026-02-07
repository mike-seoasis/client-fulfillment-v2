#!/bin/sh
echo "=== ENTRYPOINT STARTING ==="
echo "PORT=$PORT"
echo "PATH=$PATH"
which python || echo "python not found"
which uvicorn || echo "uvicorn not found"
python -u -m app.deploy || echo "Deploy script failed, continuing anyway..."
echo "=== STARTING UVICORN ==="
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1
