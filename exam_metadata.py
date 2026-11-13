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
