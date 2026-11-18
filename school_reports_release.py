"""v3.10.0: Relatórios da escola (atenção, questões, assuntos × turmas, redação, perfis por turma)
e registro da alternativa marcada nas próximas importações."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
MARK = '# === SCHOOL REPORTS V3.10.0 ==='


def patch(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: esperado 1 trecho, encontrado {count}.')
    return text.replace(old, new, 1)


def main():
    webapp = ROOT / 'webapp.py'
    text = webapp.read_text(encoding='utf-8')
    if MARK not in text:
        text = patch(text, "import motor_profiles as MOTOR", "import school_reports as SCHOOL_REPORTS  " + MARK + "\nimport motor_profiles as MOTOR", 'import')
        text = patch(text, "            if path.startswith('/api/motor/'):\n",
                     "            if path.startswith('/api/school-reports/'):\n"
                     "                return SCHOOL_REPORTS.handle(self,c,user,path,method,data,query,start,HTTPError)\n"
                     "            if path.startswith('/api/motor/'):\n", 'route')
        text = patch(text, "'motor_profiles.js':'application/javascript; charset=utf-8',",
                     "'motor_profiles.js':'application/javascript; charset=utf-8','school_reports.js':'application/javascript; charset=utf-8',", 'allowlist')
        webapp.write_text(text, encoding='utf-8')
    md = ROOT / 'model_data.py'
    text = md.read_text(encoding='utf-8')
    if MARK not in text:
        text = patch(text,
                     "metrics[f'questao:{number:03d}'] = dict(name=f'Questão {number:02d}', correct=result, total=1 if result is not None else None)",
                     "metrics[f'questao:{number:03d}'] = dict(name=f'Questão {number:02d}', correct=result, total=1 if result is not None else None, response=(str(answer).strip().upper() if answer is not None and str(answer).strip().upper() in ('A', 'B', 'C', 'D', 'E') else ''))  " + MARK,
                     'response letter')
        md.write_text(text, encoding='utf-8')
    shutil.copyfile(ROOT / 'release_assets' / 'school_reports.js', ROOT / 'static' / 'school_reports.js')
    html_path = ROOT / 'static' / 'app.html'
    html = html_path.read_text(encoding='utf-8')
    if '/static/school_reports.js' not in html:
        html = patch(html, '<script src="/static/motor_profiles.js?v=3.9.0" defer></script>',
                     '<script src="/static/motor_profiles.js?v=3.9.0" defer></script><script src="/static/school_reports.js?v=3.10.0" defer></script>', 'script tag')
        html_path.write_text(html, encoding='utf-8')
    install_css()
    print('MEUCRONOGRAMA_V3100_SCHOOL_REPORTS_READY: attention list, item analysis, topic matrix, essay competencies, profiles by class.', flush=True)



def install_css():
    shutil.copyfile(ROOT / 'release_assets' / 'qi_extras.css', ROOT / 'static' / 'qi_extras.css')
    webapp = ROOT / 'webapp.py'
    text = webapp.read_text(encoding='utf-8')
    if "'qi_extras.css'" not in text:
        text = patch(text, "'school_reports.js':'application/javascript; charset=utf-8',",
                     "'school_reports.js':'application/javascript; charset=utf-8','qi_extras.css':'text/css; charset=utf-8',", 'css allowlist')
        webapp.write_text(text, encoding='utf-8')
    html_path = ROOT / 'static' / 'app.html'
    html = html_path.read_text(encoding='utf-8')
    if '/static/qi_extras.css' not in html:
        html = patch(html, '</head>', '<link rel="stylesheet" href="/static/qi_extras.css?v=3.10.0"></head>', 'css link')
        html_path.write_text(html, encoding='utf-8')



if __name__ == '__main__':
    main()
