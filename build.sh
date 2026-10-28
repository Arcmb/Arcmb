#!/usr/bin/env bash
set -euo pipefail
python prepare_release.py
python -m pip install -r requirements.txt
