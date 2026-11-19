"""Edit a registered question booklet and its linked performance records."""
import hashlib
import sqlite3

import exams as E
import performance as F
import planner as P


def can_edit(user):
    return user['role'] in ('master', 'coordenador')


def identity_key(title, date, color):
    return hashlib.sha256(E.enc([F.norm(title), date, F.norm(color)]).encode()).hexdigest()


def find_import_map(app, c, title, date, color):
    # Older date edits changed applied_on without rebuilding identity_key.
    rows = app.db.execute(c, 'SELECT id,title,color FROM hmay_exams WHERE applied_on=?',(date,)).fetchall()
    matches = [r for r in rows if F.norm(r['title']) == F.norm(title) and F.norm(r['color']) == F.norm(color)]
    if len(matches) > 1:
        raise ValueError('Há dois cadernos com o mesmo nome, data e cor. Corrija o cadastro antes de importar.')
    return matches[0] if matches else None


def release_obsolete_key(app, c, key):
    """Free an old date key only if a write actually needs it."""
    lock = '' if app.db.local_path else ' FOR UPDATE'
    moves = {}
    while key not in moves:
        row = app.db.execute(c, 'SELECT id,title,applied_on,color FROM hmay_exams WHERE identity_key=?'+lock,
                             (key,)).fetchone()
        if not row:
            break
        actual = identity_key(row['title'], row['applied_on'], row['color'])
        if key == actual:
            if moves:
                raise ValueError('Existem mapas com a mesma identificação. Confira os cadernos cadastrados.')
            return
        moves[key] = (row['id'], actual)
        key = actual
    # Temporary keys also handle old keys that point at each other.
    for row_id, _ in moves.values():
        app.db.execute(c,'UPDATE hmay_exams SET identity_key=? WHERE id=?',('repair:'+row_id,row_id))
    for row_id, actual in moves.values():
        app.db.execute(c,'UPDATE hmay_exams SET identity_key=? WHERE id=?',(actual,row_id))


def available_import_id(app, c, base):
    """Keep preview IDs repeatable, including when an older map has been renamed."""
    candidate = base
    suffix = 0
    while app.db.execute(c, 'SELECT 1 FROM hmay_exams WHERE id=?', (candidate,)).fetchone():
        suffix += 1
        candidate = f'{base}_{suffix}'
    return candidate


def exam_link(app, column):
    if app.db.local_path:
        return f"json_extract({column}, '$._exam_id')"
    return f"({column}::jsonb ->> '_exam_id')"


def catalogue(app, c, user):
    link = exam_link(app, 'metadata')
    rows = app.db.execute(c, f"""
        SELECT e.id, e.title, e.applied_on, e.color, e.area, e.version,
               COALESCE(p.results, 0) AS results
        FROM hmay_exams e LEFT JOIN (
            SELECT {link} AS exam_id, COUNT(*) AS results FROM hmay_performance GROUP BY 1
        ) p ON p.exam_id=e.id
        ORDER BY e.applied_on DESC, e.title, e.color
    """).fetchall()
    return [dict(id=row['id'], title=row['title'], date=row['applied_on'],
                 applied_on=row['applied_on'], color=row['color'], area=row['area'],
                 version=row['version'], linkedResults=row['results'],
                 canEdit=can_edit(user)) for row in rows]


def _update_results(app, c, exam, title, date, color, stamp):
    if (title, date, color) == (exam['title'], exam['applied_on'], exam['color']):
        return 0
    key = F.norm(title)
    link = exam_link(app, 'p.metadata')
    duplicate = app.db.execute(c, f"""
        SELECT 1 FROM hmay_performance p JOIN hmay_performance other
          ON other.user_id=p.user_id AND other.id<>p.id
        WHERE {link}=? AND other.activity_key=? AND other.applied_on=? LIMIT 1
    """, (exam['id'], key, date)).fetchone()
    if duplicate:
        raise ValueError('A alteração criaria um resultado duplicado para o mesmo aluno e aplicação.')
    assignments = ['activity=?', 'activity_key=?', 'applied_on=?', 'updated_at=?', 'version=version+1']
    args = [title, key, date, stamp]
    if color != exam['color']:
        expression = ("json_set(metadata, '$.\"COR DA PROVA\"', ?)" if app.db.local_path else
                      "jsonb_set(metadata::jsonb, '{COR DA PROVA}', to_jsonb(CAST(? AS text)))::text")
        assignments.append('metadata='+expression)
        args.append(color)
    args.append(exam['id'])
    link = exam_link(app, 'metadata')
    return app.db.execute(c, f"UPDATE hmay_performance SET {', '.join(assignments)} WHERE {link}=?", tuple(args)).rowcount


