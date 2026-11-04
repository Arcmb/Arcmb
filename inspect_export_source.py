from pathlib import Path
import ast
import re

ROOT = Path(__file__).resolve().parent


def inspect_python(name, keywords):
    path = ROOT / name
    if not path.is_file():
        print(f'EXPORT_INSPECT_MISSING {name}', flush=True)
        return
    text = path.read_text(encoding='utf-8')
    print(f'EXPORT_INSPECT_FILE {name} chars={len(text)}', flush=True)
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        print(f'EXPORT_INSPECT_PARSE_ERROR {name} {exc}', flush=True)
        return
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            label = node.name.lower()
            if any(key in label for key in keywords):
                source = ast.get_source_segment(text, node) or ''
                print(f'EXPORT_INSPECT_BEGIN {name}:{node.name}', flush=True)
                print(source[:30000], flush=True)
                print(f'EXPORT_INSPECT_END {name}:{node.name}', flush=True)
    for needle in ('CREATE TABLE', 'hmay_', '/api/', 'MODEL_DATA', 'model_data', 'UNIFIED', 'unified'):
        for match in list(re.finditer(re.escape(needle), text, re.I))[:8]:
            pos = match.start()
            print(f'EXPORT_CONTEXT {name} needle={needle!r} pos={pos}', flush=True)
            print(text[max(0, pos-700):min(len(text), pos+2400)], flush=True)


def inspect_js(name):
    path = ROOT / name
    if not path.is_file():
        print(f'EXPORT_INSPECT_MISSING {name}', flush=True)
        return
    text = path.read_text(encoding='utf-8')
    print(f'EXPORT_INSPECT_FILE {name} chars={len(text)}', flush=True)
    needles = (
        'const nav', 'const pages', 'pages={', 'result-model', 'performanceView',
        'workbookEntry', 'model-data', 'acts[', 'downloadPost', 'view=', 'render()',
    )
    for needle in needles:
        positions = [m.start() for m in re.finditer(re.escape(needle), text)]
        for pos in positions[:5]:
            print(f'EXPORT_JS_CONTEXT {name} needle={needle!r} pos={pos}', flush=True)
            print(text[max(0, pos-1000):min(len(text), pos+5000)], flush=True)


keywords = ('schema', 'handle', 'parse', 'import', 'score', 'answer', 'detail', 'export', 'result', 'list', 'commit', 'save', 'aggregate', 'summary')
for filename in ('model_data.py', 'unified.py', 'performance.py', 'webapp.py'):
    inspect_python(filename, keywords)
for filename in ('static/app.js', 'static/model_data.js', 'static/performance.js', 'static/two_tab.js'):
    inspect_js(filename)
print('EXPORT_INSPECT_DONE', flush=True)
