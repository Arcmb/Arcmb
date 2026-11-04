#!/usr/bin/env bash
set -euo pipefail
python unpack_v23.py
python unpack_v24.py
python unpack_v241.py
python unpack_v25.py
python unpack_v27.py
python prepare_release.py
python extend_release.py
python adapt_release.py
python enhance_release.py
python simplify_import_release.py
python unified_release.py
python coordinator_release.py
python routine_release.py
python finalize_v241.py
python area_tabs_release.py
python finalize_v25.py
python simulado_info_release.py
python model_data_release.py
python finalize_v27.py
python finalize_v27_assets.py
python two_tab_release.py
python finalize_v281.py
python finalize_v28.py
python inspect_ui_build.py
python -m pip install -r requirements.txt
