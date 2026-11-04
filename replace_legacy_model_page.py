"""Replace the legacy area-based model page with the definitive two-tab page.

This runs after all historical release scripts. It edits the generated legacy
JavaScript itself, so route tables that captured resultModelView cannot restore
the obsolete screen later.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / 'static'
LEGACY_TITLE = 'Modelo de resultados por área'
LEGACY_BUTTON = 'Gerar Excel separado por áreas'
DELEGATE = 'function resultModelView(){return v281ResultModelView();}'


def matching_brace(text: str, opening: int) -> int:
    depth = 0
    i = opening
    quote = None
    escape = False
    line_comment = False
    block_comment = False
    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ''
        if line_comment:
            if ch == '\n':
                line_comment = False
            i += 1
            continue
        if block_comment:
            if ch == '*' and nxt == '/':
                block_comment = False
                i += 2
            else:
                i += 1
            continue
        if quote:
            if escape:
                escape = False
            elif ch == '\\':
                escape = True
            elif ch == quote:
                quote = None
            i += 1
            continue
        if ch == '/' and nxt == '/':
            line_comment = True
            i += 2
            continue
        if ch == '/' and nxt == '*':
            block_comment = True
            i += 2
            continue
        if ch in ("'", '"', '`'):
            quote = ch
            i += 1
            continue
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise RuntimeError('Unclosed JavaScript function body.')


def replace_function(text: str):
    patterns = (
        r'function\s+resultModelView\s*\([^)]*\)\s*\{',
        r'resultModelView\s*=\s*function\s*\([^)]*\)\s*\{',
        r'resultModelView\s*=\s*(?:async\s*)?\([^)]*\)\s*=>\s*\{',
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        opening = text.find('{', match.start(), match.end())
        end = matching_brace(text, opening)
        suffix = end + 1
        if suffix < len(text) and text[suffix] == ';':
            suffix += 1
        return text[:match.start()] + DELEGATE + text[suffix:], 1
    return text, 0


def replace_action(text: str):
    pattern = re.compile(
        r"acts\[['\"]model-download['\"]\]\s*=\s*(?:async\s*)?\([^)]*\)\s*=>\s*\{"
    )
    match = pattern.search(text)
    if not match:
        return text, 0
    opening = text.find('{', match.start(), match.end())
    end = matching_brace(text, opening)
    suffix = end + 1
    if suffix < len(text) and text[suffix] == ';':
        suffix += 1
    return text[:match.start()] + "acts['model-download']=v281DownloadModel;" + text[suffix:], 1


def prepare():
    candidates = []
    for path in sorted(STATIC.glob('*.js')):
        if path.name == 'two_tab.js':
            continue
        text = path.read_text(encoding='utf-8')
        if LEGACY_TITLE in text or LEGACY_BUTTON in text:
            candidates.append((path, text))
    if len(candidates) != 1:
        names = ', '.join(str(path.relative_to(ROOT)) for path, _ in candidates) or 'nenhum'
        raise RuntimeError(f'Esperado um único arquivo da tela antiga; encontrados: {names}.')

    path, text = candidates[0]
    text, functions = replace_function(text)
    if functions != 1:
        raise RuntimeError(f'Função resultModelView não localizada em {path.name}.')
    text, _ = replace_action(text)
    if LEGACY_TITLE in text or LEGACY_BUTTON in text:
        raise RuntimeError('Textos da interface antiga permaneceram após a substituição.')
    if DELEGATE not in text:
        raise RuntimeError('Delegação para a página de duas abas não foi instalada.')
    path.write_text(text, encoding='utf-8')

    print(
        f'MEUCRONOGRAMA_MODEL_PAGE_REPLACED: {path.name} now delegates to the definitive two-tab page.',
        flush=True,
    )


if __name__ == '__main__':
    prepare()
