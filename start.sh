#!/usr/bin/env bash
set -euo pipefail
python verify_two_tab_asset.py || exit 18
python verify_two_tab.py || exit 17
python verify_result_export.py || exit 19
python verify_result_import.py || exit 20
python verify_student_import_rules.py || exit 21
python verify_bulk_student_accounts.py || exit 22
python verify_bulk_accounts_panel.py || exit 23
python verify_student_summary.py || exit 24
python verify_final_interactions.py || exit 25
python verify_academic_engine.py || exit 26
python verify_student_home_dashboard.py || exit 27
python verify_tri_scores.py || exit 28
python verify_release.py || exit 11
python verify_adaptive.py || exit 12
python verify_selective.py || exit 13
python verify_workbook.py || exit 14
python verify_coordinator.py || exit 15
python verify_model_data.py || exit 16
exec gunicorn webapp:application --bind "0.0.0.0:${PORT:-10000}" --workers 1 --threads 4 --timeout 60 --access-logfile -
