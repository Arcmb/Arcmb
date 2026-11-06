"""Verify TRI/redaction import fields, generated model and Qi visual identity."""
from pathlib import Path
import base64

import model_data as M

ROOT = Path(__file__).resolve().parent


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def workbook_bytes(value):
    if isinstance(value, tuple):
        value = next((item for item in value if isinstance(item, (bytes, bytearray))), None)
    require(isinstance(value, (bytes, bytearray)), 'Workbook exporter did not return XLSX bytes.')
    return bytes(value)


def main():
    headers = [
        'NOME', 'NOME DO SIMULADO', 'DATA DE APLICAÇÃO', 'RANKING',
        'NOTA TRI GERAL', 'TRI LINGUAGENS', 'TRI HUMANAS', 'TRI NATUREZA',
        'TRI MATEMÁTICA', 'TEMA DA REDAÇÃO', 'C1', 'C2', 'C3', 'C4', 'C5', 'NOTA DA REDAÇÃO',
    ]
    row = ['ALUNO TESTE', 'SIMULADO TESTE', '06/11/2026', 1, 750, 710, 720, 730, 840,
           'Desafios da educação brasileira', 160, 180, 160, 180, 200, 880]
    blob = workbook_bytes(M.T.export(headers, [row], first_name='TRI e Redação'))
    parsed = M._tri_parse_ranking({'file': base64.b64encode(blob).decode('ascii'), 'filename': 'teste.xlsx'})
    require(len(parsed['records']) == 1, 'The TRI/redaction model row was not parsed.')
    scores = parsed['records'][0]['scores']
    require(scores['lc'] == 710 and scores['mt'] == 840, 'TRI area scores were not parsed.')
    require(scores['redaction'] == 880, 'Essay total was not parsed.')
    require([scores[f'c{i}'] for i in range(1, 6)] == [160, 180, 160, 180, 200], 'C1-C5 were not parsed.')
    require(scores['redactionTheme'] == 'Desafios da educação brasileira', 'Essay theme was not parsed.')
    metadata = {}
    changed = M._tri_apply_metadata(metadata, scores, 'TRI e Redação', {'id': 'verifier'})
    require(changed and metadata['_redaction_c1'] == 160 and metadata['_redaction_c5'] == 200, 'Competencies were not persisted.')
    require(metadata['_redaction_theme'] == 'Desafios da educação brasileira', 'Essay theme was not persisted.')
    model = workbook_bytes(M._qi_tri_template_workbook())
    require(model[:2] == b'PK' and len(model) > 2000, 'Generated TRI/redaction workbook is invalid.')
    js = (ROOT / 'static' / 'tri_scores.js').read_text(encoding='utf-8')
    css = (ROOT / 'static' / 'style.css').read_text(encoding='utf-8')
    app = (ROOT / 'static' / 'app.html').read_text(encoding='utf-8')
    logo = (ROOT / 'static' / 'qi-logo.svg').read_text(encoding='utf-8')
    require('Gerar modelo TRI + Redação' in js and "tri-import-template" in js, 'Model download UI is missing.')
    require('C1' in js and 'C5' in js, 'Competency preview is missing.')
    require('QI VESTIBULARES PASTEL RED V1' in css and '#b65362' in css, 'Qi pastel-red palette is missing.')
    require('/static/qi-logo.svg' in app and 'QI VESTIBULARES' in app, 'Qi wordmark is missing from the app.')
    accepted_reds = ('#b65362', '#d61f3c', '#e00613')
    require('<svg' in logo and any(color in logo for color in accepted_reds), 'Qi logo asset is invalid.')
    require('#fff' in logo, 'Qi logo must preserve the white symbol.')
    print('MEUCRONOGRAMA_QI_TRI_REDACAO_CHECK_OK: model, TRI areas, C1-C5, essay total and Qi branding passed.', flush=True)


if __name__ == '__main__':
    main()
