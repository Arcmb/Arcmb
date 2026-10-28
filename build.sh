#!/usr/bin/env bash
set -euo pipefail
python unpack_v23.py
python unpack_v24.py
python unpack_v241.py
python prepare_release.py
python extend_release.py
python adapt_release.py
python enhance_release.py
python simplify_import_release.py
python unified_release.py
python coordinator_release.py
python routine_release.py
python finalize_v241.py
python -m pip install -r requirements.txt