def update(app, c, user, data, HTTPError, date_only=False):
    if not can_edit(user):
        raise HTTPError(403, 'A edição dos mapas é exclusiva do Master e da coordenação.')
    exam_id = F.text(data.get('examId'), 160)
    lock = '' if app.db.local_path else ' FOR UPDATE'
    row = app.db.execute(c, 'SELECT id, title, applied_on, color, area, version, identity_key '
                         'FROM hmay_exams WHERE id=?'+lock, (exam_id,)).fetchone()
    if not row:
        raise HTTPError(404, 'Este caderno não foi encontrado.')
    exam = dict(row)
    if not date_only and (type(data.get('version')) is not int or data['version'] != exam['version']):
        raise HTTPError(409, 'Este caderno foi alterado. Feche a edição e abra novamente para conferir os dados atuais.')
    date = F.date_value(data.get('date'))
    if date_only:
        title, color, area = exam['title'], exam['color'], exam['area']
    else:
        if any(key not in data for key in ('title','color','area')):
            raise ValueError('Confira o nome do simulado, a cor e a área padrão.')
        title = F.text(data['title'], 200)
        color = F.text(data['color'], 80)
        area = E.area(F.text(data['area'], 80))
        if not title or not color:
            raise ValueError('Informe o nome do simulado e a cor. Para caderno sem cor, use Única.')
        if area not in ('', 'LC', 'CH', 'CN', 'MT'):
            raise ValueError('Escolha uma área válida ou deixe sem área padrão.')
    identity = identity_key(title, date, color)
    changed = (title,date,color,area,identity) != (exam['title'],exam['applied_on'],exam['color'],exam['area'],exam['identity_key'])
    result = dict(examId=exam_id, title=title, color=color, area=area, oldDate=exam['applied_on'],
                  newDate=date, updatedResults=0, version=exam['version'], unchanged=not changed)
    if not changed:
        return result
    # Also recognise records whose identity key was left stale by the former date editor.
    others = app.db.execute(c, 'SELECT title,color FROM hmay_exams WHERE id<>? AND applied_on=?',
                            (exam_id,date)).fetchall()
    if any(F.norm(r['title']) == F.norm(title) and F.norm(r['color']) == F.norm(color) for r in others):
        raise HTTPError(409, 'Já existe outro caderno com esse nome, data e cor.')
    stamp = P.now().isoformat()
    try:
        release_obsolete_key(app, c, identity)
        app.db.execute(c, '''UPDATE hmay_exams SET title=?, applied_on=?, color=?, area=?, identity_key=?,
                          version=version+1, updated_at=? WHERE id=?''',
                       (title,date,color,area,identity,stamp,exam_id))
        result['updatedResults'] = _update_results(app,c,exam,title,date,color,stamp)
    except Exception as exc:
        if getattr(exc, 'sqlstate', None) == '23505' or isinstance(exc, sqlite3.IntegrityError) and 'UNIQUE' in str(exc):
            raise HTTPError(409, 'Já existe um caderno ou resultado com esses dados. Confira a identificação.') from exc
        raise
    result['version'] += 1
    app.event(c,user,user['id'],'exam_date_update' if date_only else 'exam_metadata_update')
    return result


# ---------------------------------------------------------------- exclusão (v3.15.0)
# Permite desfazer um envio errado: as notas (TRI, redação e ranking), as respostas dos
# alunos e o gabarito/mapa de um caderno ou de um simulado inteiro (todas as cores).
# Tudo acontece numa única transação: ou sai tudo o que foi marcado, ou nada.

import json as _json

DELETE_CONFIRMATION = 'EXCLUIR'


def _score_key(key):
    """Campos gravados pela importação de notas (planilha de TRI, redação e ranking)."""
    return key == '_ranking' or key.startswith('_tri_') or key.startswith('_redaction_')


def _load(value, fallback):
    try:
        out = _json.loads(value or '')
    except (TypeError, ValueError):
        return fallback
    return out if isinstance(out, type(fallback)) else fallback


