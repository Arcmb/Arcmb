"""v3.8.0: menu agrupado (aluno 7 grupos, gestão 5) com sub-abas; todas as telas preservadas."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent


def patch(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: esperado 1 trecho, encontrado {count}.')
    return text.replace(old, new, 1)


def fix_stray_backslash():
    """Corrige arquivos JS gerados com uma barra invertida na 1ª linha (nunca executavam)."""
    fixed = []
    for name in ('review_history.js', 'review_calendar_table.js', 'student_guidance.js'):
        path = ROOT / 'static' / name
        text = path.read_text(encoding='utf-8')
        if text.startswith('\\\n'):
            path.write_text(text[2:], encoding='utf-8')
            fixed.append(name)
    guards = {
        'review_calendar_table.js': ("let reviewCalendarMonth=(S.serverDate||", "let reviewCalendarMonth=(S?.serverDate||"),
        'student_guidance.js': ("let qiReviewMonth=((typeof S!=='undefined'&&S.serverDate)||", "let qiReviewMonth=((typeof S!=='undefined'&&S?.serverDate)||"),
    }
    for name, (old, new) in guards.items():
        path = ROOT / 'static' / name
        text = path.read_text(encoding='utf-8')
        if old in text:
            path.write_text(text.replace(old, new, 1), encoding='utf-8')
            fixed.append(name + ' (data inicial)')
    return fixed


def main():
    fixed = fix_stray_backslash()
    shutil.copyfile(ROOT / 'release_assets' / 'nav_v4.js', ROOT / 'static' / 'nav_v4.js')
    webapp = ROOT / 'webapp.py'
    text = webapp.read_text(encoding='utf-8')
    if "'nav_v4.js'" not in text:
        text = patch(text, "'student_view_mode.js':'application/javascript; charset=utf-8',",
                     "'student_view_mode.js':'application/javascript; charset=utf-8','nav_v4.js':'application/javascript; charset=utf-8',",
                     'static allowlist')
        webapp.write_text(text, encoding='utf-8')
    html_path = ROOT / 'static' / 'app.html'
    html = html_path.read_text(encoding='utf-8')
    if '/static/nav_v4.js' not in html:
        html = patch(html, '<script src="/static/student_view_mode.js?v=3.7.19" defer></script>',
                     '<script src="/static/student_view_mode.js?v=3.7.19" defer></script>'
                     '<script src="/static/nav_v4.js?v=3.8.0" defer></script>', 'script tag')
        html_path.write_text(html, encoding='utf-8')
    print('MEUCRONOGRAMA_V380_NAV_READY: grouped navigation with sub-tabs; every legacy view kept. Fixed JS: ' + (', '.join(fixed) or 'none'), flush=True)


if __name__ == '__main__':
    main()
