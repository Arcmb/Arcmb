"""Roda todas as verificações num banco SQLite temporário (nunca no banco de produção).

Uso: python checks/run_all.py
Sai com erro na primeira verificação que falhar.
"""
from pathlib import Path
import os
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CHECKS = Path(__file__).resolve().parent

# Ordem histórica: as verificações estáticas primeiro, as de fluxo completo depois.
ORDER = [
    'verify_two_tab_asset', 'verify_two_tab', 'verify_result_export', 'verify_result_import', 'verify_student_import_rules',
    'verify_bulk_student_accounts', 'verify_bulk_accounts_panel', 'verify_student_summary', 'verify_final_interactions',
    'verify_academic_engine', 'verify_student_home_dashboard', 'verify_tri_scores', 'verify_exam_review_sync',
    'verify_qi_tri_redaction', 'verify_study_schedule', 'verify_review_history', 'verify_review_subject_labels',
    'verify_math_study_preset', 'verify_review_calendar', 'verify_schedule_admin_refinement', 'verify_student_guidance',
    'verify_final_priority_review_branding', 'verify_dedicated_review_table', 'verify_discipline_colors_review_runtime',
    'verify_responsive_ui_refinement', 'verify_review_table_runtime_bridge', 'verify_review_nav_permanent',
    'verify_review_table_compact_layout', 'verify_review_sequence_density', 'verify_review_start_date', 'verify_use_guide',
    'verify_academic_year', 'verify_tri_import_stability', 'verify_tri_import_token', 'verify_tri_dashboard',
    'verify_performance_refinement', 'verify_management_dashboard', 'verify_management_refinement_v36',
    'verify_management_refinement_v37', 'verify_reports_module', 'verify_hotfix_v371', 'verify_hotfix_v372',
    'verify_hotfix_v373', 'verify_hotfix_v374', 'verify_hotfix_v375', 'verify_hotfix_v376', 'verify_hotfix_v377',
    'verify_hotfix_v378', 'verify_hotfix_v379', 'verify_hotfix_v3710_status', 'verify_hotfix_v3711_management_filter',
    'verify_hotfix_v3712_class_analytics', 'verify_hotfix_v3713_sort', 'verify_provisional_expiry', 'verify_motor_v3718',
    'verify_student_view_v2', 'verify_motor_profiles', 'verify_school_reports', 'verify_disciplines_catalog', 'verify_enem_items', 'verify_onboarding', 'verify_csp_styles', 'verify_exam_delete', 'verify_exam_detail', 'verify_import_fixes',
    'verify_site_version', 'verify_release', 'verify_adaptive', 'verify_selective', 'verify_workbook',
    'verify_coordinator', 'verify_model_data',
]


def main():
    missing = sorted({p.stem for p in CHECKS.glob('verify_*.py')} - set(ORDER))
    if missing:
        print('Verificações fora da lista em checks/run_all.py:', ', '.join(missing), flush=True)
        return 2
    with tempfile.TemporaryDirectory() as tmp:
        env = dict(os.environ, LOCAL_TEST='1', LOCAL_DB=str(Path(tmp) / 'verify.sqlite3'),
                   PYTHONPATH=os.pathsep.join([str(ROOT), str(CHECKS)]))
        env.setdefault('ALLOWED_HOSTS', 'meucronograma.onrender.com')
        for name in ORDER:
            result = subprocess.run([sys.executable, str(CHECKS / (name + '.py'))], cwd=ROOT, env=env)
            if result.returncode:
                print(f'VERIFICACAO_FALHOU: {name}', flush=True)
                return result.returncode
    print('MEUCRONOGRAMA_ALL_CHECKS_OK', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
