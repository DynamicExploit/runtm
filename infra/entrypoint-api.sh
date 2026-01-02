#!/bin/bash
set -e

# Check ownership of mounted volumes
# Handles case where volume was created by root
if [ -w /artifacts ]; then
    echo "Artifacts directory writable"
else
    echo "Warning: /artifacts not writable by runtm user"
fi

# Run migrations and start server
exec sh -c "alembic upgrade head && uvicorn runtm_api.main:app --host 0.0.0.0 --port 8000"

