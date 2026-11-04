from pathlib import Path
import ast
import re


def inspect_python(path_name):
    path = Path(path_name)
    text = path.read_text(encoding='utf-8')
    tree = ast.parse(text)
    print(f'INSPECT_FILE {path_name} {len(text)} chars')
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            print(f'INSPECT_NODE {type(node).__name__} {node.name} lines {node.lineno}-{getattr(node, "end_lineno", node.lineno)}')
            if any(k in node.name.lower() for k in ('workbook','template','area','sheet','import','parse','handle','build')):
                segment = ast.get_source_segment(text, node) or ''
                print(f'INSPECT_SOURCE_BEGIN {path_name}:{node.name}')
                print(segment[:18000])
                print(f'INSPECT_SOURCE_END {path_name}:{node.name}')


def inspect_js(path_name):
    text = Path(path_name).read_text(encoding='utf-8')
    print(f'INSPECT_FILE {path_name} {len(text)} chars')
    for match in re.finditer(r'(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(', text):
        print('INSPECT_JS_FUNCTION', match.group(1))
    for needle in ('Gerar', 'Informações', 'Questões por área', 'area-workbook', 'template-area', 'workbook'):
        pos = text.find(needle)
        if pos >= 0:
            print(f'INSPECT_JS_CONTEXT {needle}')
            print(text[max(0,pos-1500):pos+6500])


inspect_python('area_workbook.py')
inspect_python('area_tabs_release.py')
inspect_js('static/area_tabs.js')
