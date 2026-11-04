from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / 'static'
NEEDLES = (
    'Modelo de resultados por área',
    'Gerar Excel separado por áreas',
    'resultModelView',
    "acts['model-download']",
    'two_tab.js',
)

print('UI_INSPECT_BEGIN', flush=True)
for path in sorted(STATIC.glob('*')):
    if not path.is_file():
        continue
    try:
        text = path.read_text(encoding='utf-8')
    except Exception:
        continue
    hits = []
    for needle in NEEDLES:
        start = 0
        while True:
            pos = text.find(needle, start)
            if pos < 0:
                break
            hits.append((pos, needle))
            start = pos + len(needle)
    if hits:
        print(f'UI_FILE {path.relative_to(ROOT)} length={len(text)} hits={len(hits)}', flush=True)
        for pos, needle in hits[:20]:
            left = max(0, pos - 500)
            right = min(len(text), pos + len(needle) + 1200)
            snippet = text[left:right].replace('\n', '\\n')
            print(f'UI_HIT {path.name} needle={needle!r} pos={pos} :: {snippet}', flush=True)
print('UI_INSPECT_END', flush=True)