def _deletion_scope(app, c, exam_id, whole, HTTPError, lock=False):
    suffix = '' if app.db.local_path or not lock else ' FOR UPDATE'
    row = app.db.execute(c, 'SELECT id,title,applied_on,color,version FROM hmay_exams WHERE id=?' + suffix,
                         (exam_id,)).fetchone()
    if not row:
        raise HTTPError(404, 'Este caderno não foi encontrado. Atualize a lista.')
    exam = dict(row)
    siblings = [dict(r) for r in app.db.execute(
        c, 'SELECT id,title,applied_on,color,version FROM hmay_exams WHERE applied_on=? ORDER BY color' + suffix,
        (exam['applied_on'],)).fetchall() if F.norm(r['title']) == F.norm(exam['title'])]
    exams = siblings if whole else [exam]
    ids = [x['id'] for x in exams]
    link = exam_link(app, 'metadata')
    marks = ','.join('?' for _ in ids)
    found = {}
    for r in app.db.execute(c, f'SELECT id,user_id,activity_key,activity,applied_on,metadata FROM hmay_performance '
                               f'WHERE {link} IN ({marks})', tuple(ids)).fetchall():
        found[r['id']] = dict(r)
    if whole:
        # Resultados do mesmo simulado sem vínculo com um caderno (importações antigas).
        for r in app.db.execute(c, 'SELECT id,user_id,activity_key,activity,applied_on,metadata FROM hmay_performance '
                                   'WHERE activity_key=? AND applied_on=?',
                                (F.norm(exam['title']), exam['applied_on'])).fetchall():
            found.setdefault(r['id'], dict(r))
    rows = sorted(found.values(), key=lambda r: r['id'])
    for r in rows:
        r['metadata'] = _load(r['metadata'], {})
    return exam, siblings, exams, rows


def _counts(exams, rows):
    return dict(exams=len(exams), results=len(rows), students=len({r['user_id'] for r in rows}),
                withScores=sum(1 for r in rows if any(_score_key(k) for k in r['metadata'])))


def delete_preview(app, c, user, data, HTTPError):
    if not can_edit(user):
        raise HTTPError(403, 'A exclusão de simulados é exclusiva do Master e da coordenação.')
    exam_id = F.text(data.get('examId'), 160)
    exam, siblings, _, _ = _deletion_scope(app, c, exam_id, False, HTTPError)
    scopes = {}
    for name, whole in (('caderno', False), ('simulado', True)):
        _, _, exams, rows = _deletion_scope(app, c, exam_id, whole, HTTPError)
        scopes[name] = dict(_counts(exams, rows), colors=[x['color'] for x in exams])
    return dict(examId=exam['id'], title=exam['title'], date=exam['applied_on'], color=exam['color'],
                colors=[x['color'] for x in siblings], scopes=scopes, confirmation=DELETE_CONFIRMATION)


def _remove_exam_reviews(app, c, removed):
    """Tira do cronograma dos alunos as revisões geradas pelos erros dos resultados excluídos.

    removed: {user_id: {(simulado, data), ...}}. Um conteúdo que fica sem erros é excluído
    junto com as revisões ainda não feitas; se o aluno já tiver histórico nele (sessões feitas,
    verificações ou registros de estudo), ele é pausado em vez de excluído — mesma regra da
    exclusão manual de conteúdos.
    """
    today = str(P.today())
    users = sorted(removed)
    touched = paused = deleted = 0
    lock = '' if app.db.local_path else ' FOR UPDATE'
    for start in range(0, len(users), 40):
        chunk = users[start:start + 40]
        marks = ','.join('?' for _ in chunk)
        rows = app.db.execute(c, f"SELECT user_id,profile FROM hmay_state WHERE user_id IN ({marks}) "
                                 f"AND profile LIKE '%exam_error%'" + lock, tuple(chunk)).fetchall()
        for row in rows:
            uid = row['user_id']
            pairs = {(F.norm(sim), date) for sim, date in removed[uid]}
            profile = _load(row['profile'], {})
            contents = profile.get('contents') if isinstance(profile.get('contents'), list) else []
            sessions = profile.get('sessions') if isinstance(profile.get('sessions'), list) else []
            changed = False
            keep = []
            for content in contents:
                if not isinstance(content, dict) or content.get('sourceType') != 'exam_error':
                    keep.append(content)
                    continue
                errors = content.get('examErrors') if isinstance(content.get('examErrors'), list) else []
                left = [e for e in errors if not (isinstance(e, dict) and
                                                  (F.norm(e.get('simulation')), str(e.get('date') or '')) in pairs)]
                if len(left) == len(errors):
                    keep.append(content)
                    continue
                changed = True
                cid = content.get('id')
                linked = lambda s: isinstance(s, dict) and (s.get('contentId') == cid or s.get('reviewContentId') == cid)
                if left:
                    content.update(
                        examErrors=left, errorCount=len(left),
                        firstErrorDate=min((e.get('date') or '' for e in left), default=''),
                        lastErrorDate=max((e.get('date') or '' for e in left), default=''),
                        sourceSimulations=sorted({e.get('simulation') for e in left if e.get('simulation')}),
                        sourceSkills=sorted({e.get('skill') for e in left if e.get('skill')}),
                        sourceQuestions=sorted({int(e.get('question') or 0) for e in left if e.get('question')}))
                    keep.append(content)
                    continue
                history = any(linked(s) and s.get('status') != 'planned' for s in sessions) or any(
                    isinstance(x, dict) and x.get('contentId') == cid
                    for x in (profile.get('feedback') or []) + (profile.get('studyLogs') or []))
                if history:
                    content.update(examErrors=[], errorCount=0, paused=True, sourceSimulations=[],
                                   sourceSkills=[], sourceQuestions=[])
                    sessions = [s for s in sessions if not (linked(s) and s.get('status') == 'planned'
                                                            and not s.get('locked') and str(s.get('date') or '') >= today)]
                    keep.append(content)
                    paused += 1
                else:
                    sessions = [s for s in sessions if not linked(s)]
                    deleted += 1
            if not changed:
                continue
            profile['contents'] = keep
            profile['sessions'] = sessions
            if isinstance(profile.get('planMeta'), dict):
                profile['planMeta']['dirty'] = True
            app.db.execute(c, 'UPDATE hmay_state SET profile=?,version=version+1,updated_at=? WHERE user_id=?',
                           (_json.dumps(profile, ensure_ascii=False, separators=(',', ':')), P.now().isoformat(), uid))
            touched += 1
    return dict(students=touched, removed=deleted, paused=paused)


