"""v3.12.0: cadastro de disciplinas oficiais com variações; a importação grava o nome oficial."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
MARK = '# === DISCIPLINES CATALOG V3.12.0 ==='
CANON = 'import disciplines_catalog as _DC;_DC.canon_items(app,c,{items})  ' + MARK


def patch(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: esperado 1 trecho, encontrado {count}.')
    return text.replace(old, new, 1)


def edit(name, pairs):
    path = ROOT / name
    text = path.read_text(encoding='utf-8')
    if MARK in text:
        return
    for old, new, label in pairs:
        text = patch(text, old, new, name + ' ' + label)
    path.write_text(text, encoding='utf-8')


def main():
    edit('webapp.py', [
        ("import school_reports as SCHOOL_REPORTS", "import disciplines_catalog as DISCIPLINES  " + MARK + "\nimport school_reports as SCHOOL_REPORTS", 'import'),
        ("            if path.startswith('/api/school-reports/'):\n",
         "            if path.startswith('/api/disciplines/'):\n"
         "                return DISCIPLINES.handle(self,c,user,path,method,data,query,start,HTTPError)\n"
         "            if path.startswith('/api/school-reports/'):\n", 'route'),
        ("'school_reports.js':'application/javascript; charset=utf-8',",
         "'school_reports.js':'application/javascript; charset=utf-8','disciplines_catalog.js':'application/javascript; charset=utf-8',", 'allowlist'),
    ])
    # Mapa de questões (aba Mapa de questões)
    edit('exams.py', [(" at=P.now().isoformat()\n if result['id']:\n",
                       " at=P.now().isoformat()\n " + CANON.format(items="result['items']") + "\n if result['id']:\n", 'canon')])
    # Importação unificada (planilha com alunos e mapa)
    edit('unified.py', [("    at=P.now().isoformat();exam=p['exam'];old=p['old'];db=app.db\n    if p['mapChanged']:\n",
                         "    at=P.now().isoformat();exam=p['exam'];old=p['old'];db=app.db\n    if p['mapChanged']:\n        " + CANON.format(items="exam['items']") + "\n", 'canon')])
    # Importação de resultados com mapa
    edit('model_data.py', [("    for pack in package['exams'].values():\n        exam, old = pack['result'], pack['old']\n",
                            "    for pack in package['exams'].values():\n        exam, old = pack['result'], pack['old']\n        " + CANON.format(items="exam['items']") + "\n", 'canon')])
    shutil.copyfile(ROOT / 'release_assets' / 'disciplines_catalog.js', ROOT / 'static' / 'disciplines_catalog.js')
    html_path = ROOT / 'static' / 'app.html'
    html = html_path.read_text(encoding='utf-8')
    if '/static/disciplines_catalog.js' not in html:
        html = patch(html, '<script src="/static/school_reports.js?v=3.11.0" defer></script>',
                     '<script src="/static/school_reports.js?v=3.11.0" defer></script><script src="/static/disciplines_catalog.js?v=3.12.0" defer></script>', 'script tag')
        html = patch(html, 'qi_extras.css?v=3.11.0', 'qi_extras.css?v=3.12.0', 'css cache')
        html_path.write_text(html, encoding='utf-8')
    print('MEUCRONOGRAMA_V3120_DISCIPLINES_READY: official discipline names applied on every exam-map import.', flush=True)


if __name__ == '__main__':
    main()
