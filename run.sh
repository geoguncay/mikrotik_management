#!/bin/bash
# MikroTik Management - Startup script

cd "$(dirname "$0")/backend"
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
