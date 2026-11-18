"""Validade da senha provisória (v3.7.17).

Regras definidas pelo responsável em 18/11/2026:
- Toda senha provisória definida a partir desta versão vale 7 dias.
- Contas já existentes sem prazo registrado não expiram (base do ano atual).
- Senha vencida: login recusado com orientação para procurar a coordenação.
- Master e coordenação podem renovar a senha provisória de um aluno que ainda
  não concluiu o primeiro acesso. A coordenação continua restrita a contas Aluno
  ativas (mesma regra de require_target); contas Especiais nunca são alcançadas.

A tabela não usa chave estrangeira de propósito: os verificadores de inicialização
apagam contas técnicas e não conhecem esta tabela.
"""
import datetime as _dt
import hashlib
import time

VALIDITY_SECONDS = 7 * 86400
EXPIRED_MESSAGE = 'Sua senha provisória expirou. Procure a coordenação para receber uma nova.'
STUDENT_ROLES = ('aluno', 'user')


def schema(db, c):
    db.execute(c, 'CREATE TABLE IF NOT EXISTS hmay_provisional (user_id TEXT PRIMARY KEY, '
                  'expires_at BIGINT NOT NULL, set_by TEXT NOT NULL, set_at TEXT NOT NULL)')


def _row(row, key):
    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        return None


def start(app, c, target_id, actor_id='', now=None):
    """Inicia (ou reinicia) o prazo de 7 dias da senha provisória da conta."""
    stamp = int(now if now is not None else time.time())
    expires = stamp + VALIDITY_SECONDS
    app.db.execute(c, 'DELETE FROM hmay_provisional WHERE user_id=?', (target_id,))
    app.db.execute(c, 'INSERT INTO hmay_provisional(user_id,expires_at,set_by,set_at) VALUES (?,?,?,?)',
                   (target_id, expires, str(actor_id or ''), _dt.datetime.fromtimestamp(stamp, _dt.timezone.utc).isoformat()))
    return expires


def start_if_student(app, c, target_id, actor_id=''):
    row = app.db.execute(c, 'SELECT role,must_change FROM hmay_users WHERE id=?', (target_id,)).fetchone()
    if row and _row(row, 'role') in STUDENT_ROLES and int(_row(row, 'must_change') or 0):
        return start(app, c, target_id, actor_id)
    return None


def clear(app, c, target_id):
    app.db.execute(c, 'DELETE FROM hmay_provisional WHERE user_id=?', (target_id,))


def expires_at(app, c, target_id):
    row = app.db.execute(c, 'SELECT expires_at FROM hmay_provisional WHERE user_id=?', (target_id,)).fetchone()
    return int(_row(row, 'expires_at')) if row else None


def expired(app, c, user, now=None):
    """True somente para conta com troca pendente e prazo registrado já vencido."""
    if not user or not int(_row(user, 'must_change') or 0):
        return False
    limit = expires_at(app, c, _row(user, 'id'))
    return limit is not None and int(now if now is not None else time.time()) >= limit


def _display(timestamp):
    import planner as P
    return _dt.datetime.fromtimestamp(timestamp, P.TZ).strftime('%d/%m/%Y %H:%M')


def handle(app, c, user, path, method, data, query, start_response, HTTPError):
    if path != '/api/provisional/renew':
        raise HTTPError(404, 'Página não encontrada.')
    if user.get('role') not in ('master', 'coordenador'):
        raise HTTPError(403, 'Renovação reservada ao Master e à coordenação.')
    if method != 'POST':
        raise HTTPError(405, 'Use o formulário de renovação.')
    import webapp as W
    login = str(data.get('username') or '').strip().lower()
    if not login:
        raise ValueError('Informe o login do aluno.')
    row = app.db.execute(c, 'SELECT id,username,name,role,active,must_change FROM hmay_users WHERE username=?',
                         (login,)).fetchone()
    # Mesma resposta para login inexistente e conta fora do escopo: não revela contas Especiais.
    if not row:
        raise HTTPError(404, 'Aluno não encontrado entre as contas que você pode administrar.')
    target = dict(row)
    try:
        app.require_target(user, target['id'], c)
    except HTTPError:
        raise HTTPError(404, 'Aluno não encontrado entre as contas que você pode administrar.')
    if target['role'] not in STUDENT_ROLES or not target['active']:
        raise HTTPError(404, 'Aluno não encontrado entre as contas que você pode administrar.')
    if not int(target['must_change'] or 0):
        raise HTTPError(409, 'Este aluno já concluiu o primeiro acesso. A redefinição de senha é feita pelo Master.')
    password = W.valid_password(data.get('password'))
    app.db.execute(c, 'UPDATE hmay_users SET password=?,must_change=1 WHERE id=?', (W.password_hash(password), target['id']))
    app.db.execute(c, 'DELETE FROM hmay_sessions WHERE user_id=?', (target['id'],))
    app.db.execute(c, 'DELETE FROM hmay_attempts WHERE key=?', ('user:' + hashlib.sha256(target['username'].encode()).hexdigest(),))
    limit = start(app, c, target['id'], user.get('id'))
    app.event(c, user, target['id'], 'provisional_password_renewed')
    return app.reply(start_response, 200, dict(ok=True, name=target['name'], username=target['username'],
                                               expiresAt=_display(limit)))
