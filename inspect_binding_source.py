from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parent
source = (ROOT / 'model_data.py').read_text(encoding='utf-8')
module = ast.parse(source)
print('BINDING_INSPECT_BEGIN', flush=True)
for node in module.body:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == '_student_key':
        print('BINDING_FUNCTION _student_key', flush=True)
        print(ast.get_source_segment(source, node), flush=True)
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == 'prepare':
        block = ast.get_source_segment(source, node) or ''
        lines = block.splitlines()
        markers = ('accounts', 'resolved', 'mapping', "student['login']", "student['name']", 'username', 'by_name', 'by_login')
        printed = set()
        for index, line in enumerate(lines):
            if any(marker in line for marker in markers):
                start = max(0, index - 5)
                end = min(len(lines), index + 8)
                key = (start, end)
                if key in printed:
                    continue
                printed.add(key)
                print(f'BINDING_PREPARE_LINES {start + 1}-{end}', flush=True)
                for number in range(start, end):
                    print(f'{number + 1:04d}: {lines[number]}', flush=True)
print('BINDING_INSPECT_END', flush=True)
