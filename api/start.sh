#!/bin/sh
set -e
PORT="${PORT:-8010}"
exec python -m uvicorn main:app --host 0.0.0.0 --port "$PORT"
