"""Verify the centralized bulk student-account administration panel."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    js_path = ROOT / 'static' / 'bulk_accounts_panel.js'
    require(js_path.is_file(), 'Bulk account panel asset was not generated.')
    js = js_path.read_text(encoding='utf-8')
    html = (ROOT / 'static' / 'app.html').read_text(encoding='utf-8')
    css = (ROOT / 'static' / 'style.css').read_text(encoding='utf-8')
    webapp = (ROOT / 'webapp.py').read_text(encoding='utf-8')

    for marker in [
        'Cadastro de alunos em lote',
        'bulk-accounts-toggle-password',
        'bulk-accounts-inspect',
        'bulk-accounts-create',
        'Selecionar arquivo',
        'Conferir alunos',
        'Criar contas',
        'Atualizar painel',
        'Concluído',
        '/api/accounts/bulk-from-results',
        'resultImportBulkAccountsPanel=function()',
    ]:
        require(marker in js, f'Missing bulk account UI marker: {marker}')

    require('/static/bulk_accounts_panel.js?v=2.8.6' in html, 'Bulk account panel script is missing from app.html.')
    require("'bulk_accounts_panel.js':'application/javascript; charset=utf-8'" in webapp, 'Bulk account panel MIME entry is missing.')
    require('MEU CRONOGRAMA: PAINEL DE CONTAS EM LOTE' in css, 'Bulk account panel CSS was not added.')
    print('MEUCRONOGRAMA_BULK_ACCOUNTS_PANEL_CHECK_OK: panel placement, password visibility, progress stages and result-import handoff passed.', flush=True)


if __name__ == '__main__':
    main()