def delete(app, c, user, data, HTTPError):
    if not can_edit(user):
        raise HTTPError(403, 'A exclusão de simulados é exclusiva do Master e da coordenação.')
    if str(data.get('confirmation') or '').strip().upper() != DELETE_CONFIRMATION:
        raise ValueError('Para confirmar, digite ' + DELETE_CONFIRMATION + '.')
    scores, answers, remove_map = (bool(data.get(k)) for k in ('scores', 'answers', 'map'))
    if not (scores or answers or remove_map):
        raise ValueError('Marque o que deve ser excluído.')
    whole = bool(data.get('whole'))
    exam_id = F.text(data.get('examId'), 160)
    exam, _, exams, rows = _deletion_scope(app, c, exam_id, whole, HTTPError, lock=True)
    counts = _counts(exams, rows)
    expected = data.get('expected') if isinstance(data.get('expected'), dict) else {}
    if any(expected.get(k) != counts[k] for k in ('exams', 'results', 'withScores')):
        raise HTTPError(409, 'Os dados deste simulado mudaram desde a conferência. Abra a exclusão de novo para conferir.')
    if remove_map and rows and not answers:
        raise HTTPError(409, 'Há respostas de alunos ligadas a este gabarito. Marque também "Respostas dos alunos".')
    stamp = P.now().isoformat()
    result = dict(examId=exam['id'], title=exam['title'], date=exam['applied_on'], whole=whole,
                  deletedResults=0, clearedScores=0, deletedExams=0, reviews=dict(students=0, removed=0, paused=0))
    if answers and rows:
        removed = {}
        for r in rows:
            removed.setdefault(r['user_id'], set()).add((r['activity'], r['applied_on']))
        ids = [r['id'] for r in rows]
        for start in range(0, len(ids), 500):
            group = ids[start:start + 500]
            marks = ','.join('?' for _ in group)
            app.db.execute(c, f'DELETE FROM hmay_performance WHERE id IN ({marks})', tuple(group))
        result['deletedResults'] = len(ids)
        result['clearedScores'] = counts['withScores']
        result['reviews'] = _remove_exam_reviews(app, c, removed)
    elif scores:
        for r in rows:
            metadata = r['metadata']
            if not any(_score_key(k) for k in metadata):
                continue
            clean = {k: v for k, v in metadata.items() if not _score_key(k)}
            app.db.execute(c, 'UPDATE hmay_performance SET metadata=?,version=version+1,updated_at=? WHERE id=?',
                           (_json.dumps(clean, ensure_ascii=False, separators=(',', ':')), stamp, r['id']))
            result['clearedScores'] += 1
    if remove_map:
        ids = [x['id'] for x in exams]
        marks = ','.join('?' for _ in ids)
        link = exam_link(app, 'metadata')
        left = app.db.execute(c, f'SELECT COUNT(*) AS n FROM hmay_performance WHERE {link} IN ({marks})', tuple(ids)).fetchone()
        if left['n']:
            raise HTTPError(409, 'Ainda há respostas ligadas a este gabarito. Nada foi excluído.')
        app.db.execute(c, f'DELETE FROM hmay_exams WHERE id IN ({marks})', tuple(ids))
        result['deletedExams'] = len(ids)
    kinds = [name for name, on in (('notas', scores or answers), ('respostas', answers), ('gabarito', remove_map)) if on]
    app.event(c, user, user['id'], 'exam_delete:' + '+'.join(kinds) + (':simulado' if whole else ':caderno'))
    try:
        import results_store as RS
        RS.STORE.invalidate()
        import model_data as MD
        MD._v36_dashboard_cache.clear()
    except Exception:
        pass
    return result
