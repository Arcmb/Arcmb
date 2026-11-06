"""Normalize the project workbook exporter result to raw XLSX bytes."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
path = ROOT / 'model_data.py'
text = path.read_text(encoding='utf-8')
old = "    return T.export(headers, rows, first_name='TRI e Redação', extra_sheets=[('Como preencher', help_headers, help_rows)])"
new = """    output = T.export(headers, rows, first_name='TRI e Redação', extra_sheets=[('Como preencher', help_headers, help_rows)])
    if isinstance(output, tuple):
        output = next((item for item in output if isinstance(item, (bytes, bytearray))), None)
    if not isinstance(output, (bytes, bytearray)):
        raise ValueError('Não foi possível gerar o arquivo-modelo TRI e Redação.')
    return bytes(output)"""
if old not in text:
    raise RuntimeError('TRI template exporter anchor was not found.')
text = text.replace(old, new, 1)
path.write_text(text, encoding='utf-8')
print('MEUCRONOGRAMA_QI_TRI_TEMPLATE_BYTES_READY: workbook exporter normalized to XLSX bytes.', flush=True)
