#!/usr/bin/env bash
set -euo pipefail
python verify_release.py
python verify_adaptive.py
python verify_selective.py
python verify_workbook.py
python verify_coordinator.py
exec gunicorn webapp:application --bind "0.0.0.0:${PORT:-10000}" --workers 1 --threads 4 --timeout 60 --access-logfile -
