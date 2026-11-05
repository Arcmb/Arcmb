from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent


def emit_file(path, markers, radius=1800):
    text = path.read_text(encoding='utf-8')
    print(f'ACCOUNT_SOURCE_FILE {path} chars={len(text)}', flush=True)
    for marker in markers:
        start = 0
        hits = 0
        while True:
            pos = text.find(marker, start)
            if pos < 0:
                break
            hits += 1
            left = max(0, pos - radius)
            right = min(len(text), pos + len(marker) + radius)
            snippet = text[left:right].replace('\n', '\\n')
            print(f'ACCOUNT_SOURCE_HIT file={path.name} marker={marker!r} pos={pos} :: {snippet}', flush=True)
            start = pos + len(marker)
        if hits == 0:
            print(f'ACCOUNT_SOURCE_MISS file={path.name} marker={marker!r}', flush=True)


print('ACCOUNT_SOURCE_INSPECT_BEGIN', flush=True)
emit_file(ROOT / 'static' / 'app.js', [
    'function accountsView',
    "acts['new-account']",
    "acts['create-account']",
    '/api/accounts',
    '/api/account',
    'create-account',
    'create-user',
], radius=2600)
path = ROOT / 'static' / 'coordinator_accounts.js'
if path.exists():
    emit_file(path, ['accountsView', 'create', 'account', 'password'], radius=2200)
emit_file(ROOT / 'webapp.py', [
    "path == '/api/accounts'",
    "path == '/api/account'",
    'create_user(',
    'allowed_accounts(',
    "'/api/accounts'",
    "'/api/account'",
], radius=3000)
print('ACCOUNT_SOURCE_INSPECT_END', flush=True)
