"""v3.7.19: Master e coordenação veem a conta do aluno com a interface do aluno."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent


def patch(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: esperado 1 trecho, encontrado {count}.')
    return text.replace(old, new, 1)


def main():
    shutil.copyfile(ROOT / 'release_assets' / 'student_view_mode.js', ROOT / 'static' / 'student_view_mode.js')
    webapp = ROOT / 'webapp.py'
    text = webapp.read_text(encoding='utf-8')
    if "'student_view_mode.js'" not in text:
        text = patch(text, "'provisional_renewal.js':'application/javascript; charset=utf-8',",
                     "'provisional_renewal.js':'application/javascript; charset=utf-8','student_view_mode.js':'application/javascript; charset=utf-8',",
                     'static allowlist')
        webapp.write_text(text, encoding='utf-8')
    html_path = ROOT / 'static' / 'app.html'
    html = html_path.read_text(encoding='utf-8')
    if '/static/student_view_mode.js' not in html:
        html = patch(html, '<script src="/static/provisional_renewal.js?v=3.7.17" defer></script>',
                     '<script src="/static/provisional_renewal.js?v=3.7.17" defer></script>'
                     '<script src="/static/student_view_mode.js?v=3.7.19" defer></script>', 'script tag')
        html_path.write_text(html, encoding='utf-8')
    print('MEUCRONOGRAMA_V3719_STUDENT_VIEW_READY: managers see student accounts with the student interface.', flush=True)


if __name__ == '__main__':
    main()
