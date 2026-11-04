"""Production verification for the collective converted-result export."""
import base64
import hashlib
import io
import json
import os
import secrets

from webapp import App
import model_data as M
import selective as S


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def encoded(blob):
    return base64.b64encode(blob).decode('ascii')


def static_request(app, host, path):
    result = {}
    env = {
        'REQUEST_METHOD': 'GET', 'PATH_INFO': path, 'QUERY_STRING': '',
        'HTTP_HOST': host, 'wsgi.input': io.BytesIO(b''),
        'wsgi.url_scheme': 'https', 'CONTENT_LENGTH': '0',
        'REMOTE_ADDR': '127.0.0.1',
    }
    def start(status, headers):
        result['status'] = int(status.split()[0])
        result['headers'] = dict(headers)
    result['body'] = b''.join(app(env, start))
    return result


def main():
    app = App()
    require(app.db.configured, 'DATABASE_URL is required.')
    host = os.getenv('RENDER_EXTERNAL_HOSTNAME') or sorted(app.hosts)[0]
    app.db.initialize(app.owner, app.env.get('MASTER_PASSWORD', ''), app.env.get('MAYRA_INITIAL_PASSWORD', ''))

    asset = static_request(app, host, '/static/result_export.js')
    require(asset['status'] == 200, 'Result-export JavaScript must be served with HTTP 200.')
    require(b'Exportar resultados convertidos' in asset['body'], 'Result-export interface is incomplete.')

    token = secrets.token_hex(8)
    login_user = 'export_aluno_' + token
    login_special = 'export_especial_' + token
    activity = 'Simulado técnico de exportação ' + token
    activity_key = 'simulado_tecnico_exportacao_' + token
    applied_on = '2099-12-31'
    exam_id = 'rx_exam_' + token
    performance_user = 'rx_perf_user_' + token
    performance_special = 'rx_perf_special_' + token
    student_id = special_id = None
    try:
        with app.db.connection(write=True) as conn:
            owner = app.db.execute(conn, 'SELECT id FROM hmay_users WHERE username=?', (app.owner,)).fetchone()
            require(owner, 'Master account is required.')
            student_id = app.db.create_user(conn, login_user, 'Aluno Exportação ' + token, secrets.token_urlsafe(24), must_change=False)
            special_id = app.db.create_user(conn, login_special, 'Especial Exportação ' + token, secrets.token_urlsafe(24), must_change=False)
            app.db.execute(conn, "UPDATE hmay_users SET role='special' WHERE id=?", (special_id,))

            items = [
                {'number': 1, 'area': 'LC', 'discipline': 'Inglês', 'topic': 'Leitura', 'subject': 'Texto', 'skill': 'H01', 'language': 'Inglês', 'answer': 'A'},
                {'number': 1, 'area': 'LC', 'discipline': 'Espanhol', 'topic': 'Leitura', 'subject': 'Texto', 'skill': 'H02', 'language': 'Espanhol', 'answer': 'B'},
                {'number': 6, 'area': 'LC', 'discipline': 'Português', 'topic': 'Interpretação', 'subject': 'Gênero textual', 'skill': 'H03', 'language': '', 'answer': 'C'},
                {'number': 46, 'area': 'CH', 'discipline': 'História', 'topic': 'Brasil República', 'subject': 'Cidadania', 'skill': 'H05', 'language': '', 'answer': 'D'},
            ]
            now = '2099-12-31T12:00:00+00:00'
            app.db.execute(
                conn,
                'INSERT INTO hmay_exams(id,identity_key,owner_id,title,applied_on,color,area,items,version,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)',
                (exam_id, 'rx_identity_' + token, owner['id'], activity, applied_on, 'AZUL', '', json.dumps(items, ensure_ascii=False), 1, now),
            )
            metrics = {
                'questao:001': {'name': 'Questão 01', 'correct': 1, 'total': 1},
                'questao:006': {'name': 'Questão 06', 'correct': 0, 'total': 1},
                'questao:046': {'name': 'Questão 46', 'correct': 1, 'total': 1},
            }
            metadata = {
                'COR DA PROVA': 'AZUL', 'L.E': 'Inglês', 'TURMA': 'TESTE',
                '_exam_id': exam_id, '_exam_version': 1,
                'Respostas convertidas automaticamente': 'A–E comparadas ao gabarito',
            }
            for perf_id, user_id in ((performance_user, student_id), (performance_special, special_id)):
                app.db.execute(
                    conn,
                    'INSERT INTO hmay_performance(id,user_id,activity_key,activity,applied_on,metrics,metadata,version,updated_at) VALUES (?,?,?,?,?,?,?,?,?)',
                    (perf_id, user_id, activity_key, activity, applied_on,
                     json.dumps(metrics, ensure_ascii=False), json.dumps(metadata, ensure_ascii=False), 1, now),
                )

            manager = {'id': owner['id'], 'role': 'coordenador'}
            simulations = M.result_export_simulations(app, conn, manager)
            selected = [x for x in simulations if x['activityKey'] == activity_key and x['date'] == applied_on]
            require(len(selected) == 1, 'Imported simulation must appear once in the export list.')
            require(selected[0]['participants'] == 1, 'Special profiles must not appear in collective student export.')

            blob, _ = M.result_export_workbook(app, conn, manager, activity_key, applied_on)
            workbook = {'filename': 'Resultados_convertidos.xlsx', 'file': encoded(blob)}
            _, _, sheets, _, _ = S.matrix(workbook)
            expected = ['Resumo dos alunos', 'Por área', 'Por disciplina', 'Por tópico', 'Por assunto', 'Por habilidade']
            require(sheets == expected, 'Collective export workbook sheets are incomplete or out of order.')

            summary, _, _, _, _ = S.matrix({**workbook, 'sheet': 'Resumo dos alunos'})
            require(len(summary) == 2, 'Only the regular student must appear in the summary.')
            require(summary[1][0] == 'Aluno Exportação ' + token, 'Student name missing from summary.')
            require(int(summary[1][7]) == 2 and int(summary[1][8]) == 1, 'Converted correct/error totals are incorrect.')
            require(int(summary[1][10]) == 3, 'Valid-question denominator is incorrect.')

            skill_rows, _, _, _, _ = S.matrix({**workbook, 'sheet': 'Por habilidade'})
            labels = {str(row[3]) for row in skill_rows[1:] if len(row) > 3}
            require('Linguagens · H01' in labels, 'Language skill must remain scoped to Linguagens.')
            require('Humanas · H05' in labels, 'Humanities skill must remain scoped to Humanas.')
            all_values = []
            for sheet in sheets:
                matrix, _, _, _, _ = S.matrix({**workbook, 'sheet': sheet})
                all_values.extend(str(value) for row in matrix for value in row)
            require('Especial Exportação ' + token not in all_values, 'Special profile leaked into collective export.')
    finally:
        if student_id or special_id or exam_id:
            with app.db.connection(write=True) as conn:
                for user_id in (student_id, special_id):
                    if not user_id:
                        continue
                    app.db.execute(conn, 'DELETE FROM hmay_performance WHERE user_id=?', (user_id,))
                    app.db.execute(conn, 'DELETE FROM hmay_events WHERE actor_id=? OR target_id=?', (user_id, user_id))
                    app.db.execute(conn, 'DELETE FROM hmay_sessions WHERE user_id=?', (user_id,))
                    app.db.execute(conn, 'DELETE FROM hmay_state WHERE user_id=?', (user_id,))
                    app.db.execute(conn, 'DELETE FROM hmay_users WHERE id=?', (user_id,))
                app.db.execute(conn, 'DELETE FROM hmay_exams WHERE id=?', (exam_id,))
                for login in (login_user, login_special):
                    key = 'user:' + hashlib.sha256(login.encode()).hexdigest()
                    app.db.execute(conn, 'DELETE FROM hmay_attempts WHERE key=?', (key,))

    print('MEUCRONOGRAMA_RESULT_EXPORT_CHECK_OK: list, privacy, converted totals and six-sheet XLSX passed.', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('MEUCRONOGRAMA_RESULT_EXPORT_CHECK_FAILED: ' + type(exc).__name__ + '. Credentials omitted.', flush=True)
        raise
