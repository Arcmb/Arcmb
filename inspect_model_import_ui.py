from pathlib import Path
import re

path = Path(__file__).resolve().parent / 'static' / 'model_data.js'
text = path.read_text(encoding='utf-8')

print('MODEL_IMPORT_UI_INSPECT_BEGIN', flush=True)
for marker in ('function workbookEntry', "acts['workbook-inspect']", "acts['workbook-preview']", "acts['workbook-confirm']", 'modelDataDraft', 'workbookDraft'):
    start = 0
    while True:
        pos = text.find(marker, start)
        if pos < 0:
            break
        left = max(0, pos - 500)
        right = min(len(text), pos + 4500)
        print(f'MODEL_IMPORT_UI_HIT marker={marker!r} pos={pos}', flush=True)
        print(text[left:right].replace('\n', '\\n'), flush=True)
        start = pos + len(marker)
print('MODEL_IMPORT_UI_INSPECT_END', flush=True)
