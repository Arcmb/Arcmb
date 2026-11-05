from pathlib import Path
import tempfile

from webapp import App, bulk_create_student_accounts


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = str(Path(tmp) / 'bulk_students.sqlite3')
        app = App({
            'LOCAL_TEST': '1',
            'LOCAL_DB': db_path,
            'MASTER_USERNAME': 'arcmb',
            'MASTER_PASSWORD': 'MasterTest991!',
            'SECRET_KEY': 'x' * 48,
            'ALLOWED_HOSTS': 'testserver',
        })
        app.db.initialize(app.owner, 'MasterTest991!', '')
        students = [
            {'name': 'Ana Carolina Teste', 'login': ''},
            {'name': 'Bruno de Souza Teste', 'login': 'bruno.teste'},
            {'name': ' ANA  CAROLINA TESTE ', 'login': ''},
        ]
        with app.db.connection(write=True) as c:
            owner = dict(app.db.execute(c, 'SELECT * FROM hmay_users WHERE username=?', ('arcmb',)).fetchone())
            result = bulk_create_student_accounts(app, c, owner, students, 'Temporaria991!')
            require(result['summary']['created'] == 2, 'Two unique student accounts should be created.')
            require(result['summary']['duplicateRows'] == 1, 'Repeated normalized name should be ignored.')
            require(result['summary']['conflicts'] == 0, 'The test batch should have no conflicts.')
            created_logins = {item['username'] for item in result['created']}
            require('bruno.teste' in created_logins, 'Provided login should be preserved.')
            generated = [item for item in result['created'] if item['name'] == 'Ana Carolina Teste'][0]
            require(generated['generatedLogin'] is True and generated['username'].startswith('ana.teste'), 'Blank login should be generated from the name.')
            rows = app.db.execute(c, "SELECT username,role,active,must_change,password FROM hmay_users WHERE name IN (?,?) ORDER BY name", ('Ana Carolina Teste','Bruno de Souza Teste')).fetchall()
            require(len(rows) == 2, 'Created students should exist in the database.')
            require(all(row['role'] == 'aluno' for row in rows), 'Batch-created accounts must have the Aluno role.')
            require(all(row['active'] == 1 and row['must_change'] == 1 for row in rows), 'Accounts must be active and require a password change.')
            require(all(row['password'] != 'Temporaria991!' for row in rows), 'Passwords must be stored as hashes.')
            state_count = app.db.execute(c, "SELECT COUNT(*) AS n FROM hmay_state s JOIN hmay_users u ON u.id=s.user_id WHERE u.name IN (?,?)", ('Ana Carolina Teste','Bruno de Souza Teste')).fetchone()['n']
            require(state_count == 2, 'Each account must receive an internal profile.')
            second = bulk_create_student_accounts(app, c, owner, students, 'OutraSenha991!')
            require(second['summary']['created'] == 0 and second['summary']['existing'] == 2, 'Reimporting the same names must not create duplicates.')
            try:
                bulk_create_student_accounts(app, c, {'role': 'especial'}, students, 'Temporaria991!')
            except PermissionError:
                pass
            else:
                raise AssertionError('Special profiles must not create batch accounts.')

    js = (Path(__file__).resolve().parent / 'static' / 'result_import.js').read_text(encoding='utf-8')
    for marker in [
        'Cadastrar contas ausentes em lote',
        "acts['result-import-bulk-create']",
        "acts['result-import-bulk-download']",
        '/api/accounts/bulk-from-results',
        'Senha provisória comum para os novos alunos',
    ]:
        require(marker in js, f'Missing bulk-account UI marker: {marker}')
    html = (Path(__file__).resolve().parent / 'static' / 'app.html').read_text(encoding='utf-8')
    require('/static/result_import.js?v=2.8.5' in html, 'Bulk importer cache key is missing.')
    print('MEUCRONOGRAMA_BULK_STUDENT_ACCOUNTS_CHECK_OK: batch creation, generated logins, duplicate protection, roles, password change and UI passed.', flush=True)


if __name__ == '__main__':
    main()
