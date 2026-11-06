from pathlib import Path
import base64
import io
import zipfile

ROOT = Path(__file__).resolve().parent


def require(value, message):
    if not value:
        raise RuntimeError(message)


def ranking_xlsx():
    content_types = '''<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
 <Default Extension="xml" ContentType="application/xml"/>
</Types>'''
    workbook = '''<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
 <sheets><sheet name="Ranking Geral" sheetId="1" r:id="rId1"/></sheets>
</workbook>'''
    relationships = '''<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>'''

    def text_cell(ref, value):
        return f'<c r="{ref}" t="inlineStr"><is><t>{value}</t></is></c>'

    def num_cell(ref, value):
        return f'<c r="{ref}"><v>{value}</v></c>'

    headers = ['NOME', 'TURMA', 'TIPO', 'data', 'RANKING', 'TRI', 'TRI 10%', 'TRI LING', 'TRI HUM', 'TRI NAT', 'TRI MAT', 'RED']
    cols = [chr(65 + i) for i in range(len(headers))]
    row1 = ''.join(text_cell(f'{col}1', value) for col, value in zip(cols, headers))
    row2 = ''.join([
        text_cell('A2', 'ALUNA TESTE'), text_cell('B2', 'Qi Med 01'), text_cell('C2', '10º Simulado Enem SAS'),
        text_cell('D2', '25/10/2026'), num_cell('E2', 7), num_cell('F2', 853.8), num_cell('G2', 939.18),
        num_cell('H2', 743), num_cell('I2', 772), num_cell('J2', 831), num_cell('K2', 923), num_cell('L2', 1000),
    ])
    sheet = f'''<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
 <sheetData><row r="1">{row1}</row><row r="2">{row2}</row></sheetData>
</worksheet>'''
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('[Content_Types].xml', content_types)
        archive.writestr('xl/workbook.xml', workbook)
        archive.writestr('xl/_rels/workbook.xml.rels', relationships)
        archive.writestr('xl/worksheets/sheet1.xml', sheet)
    return base64.b64encode(output.getvalue()).decode('ascii')


def main():
    model_text = (ROOT / 'model_data.py').read_text(encoding='utf-8')
    js = (ROOT / 'static' / 'tri_scores.js').read_text(encoding='utf-8')
    html = (ROOT / 'static' / 'app.html').read_text(encoding='utf-8')
    webapp = (ROOT / 'webapp.py').read_text(encoding='utf-8')

    require('NOTAS TRI VINCULADAS AO SIMULADO' in model_text, 'TRI backend marker is missing.')
    require('/api/model-data/tri-inspect' in model_text and '/api/model-data/tri-confirm' in model_text, 'TRI endpoints are missing.')
    require('_tri_lc' in model_text and '_tri_mt' in model_text and 'Nota TRI geral' in model_text, 'TRI metadata/export fields are incomplete.')
    require('Importar Ranking e notas TRI' in js and 'TCT/acertos e TRI são indicadores diferentes' in js, 'TRI interface is incomplete.')
    require('/static/tri_scores.js?v=' in html, 'TRI asset is not loaded.')
    require("'tri_scores.js':'application/javascript; charset=utf-8'" in webapp, 'TRI static MIME is missing.')

    import model_data
    parsed = model_data._tri_parse_ranking({'file': ranking_xlsx()})
    require(parsed['sheet'] == 'Ranking Geral', 'Ranking Geral sheet was not selected.')
    require(len(parsed['records']) == 1, 'Ranking row was not parsed.')
    scores = parsed['records'][0]['scores']
    require(scores['ranking'] == 7, 'Ranking was not parsed.')
    require(scores['tri'] == 853.8 and scores['triBonus'] == 939.18, 'General TRI fields were not parsed.')
    require(scores['lc'] == 743 and scores['ch'] == 772 and scores['cn'] == 831 and scores['mt'] == 923, 'TRI scores by area were not parsed.')
    require(scores['redaction'] == 1000, 'Redaction score was not parsed.')
    compile(model_text, 'model_data.py', 'exec')
    print('MEUCRONOGRAMA_TRI_SCORES_CHECK_OK: Ranking Geral, TRI geral, TRI por área, redação, exportação e painel passed.', flush=True)


if __name__ == '__main__':
    main()
