#!/usr/bin/env bash
set -euo pipefail
# As verificações rodam num banco SQLite temporário, nunca no banco de produção.
python checks/run_all.py
exec gunicorn webapp:application --bind "0.0.0.0:${PORT:-10000}" --workers 1 --threads 4 --timeout 60 --access-logfile -
