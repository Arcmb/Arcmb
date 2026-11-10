"""Production verification for the student academic home dashboard."""
from pathlib import Path
import hashlib
import json
import os
import secrets

from webapp import App
import model_data as M
import planner as P

ROOT = Path(__file__).resolve().parent


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    js = (ROOT / 'static' / 'student_summary.js').read_text(encoding='utf-8')
    css = (ROOT / 'static' / 'style.css').read_text(encoding='utf-8')
    html = (ROOT / 'static' / 'app.html').read_text(encoding='utf-8')
    model = (ROOT / 'model_data.py').read_text(encoding='utf-8')
    for marker in [
        'TRAJETÓRIA ACADÊMICA NA VISÃO GERAL',
        'Meu desempenho e progresso',
        'Evolução nos simulados',
        'Trilha de aprendizagem',
        'Execução da rotina',
        "view==='performance'||view==='home'",
        'studentHomeOriginalHomeView',
    ]:
        require(marker in js, 'Missing student-home marker: ' + marker)
    require('MEU CRONOGRAMA: TRAJETÓRIA ACADÊMICA NA VISÃO GERAL' in css, 'Student-home CSS is missing.')
    require('/static/student_summary.js?v=3.5.0' in html, 'Student-home cache key is missing.')
    require('# === MEU CRONOGRAMA: TRAJETÓRIA ACADÊMICA NA VISÃO GERAL ===' in model, 'Student-home backend extension is missing.')

    app = App()
    require(app.db.configured, 'DATABASE_URL is required.')
    app.db.initialize(app.owner, app.env.get('MASTER_PASSWORD', ''), app.env.get('MAYRA_INITIAL_PASSWORD', ''))
    token = secrets.token_hex(8)
    login = 'home_student_' + token
    student_id = exam_id = performance_id = None
    try:
        with app.db.connection(write=True) as conn:
            owner = app.db.execute(conn, 'SELECT id FROM hmay_users WHERE username=?', (app.owner,)).fetchone()
            require(owner, 'Master account is required.')
            student_id = app.db.create_user(
                conn, login, 'Aluno Painel ' + token, secrets.token_urlsafe(24),
                role='aluno', must_change=False,
            )
            state = app.db.execute(conn, 'SELECT profile FROM hmay_state WHERE user_id=?', (student_id,)).fetchone()
            profile = json.loads(state['profile'])
            profile['contents'] = [{
                'id': 'content_' + token, 'subjectId': '', 'title': 'Conteúdo técnico',
                'topic': 'Tópico técnico', 'status': 'studied', 'paused': False,
                'studyMinutes': 40, 'reviewMinutes': 20, 'difficulty': 3,
                'studiedOn': '2026-10-01', 'studiedTime': '10:00',
                'nextDue': '2026-10-02', 'stage': 1,
            }]
            profile['sessions'] = [
                {'id': 's1_' + token, 'kind': 'study', 'status': 'done'},
                {'id': 's2_' + token, 'kind': 'review', 'status': 'partial'},
                {'id': 's3_' + token, 'kind': 'review', 'status': 'planned'},
                {'id': 's4_' + token, 'kind': 'action', 'status': 'missed'},
            ]
            profile['feedback'] = [{
                'id': 'f1_' + token, 'actualMin': 35, 'total': 10,
                'correct': 7, 'contentId': 'content_' + token,
            }]
            app.db.execute(
                conn, 'UPDATE hmay_state SET profile=?,version=version+1,updated_at=? WHERE user_id=?',
                (json.dumps(profile, ensure_ascii=False), P.now().isoformat(), student_id),
            )

            exam_id = 'home_exam_' + token
            performance_id = 'home_perf_' + token
            items = [
                {'number': 1, 'area': 'LC', 'discipline': 'Português', 'topic': 'Leitura', 'subject': 'Interpretação', 'skill': 'H01', 'language': '', 'answer': 'A'},
                {'number': 2, 'area': 'LC', 'discipline': 'Português', 'topic': 'Gramática', 'subject': 'Coesão', 'skill': 'H18', 'language': '', 'answer': 'B'},
            ]
            now = P.now().isoformat()
            app.db.execute(
                conn,
                'INSERT INTO hmay_exams(id,identity_key,owner_id,title,applied_on,color,area,items,version,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)',
                (exam_id, 'home_identity_' + token, owner['id'], 'Simulado Painel', '2026-10-25', 'AZUL', '', json.dumps(items, ensure_ascii=False), 1, now),
            )
            metrics = {
                'questao:001': {'name': 'Questão 01', 'correct': 1, 'total': 1},
                'questao:002': {'name': 'Questão 02', 'correct': 0, 'total': 1},
            }
            metadata = {
                'COR DA PROVA': 'AZUL', 'L.E': '', 'TURMA': 'TESTE',
                '_exam_id': exam_id, '_exam_version': 1,
            }
            app.db.execute(
                conn,
                'INSERT INTO hmay_performance(id,user_id,activity_key,activity,applied_on,metrics,metadata,version,updated_at) VALUES (?,?,?,?,?,?,?,?,?)',
                (performance_id, student_id, 'simulado_painel_' + token, 'Simulado Painel', '2026-10-25', json.dumps(metrics), json.dumps(metadata), 1, now),
            )
            target = dict(app.db.execute(conn, 'SELECT id,username,name,role,active FROM hmay_users WHERE id=?', (student_id,)).fetchone())
            summary = M.student_summary(app, conn, {'id': owner['id'], 'role': 'master'}, target)
            require(summary['performance']['simulations'] == 1, 'The first simulation must appear on the student dashboard.')
            require(summary['performance']['correct'] == 1, 'Simulation correct count is wrong.')
            engagement = summary.get('engagement') or {}
            require(engagement.get('activities', {}).get('done') == 1, 'Completed activity count is wrong.')
            require(engagement.get('activities', {}).get('missed') == 1, 'Missed activity count is wrong.')
            require(engagement.get('reviews', {}).get('planned') == 1, 'Planned review count is wrong.')
            require(engagement.get('reviews', {}).get('partial') == 1, 'Partial review count is wrong.')
            require(engagement.get('reviews', {}).get('overdue') == 1, 'Overdue review count is wrong.')
    finally:
        if student_id:
            with app.db.connection(write=True) as conn:
                app.db.execute(conn, 'DELETE FROM hmay_performance WHERE user_id=?', (student_id,))
                if exam_id:
                    app.db.execute(conn, 'DELETE FROM hmay_exams WHERE id=?', (exam_id,))
                app.db.execute(conn, 'DELETE FROM hmay_events WHERE actor_id=? OR target_id=?', (student_id, student_id))
                app.db.execute(conn, 'DELETE FROM hmay_sessions WHERE user_id=?', (student_id,))
                app.db.execute(conn, 'DELETE FROM hmay_state WHERE user_id=?', (student_id,))
                app.db.execute(conn, 'DELETE FROM hmay_users WHERE id=?', (student_id,))
                key = 'user:' + hashlib.sha256(login.encode()).hexdigest()
                app.db.execute(conn, 'DELETE FROM hmay_attempts WHERE key=?', (key,))

    print('MEUCRONOGRAMA_STUDENT_HOME_CHECK_OK: first simulation, evolution data, revisions and activities passed.', flush=True)


if __name__ == '__main__':
    main()
