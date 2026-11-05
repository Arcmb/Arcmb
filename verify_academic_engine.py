"""Production verification for bounded academic priorities in the planner."""
import copy
import hashlib
import json
import secrets

from webapp import App
import adaptive as A
import planner as P


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def study_subject(identifier, name, weekly=200):
    return {
        'id': identifier, 'name': name, 'kind': 'study',
        'action': 'Estudar e praticar', 'weeklyMin': weekly,
        'difficulty': 3, 'importance': 3, 'examDate': '', 'active': True,
    }


def main():
    app = App()
    require(app.db.configured, 'DATABASE_URL is required.')
    app.db.initialize(app.owner, app.env.get('MASTER_PASSWORD', ''), app.env.get('MAYRA_INITIAL_PASSWORD', ''))

    token = secrets.token_hex(8)
    login = 'academic_engine_' + token
    user_id = None
    exam_id = 'academic_exam_' + token
    performance_id = 'academic_perf_' + token
    applied_on = P.today()
    try:
        with app.db.connection(write=True) as conn:
            owner = app.db.execute(conn, 'SELECT id FROM hmay_users WHERE username=?', (app.owner,)).fetchone()
            require(owner, 'Master account is required.')
            user_id = app.db.create_user(conn, login, 'Aluno Motor Acadêmico ' + token, secrets.token_urlsafe(24), must_change=False)
            app.db.execute(conn, "UPDATE hmay_users SET role='aluno' WHERE id=?", (user_id,))

            items = []
            metrics = {}
            for number in range(1, 11):
                items.append({'number': number, 'area': 'MT', 'discipline': 'Matemática', 'topic': 'Teste', 'subject': 'Teste', 'skill': 'H01', 'language': '', 'answer': 'A'})
                metrics[f'questao:{number:03d}'] = {'name': f'Questão {number:02d}', 'correct': 0, 'total': 1}
            for number in range(11, 21):
                items.append({'number': number, 'area': 'LC', 'discipline': 'Português', 'topic': 'Teste', 'subject': 'Teste', 'skill': 'H01', 'language': '', 'answer': 'B'})
                metrics[f'questao:{number:03d}'] = {'name': f'Questão {number:02d}', 'correct': 1, 'total': 1}
            stamp = P.now().isoformat()
            app.db.execute(
                conn,
                'INSERT INTO hmay_exams(id,identity_key,owner_id,title,applied_on,color,area,items,version,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)',
                (exam_id, 'academic_identity_' + token, owner['id'], 'Teste motor acadêmico', applied_on, 'AZUL', '', json.dumps(items, ensure_ascii=False), 1, stamp),
            )
            metadata = {'COR DA PROVA': 'AZUL', 'L.E': 'Inglês', 'TURMA': 'TESTE', '_exam_id': exam_id, '_exam_version': 1}
            app.db.execute(
                conn,
                'INSERT INTO hmay_performance(id,user_id,activity_key,activity,applied_on,metrics,metadata,version,updated_at) VALUES (?,?,?,?,?,?,?,?,?)',
                (performance_id, user_id, 'academic_activity_' + token, 'Teste motor acadêmico', applied_on, json.dumps(metrics, ensure_ascii=False), json.dumps(metadata, ensure_ascii=False), 1, stamp),
            )

            profile = P.default_profile('Aluno Motor Acadêmico ' + token, user_id)
            profile['subjects'] = [study_subject('sub-math', 'Matemática'), study_subject('sub-port', 'Português')]
            academic = A.academic_priority(app, conn, user_id, profile)
            require(academic['used'], 'Low academic performance must produce a bounded priority.')
            require(1.0 < academic['bonuses'].get('sub-math', 1.0) <= 1.25, 'Mathematics priority is outside the allowed bound.')
            require(academic['bonuses'].get('sub-port', 1.0) == 1.0, 'High-performing Portuguese must not receive a weakness bonus.')
            math_row = next((row for row in academic['subjects'] if row['subjectId'] == 'sub-math'), None)
            require(math_row and math_row['questions'] == 10 and math_row['correct'] == 0, 'Mathematics evidence was not classified correctly.')

            planner_profile = P.default_profile('Teste de distribuição', 'academic-planner')
            planner_profile['settings'].update({'weeklyGoal': 400, 'dailyMax': 240, 'reservePct': 0, 'sessionMin': 20, 'sessionMax': 50, 'breakMin': 10})
            for availability in planner_profile['availability']:
                availability['status'] = 'available'
                availability['ranges'] = [{'start': '08:00', 'end': '20:00'}]
            planner_profile['subjects'] = [study_subject('sub-math', 'Matemática'), study_subject('sub-port', 'Português')]
            generated = P.generate(copy.deepcopy(planner_profile), P.add(P.week(P.today()), 7), mode='fill', bonuses={}, subject_bonuses={'sub-math': 1.25})
            math_minutes = sum(session['end'] - session['start'] for session in generated['sessions'] if session['subjectId'] == 'sub-math')
            port_minutes = sum(session['end'] - session['start'] for session in generated['sessions'] if session['subjectId'] == 'sub-port')
            require(math_minutes > port_minutes, 'A bounded academic priority must increase the relative allocation of the weaker discipline.')

            source = (P.__file__ and open(P.__file__, encoding='utf-8').read())
            require('subject_bonuses=None' in source and "subject_bonuses.get(sub['id']" in source, 'Planner source is not wired to subject priorities.')
            adaptive_source = open(A.__file__, encoding='utf-8').read()
            require("academic=academic_priority" in adaptive_source and 'subject_bonuses=academic.get' in adaptive_source, 'Adaptive preview does not pass academic priorities to the planner.')
    finally:
        if user_id:
            with app.db.connection(write=True) as conn:
                app.db.execute(conn, 'DELETE FROM hmay_performance WHERE user_id=?', (user_id,))
                app.db.execute(conn, 'DELETE FROM hmay_events WHERE actor_id=? OR target_id=?', (user_id, user_id))
                app.db.execute(conn, 'DELETE FROM hmay_sessions WHERE user_id=?', (user_id,))
                app.db.execute(conn, 'DELETE FROM hmay_state WHERE user_id=?', (user_id,))
                app.db.execute(conn, 'DELETE FROM hmay_users WHERE id=?', (user_id,))
                app.db.execute(conn, 'DELETE FROM hmay_exams WHERE id=?', (exam_id,))
                key = 'user:' + hashlib.sha256(login.encode()).hexdigest()
                app.db.execute(conn, 'DELETE FROM hmay_attempts WHERE key=?', (key,))

    print('MEUCRONOGRAMA_ACADEMIC_ENGINE_CHECK_OK: imported results affect only bounded subject weights in confirmed previews.', flush=True)


if __name__ == '__main__':
    main()
