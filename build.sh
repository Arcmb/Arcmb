#!/usr/bin/env bash
set -euo pipefail
python unpack_v23.py
python prepare_release.py
python extend_release.py
python adapt_release.py
python enhance_release.py
python -m pip install -r requirements.txt
