"""Teste descartável no banco configurado para o fluxo MODELO DADOS."""
import base64
import hashlib
import os
import secrets

from webapp import App
import model_data as M
import templates_v23 as T
import unified as U
import exams as E
from verify_release import require


def main():
    app = App(); app.db.initialize(app.owner, app.env.get('MASTER_PASSWORD', ''), app.env.get('MAYRA_INITIAL_PASSWORD', ''))
    login = 'modelo_' + secrets.token_hex(6); password = secrets.token_urlsafe(24)
    title = 'Verificação modelo ' + secrets.token_hex(5); date = '2026-11-04'; color = 'AZUL'
    user_id = None; exam_ids = []; perf_ids = []
    try:
        with app.db.connection(write=True) as c:
            owner = dict(app.db.execute(c, 'SELECT * FROM hmay_users WHERE username=?', (app.owner,)).fetchone())
            user_id = app.db.create_user(c, login, 'Aluno técnico modelo', password, 'aluno', False)
            students = [['Aluno técnico modelo', login, 'Teste', title, date, color, 'Inglês', 'A', 'C', '', 'A']]
            maps = []
            english_keys = ['A', 'B', 'D', 'ANULADA']
            spanish_keys = ['E', 'D', 'C', 'ANULADA']
            for question in range(1, 5):
                maps.append([title, date, color, question, 'LC', 'Inglês', 'Leitura', 'Texto', 'H01', 'Inglês', english_keys[question - 1]])
                maps.append([title, date, color, question, 'LC', 'Espanhol', 'Leitura', 'Texto', 'H02', 'Espanhol', spanish_keys[question - 1]])
            blob, _ = T.export(['Nome do aluno','LOGIN','Turma','nome do simulado','data de aplicação','Cor da prova','L. Estrangeira',1,2,3,4], students, first_name=M.STUDENTS_SHEET,
                               extra_sheets=[(M.EXAM_SHEET,['nome do simulado','data de aplicação','Cor da prova','QUESTÃO','ÁREA','DISCIPLINA','TÓPICO','ASSUNTO','HABILIDADE','LÍNGUA ESTRANGEIRA','GABARITO'],maps)])
            data = {'filename':'modelo.xlsx','file':base64.b64encode(blob).decode(),'date':date,'mapping':{},'replace':False,'replaceMap':False}
            parsed = M._parse(data, True); data['mapping'] = {parsed['students'][0]['key']: user_id}
            package = M.prepare(app, c, owner, data)
            require(package['prepared'][0]['metrics']['questao:001']['correct'] == 1, 'Alternative A should match answer A.')
            require(package['prepared'][0]['metrics']['questao:002']['correct'] == 0, 'Alternative C should differ from answer B.')
            require(package['prepared'][0]['metrics']['questao:003']['correct'] == 0, 'Blank response should be an error when the question has a valid answer.')
            require(package['prepared'][0]['metrics']['questao:004']['correct'] is None and package['prepared'][0]['metrics']['questao:004']['total'] is None, 'Annulled question must not generate a correct answer or an error.')
            class Conflict(Exception):
                pass
            M.confirm(app, c, owner, package, Conflict)
            row = app.db.execute(c, 'SELECT * FROM hmay_performance WHERE user_id=?', (user_id,)).fetchone()
            require(row is not None, 'Converted result was not persisted.')
            perf_ids.append(row['id'])
            import json
            metadata = json.loads(row['metadata']); metrics = json.loads(row['metrics'])
            exam_ids.append(metadata['_exam_id']); exam = E.get_exam(app, c, metadata['_exam_id'])
            analysis = U.analyse(exam, metrics, metadata)
            require(analysis['overall']['correct'] == 1 and analysis['overall']['errors'] == 2, 'Detailed analysis mismatch.')
    finally:
        if user_id:
            with app.db.connection(write=True) as c:
                app.db.execute(c, 'DELETE FROM hmay_adjustments WHERE actor_id=? OR target_id=?', (user_id, user_id))
                app.db.execute(c, 'DELETE FROM hmay_adaptive_observations WHERE user_id=?', (user_id,))
                app.db.execute(c, 'DELETE FROM hmay_adaptive_consent WHERE user_id=?', (user_id,))
                app.db.execute(c, 'DELETE FROM hmay_proposals WHERE actor_id=? OR target_id=?', (user_id, user_id))
                app.db.execute(c, 'DELETE FROM hmay_events WHERE actor_id=? OR target_id=?', (user_id, user_id))
                app.db.execute(c, 'DELETE FROM hmay_sessions WHERE user_id=?', (user_id,))
                app.db.execute(c, 'DELETE FROM hmay_performance WHERE user_id=?', (user_id,))
                for exam_id in exam_ids:
                    app.db.execute(c, 'DELETE FROM hmay_exams WHERE id=?', (exam_id,))
                app.db.execute(c, 'DELETE FROM hmay_state WHERE user_id=?', (user_id,))
                app.db.execute(c, 'DELETE FROM hmay_users WHERE id=?', (user_id,))
                app.db.execute(c, 'DELETE FROM hmay_attempts WHERE key=?', ('user:' + hashlib.sha256(login.encode()).hexdigest(),))
    print('MEUCRONOGRAMA_V27_CHECK_OK: correct/different/blank/annulled rules, A-E conversion, persistence and detailed analysis passed.', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('MEUCRONOGRAMA_V27_CHECK_FAILED: ' + type(exc).__name__ + '. Credentials omitted.', flush=True)
        raise SystemExit(1)
