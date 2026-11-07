"""Persist the dedicated review-table entry in the base navigation.

The review page renderer is independent, but the menu entry was still injected
at runtime. Any initialization-order change could therefore hide the tab even
while the page code and learner data were valid. This release patches the base
app navigation after all generated assets are assembled and bumps cache keys.
"""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent
MARK="['review-table','Tabela de revisões']"


def patch_navigation():
    path=ROOT/'static'/'app.js'
    text=path.read_text(encoding='utf-8')
    if MARK not in text:
        patterns=(
            r"(\[\s*['\"]reviews['\"]\s*,\s*['\"]Minhas revisões['\"]\s*\])",
            r"(\[\s*['\"]reviews['\"]\s*,\s*['\"][^'\"]*revisões[^'\"]*['\"]\s*\])",
        )
        for pattern in patterns:
            updated,count=re.subn(pattern,lambda match:match.group(1)+','+MARK,text,count=1,flags=re.I)
            if count:
                text=updated
                break
        else:
            declaration=re.search(r"((?:const|let|var)\s+navItems\s*=\s*\[)(.*?)(\]\s*;)",text,flags=re.S)
            if not declaration:
                raise RuntimeError('Não foi possível localizar a lista principal de navegação em static/app.js.')
            body=declaration.group(2).rstrip()
            separator=',' if body and not body.endswith(',') else ''
            replacement=declaration.group(1)+body+separator+MARK+declaration.group(3)
            text=text[:declaration.start()]+replacement+text[declaration.end():]
    if MARK not in text:
        raise RuntimeError('A entrada permanente Tabela de revisões não foi inserida.')
    path.write_text(text,encoding='utf-8')


def bump_cache_keys():
    path=ROOT/'static'/'app.html'
    html=path.read_text(encoding='utf-8')
    html=re.sub(r'/static/app\.js\?v=[^"\']+','/static/app.js?v=2.9.5',html)
    html=re.sub(r'/static/review_table_page\.js\?v=[^"\']+','/static/review_table_page.js?v=5.4.1',html)
    path.write_text(html,encoding='utf-8')


def main():
    patch_navigation();bump_cache_keys()
    print('MEUCRONOGRAMA_REVIEW_NAV_READY: Tabela de revisões is permanent in the base navigation.',flush=True)


if __name__=='__main__':main()
