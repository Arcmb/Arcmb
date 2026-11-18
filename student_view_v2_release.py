"""v3.8.2: um único campo de busca de aluno, visão do aluno ao selecionar uma conta de aluno,
revisões unificadas em um item de menu e correção de três arquivos JS que nunca executavam."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent


def patch(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: esperado 1 trecho, encontrado {count}.')
    return text.replace(old, new, 1)


def fix_legacy_js():
    fixed = []
    for name in ('review_history.js', 'review_calendar_table.js', 'student_guidance.js'):
        path = ROOT / 'static' / name
        text = path.read_text(encoding='utf-8')
        if text.startswith('\\\n'):
            text = text[2:]
            fixed.append(name)
        text = text.replace("let reviewCalendarMonth=(S.serverDate||", "let reviewCalendarMonth=(S?.serverDate||")
        text = text.replace("let qiReviewMonth=((typeof S!=='undefined'&&S.serverDate)||", "let qiReviewMonth=((typeof S!=='undefined'&&S?.serverDate)||")
        path.write_text(text, encoding='utf-8')
    return fixed


def main():
    fixed = fix_legacy_js()
    shutil.copyfile(ROOT / 'release_assets' / 'student_view_v2.js', ROOT / 'static' / 'student_view_v2.js')
    webapp = ROOT / 'webapp.py'
    text = webapp.read_text(encoding='utf-8')
    if "'student_view_v2.js'" not in text:
        text = patch(text, "'provisional_renewal.js':'application/javascript; charset=utf-8',",
                     "'provisional_renewal.js':'application/javascript; charset=utf-8','student_view_v2.js':'application/javascript; charset=utf-8',",
                     'static allowlist')
        webapp.write_text(text, encoding='utf-8')
    html_path = ROOT / 'static' / 'app.html'
    html = html_path.read_text(encoding='utf-8')
    if '/static/student_view_v2.js' not in html:
        html = patch(html, '<script src="/static/provisional_renewal.js?v=3.7.17" defer></script>',
                     '<script src="/static/provisional_renewal.js?v=3.7.17" defer></script>'
                     '<script src="/static/student_view_v2.js?v=3.8.2" defer></script>', 'script tag')
        html_path.write_text(html, encoding='utf-8')
    print('MEUCRONOGRAMA_V382_STUDENT_VIEW_READY: single account search, student view, unified reviews. Fixed JS: ' + (', '.join(fixed) or 'none'), flush=True)


if __name__ == '__main__':
    main()
