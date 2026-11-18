"""Verificação estática da v3.10.0. Não grava no banco."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    import school_reports as S
    webapp = (ROOT / 'webapp.py').read_text(encoding='utf-8')
    require("if path.startswith('/api/school-reports/'):" in webapp, 'Rota dos relatórios ausente.')
    require("user.get('role') not in ('master', 'coordenador')" in (ROOT / 'school_reports.py').read_text(encoding='utf-8'), 'Relatórios devem ser restritos à gestão.')
    require("response=(str(answer)" in (ROOT / 'model_data.py').read_text(encoding='utf-8'), 'Importação deve guardar a alternativa marcada.')
    require('/static/school_reports.js' in (ROOT / 'static' / 'app.html').read_text(encoding='utf-8'), 'Script da tela ausente.')
    require(S._pct(1, 4) == 25.0 and S._pct(0, 0) is None, 'Cálculo de percentual incorreto.')
    require(S._priority(65, 20, 1) == 'alta' and S._priority(52, 20, 3) == 'alta' and S._priority(52, 20, 2) == 'media' and S._priority(30, 20, 5) == 'baixa' and S._priority(90, 5, 5) == 'dados', 'Regra de prioridade incorreta.')
    require("'/api/school-reports/most-missed'" in (ROOT / 'school_reports.py').read_text(encoding='utf-8'), 'Relatório de mais errados ausente.')
    print('MEUCRONOGRAMA_V3100_SCHOOL_REPORTS_CHECK_OK: routes, manager-only access and response capture present.', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('MEUCRONOGRAMA_V3100_SCHOOL_REPORTS_CHECK_FAILED:', exc, flush=True)
        sys.exit(1)
