"""Static and route checks for the final interaction fixes."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    model = (ROOT / 'model_data.py').read_text(encoding='utf-8')
    web = (ROOT / 'webapp.py').read_text(encoding='utf-8')
    html = (ROOT / 'static' / 'app.html').read_text(encoding='utf-8')
    export_js = (ROOT / 'static' / 'result_export.js').read_text(encoding='utf-8')
    bulk_js = (ROOT / 'static' / 'bulk_accounts_panel.js').read_text(encoding='utf-8')
    return_js = (ROOT / 'static' / 'return_to_owner.js').read_text(encoding='utf-8')

    require("'/api/model-data/export-results-json'" in model, 'JSON export endpoint is missing.')
    require('b64encode(blob)' in model, 'JSON export does not carry the workbook bytes.')
    require("api('/api/model-data/export-results-json'" in export_js, 'Export button does not call the robust endpoint.')
    require('resultExportSaveBase64' in export_js and 'Gerando as seis abas' in export_js, 'Export progress/download UI is incomplete.')
    require('password_digest = password_hash(password)' in web, 'Bulk password must be hashed once per chunk.')
    require("'nextOffset': next_offset" in web, 'Bulk backend pagination is missing.')
    require('Perfis processados:' in bulk_js and 'offset,limit:chunkSize' in bulk_js, 'Real bulk progress is incomplete.')
    require("acts['return-owner']" in return_js and "acts['open-account']" in return_js, 'Return-to-owner action is incomplete.')
    require('/static/result_export.js?v=2.8.9' in html, 'Export asset cache key was not updated.')
    require('/static/bulk_accounts_panel.js?v=2.8.9' in html, 'Bulk asset cache key was not updated.')
    require('/static/return_to_owner.js?v=2.8.9' in html, 'Return-to-owner asset is not loaded.')
    print('MEUCRONOGRAMA_FINAL_INTERACTIONS_CHECK_OK: Excel download, bulk progress and owner return are wired.', flush=True)


if __name__ == '__main__':
    main()
