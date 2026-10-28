"""Prepare Meu Cronograma from the original, SHA-256-verified source archive.
Only presentation/service names change; existing tables, cookies and backups
remain compatible. No credentials or user data are part of this file.
"""
from pathlib import Path
from unpack_source import unpack

ROOT = Path(__file__).resolve().parent
FILES = ('webapp.py', 'static/app.html', 'static/app.js', 'static/login.html',
         'static/setup.html', 'static/manifest.webmanifest')
REPLACEMENTS = (
    ('Horário da May', 'Meu Cronograma'),
    ('Horario da May', 'Meu Cronograma'),
    ('Horario_da_May', 'Meu_Cronograma'),
    ('horariodamay.onrender.com', 'meucronograma.onrender.com'),
    ("logging.getLogger('horariodamay')", "logging.getLogger('meucronograma')"),
    ("service='horariodamay'", "service='meucronograma'"),
    ('@horariodamay', '@meucronograma'),
)


def prepare():
    # The tracked requirements file is authoritative. The legacy archive contains
    # its original dependency pins and must not restore them during each build.
    requirements_path = ROOT / 'requirements.txt'
    requirements = requirements_path.read_text(encoding='utf-8')
    if not requirements.strip():
        raise RuntimeError('The tracked requirements.txt must not be empty.')
    unpack()
    requirements_path.write_text(requirements, encoding='utf-8')
    for name in FILES:
        path = ROOT / name
        text = path.read_text(encoding='utf-8')
        for before, after in REPLACEMENTS:
            text = text.replace(before, after)
        path.write_text(text, encoding='utf-8')
    path = ROOT / 'webapp.py'
    text = path.read_text(encoding='utf-8')
    text = text.replace("if path=='/healthz':return self.reply(start,200,", "if path=='/healthz':return self.reply(start,200 if configured else 503,")
    anchor = "        self.db.initialize(self.owner,self.env.get('MASTER_PASSWORD',''),self.env.get('MAYRA_INITIAL_PASSWORD',''))\n"
    readiness = """        if path=='/readyz' and method=='GET':
            with self.db.connection() as connection:
                self.db.execute(connection, 'SELECT 1').fetchone()
            return self.reply(start,200,dict(service='meucronograma',ready=True))
"""
    if "if path=='/readyz'" not in text:
        if text.count(anchor) != 1:
            raise RuntimeError('Unexpected application version; readiness patch not applied.')
        text = text.replace(anchor, anchor + readiness)
    path.write_text(text, encoding='utf-8')
    print('Meu Cronograma: branding and readiness prepared; existing data schema preserved.')


if __name__ == '__main__':
    prepare()
