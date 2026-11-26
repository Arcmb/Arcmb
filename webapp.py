"""Aplicação WSGI. PostgreSQL na nuvem; SQLite somente no teste local explícito.
Senhas PBKDF2, sessões opacas, CSRF, autorização por conta, bloqueio de tentativas
repetidas e gravação transacional com controle de versão. Sem telemetria.
"""
from __future__ import annotations
import contextlib, csv, hashlib, hmac, html, io, json, logging, os, re, secrets, sqlite3, threading, time
from http.cookies import SimpleCookie
from http import HTTPStatus
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import planner as P
import performance as PERF
import adaptive as ADAPT
import exams as EXAMS
import unified as UNIFIED
import area_workbook as AREA_WORKBOOK
import academic_history as HISTORY
import model_data as MODEL_DATA
import disciplines_catalog as DISCIPLINES  # === DISCIPLINES CATALOG V3.12.0 ===
import enem_items as ENEM_ITEMS
import school_reports as SCHOOL_REPORTS  # === SCHOOL REPORTS V3.10.0 ===
import motor_profiles as MOTOR  # === MOTOR PROFILES V3.9.0 ===
import provisional_access as PROVISIONAL  # === PROVISIONAL EXPIRY V3.7.17 ===
EXAMS.analyse=AREA_WORKBOOK.analyse

BASE=Path(__file__).resolve().parent
MAX_BODY=5_000_000
LOG=logging.getLogger('meucronograma')

class HTTPError(Exception):
    def __init__(self,status,message): self.status,self.message=status,message

def encode(data):return json.dumps(data,ensure_ascii=False,separators=(',',':'),allow_nan=False)
def password_hash(password):
    salt=secrets.token_hex(16);rounds=600000
    return f'pbkdf2_sha256${rounds}${salt}$'+hashlib.pbkdf2_hmac('sha256',password.encode(),salt.encode(),rounds).hex()
def password_ok(password,stored):
    try:
        kind,rounds,salt,wanted=stored.split('$')
        if kind!='pbkdf2_sha256' or not 100000<=int(rounds)<=2000000:return False
        got=hashlib.pbkdf2_hmac('sha256',password.encode(),salt.encode(),int(rounds)).hex()
        return hmac.compare_digest(got,wanted)
    except (ValueError,TypeError):return False

def valid_password(value):
    if not isinstance(value,str) or not 8<=len(value)<=128:raise ValueError('A senha precisa ter de 8 a 128 caracteres.')
    return value

def username(value):
    value=str(value).strip().lower()
    if not re.fullmatch(r'[a-z0-9_.-]{3,40}',value):raise ValueError('Login: 3 a 40 letras sem acento, números, ponto, hífen ou sublinhado.')
    return value

class Database:
    def __init__(self,url,local_path=None):self.url=url;self.local_path=local_path;self.ready=False;self.lock=threading.Lock()
    @property
    def configured(self):return bool(self.url or self.local_path)
    @contextlib.contextmanager
    def connection(self,write=False):
        if self.local_path:
            conn=sqlite3.connect(self.local_path,timeout=15);conn.row_factory=sqlite3.Row;conn.execute('PRAGMA foreign_keys=ON')
            if write:conn.execute('BEGIN IMMEDIATE')
        else:
            import psycopg
            from psycopg.rows import dict_row
            conn=psycopg.connect(self.url,connect_timeout=8,row_factory=dict_row)
        try:yield conn;conn.commit()
        except Exception:conn.rollback();raise
        finally:conn.close()
    def execute(self,conn,sql,args=()):return conn.execute(sql if self.local_path else sql.replace('?','%s'),args)
    def initialize(self,owner,owner_password,may_password=''):
        if self.ready:return
        with self.lock:
            if self.ready:return
            with self.connection(write=True)as c:
                for statement in [
                    'CREATE TABLE IF NOT EXISTS hmay_users (id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE, name TEXT NOT NULL, password TEXT NOT NULL, role TEXT NOT NULL, active INTEGER NOT NULL, must_change INTEGER NOT NULL, created_at TEXT NOT NULL)',
                    'CREATE TABLE IF NOT EXISTS hmay_state (user_id TEXT PRIMARY KEY REFERENCES hmay_users(id), profile TEXT NOT NULL, version INTEGER NOT NULL, updated_at TEXT NOT NULL)',
                    'CREATE TABLE IF NOT EXISTS hmay_sessions (token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES hmay_users(id), csrf TEXT NOT NULL, expires BIGINT NOT NULL)',
                    'CREATE TABLE IF NOT EXISTS hmay_attempts (key TEXT PRIMARY KEY, hits INTEGER NOT NULL, until_at BIGINT NOT NULL)',
                    'CREATE TABLE IF NOT EXISTS hmay_events (id TEXT PRIMARY KEY, actor_id TEXT NOT NULL, target_id TEXT NOT NULL, kind TEXT NOT NULL, at TEXT NOT NULL)',
                    'CREATE INDEX IF NOT EXISTS hmay_sessions_user ON hmay_sessions(user_id)',
                    'CREATE INDEX IF NOT EXISTS hmay_events_time ON hmay_events(at)']:
                    self.execute(c,statement)
                PERF.schema(self,c)
                ADAPT.schema(self,c)
                EXAMS.schema(self,c)
                PROVISIONAL.schema(self,c)
                found=self.execute(c,'SELECT id FROM hmay_users WHERE username=?',(owner,)).fetchone()
                if not found:
                    if not owner_password:raise RuntimeError('MASTER_PASSWORD precisa ser configurada para o primeiro acesso.')
                    self.create_user(c,owner,'Fábio',valid_password(owner_password),'master',False)
                # A conta do proprietário nunca é rebaixada nem tem sua senha restaurada no deploy.
                self.execute(c,'UPDATE hmay_users SET role=?,active=1 WHERE username=?',('master',owner))
                if not self.execute(c,'SELECT id FROM hmay_users WHERE username=?',('mayra',)).fetchone():
                    self.create_user(c,'mayra','Mayra',valid_password(may_password)if may_password else None,'user',True)
            self.ready=True
    def create_user(self,c,login,name,password,role='user',must_change=True):
        i=P.uid();p=P.default_profile(name,i)
        self.execute(c,'INSERT INTO hmay_users(id,username,name,password,role,active,must_change,created_at) VALUES (?,?,?,?,?,?,?,?)',(i,login,name,password_hash(password)if password else '!',role,1,int(must_change),P.now().isoformat()))
        self.execute(c,'INSERT INTO hmay_state(user_id,profile,version,updated_at) VALUES (?,?,?,?)',(i,encode(p),1,P.now().isoformat()));return i


# === MEU CRONOGRAMA: CADASTRO EM LOTE A PARTIR DOS RESULTADOS ===
def _bulk_row_value(row, key, default=''):
    try:
        value = row[key]
    except (KeyError, IndexError, TypeError):
        value = default
    return default if value is None else value


def _bulk_normalize_name(value):
    import unicodedata
    text = unicodedata.normalize('NFKD', str(value or ''))
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r'[^A-Za-z0-9]+', ' ', text).strip().lower()
    return ' '.join(text.split())


def _bulk_login_base(name):
    import unicodedata
    text = unicodedata.normalize('NFKD', str(name or ''))
    text = ''.join(ch for ch in text if not unicodedata.combining(ch)).lower()
    parts = re.findall(r'[a-z0-9]+', text)
    if len(parts) >= 2:
        base = parts[0] + '.' + parts[-1]
    elif parts:
        base = parts[0]
    else:
        base = 'aluno'
    base = re.sub(r'[^a-z0-9_.-]+', '', base).strip('._-')
    if len(base) < 3:
        base = ('aluno.' + base).strip('.')
    return (base or 'aluno')[:36]


def _bulk_unique_login(base, used_logins):
    base = (base or 'aluno')[:40].strip('._-') or 'aluno'
    candidate = base
    suffix = 2
    while candidate in used_logins:
        tail = '.' + str(suffix)
        candidate = base[:40-len(tail)].rstrip('._-') + tail
        suffix += 1
    return candidate


def bulk_create_student_accounts(app, c, user, students, provisional_password):
    if user.get('role') not in ('master', 'coordenador'):
        raise PermissionError('Cadastro em lote reservado ao Master e à coordenação.')
    password = valid_password(provisional_password)
    password_digest = password_hash(password)
    if not isinstance(students, list) or not students:
        raise ValueError('O arquivo não possui alunos para cadastrar.')
    if len(students) > 5000:
        raise ValueError('O cadastro em lote aceita até 5.000 linhas por arquivo.')

    rows = app.db.execute(
        c,
        "SELECT id,username,name,role,active FROM hmay_users WHERE role<>'deleted' ORDER BY name,username"
    ).fetchall()
    used_logins = {
        str(_bulk_row_value(row, 'username')).strip().lower()
        for row in rows
    }
    by_name_students = {}
    by_name_other = {}
    for row in rows:
        normalized = _bulk_normalize_name(_bulk_row_value(row, 'name'))
        if not normalized:
            continue
        target = by_name_students if _bulk_row_value(row, 'role') in ('user', 'aluno') else by_name_other
        target.setdefault(normalized, []).append(row)

    created = []
    existing = []
    conflicts = []
    duplicate_rows = 0
    seen_file = set()
    account_count = int(app.db.execute(c, "SELECT COUNT(*) AS n FROM hmay_users WHERE role<>'deleted'").fetchone()['n'])

    for student in students:
        name = str(student.get('name') or '').strip()
        normalized = _bulk_normalize_name(name)
        if not normalized or not 1 < len(name) <= 150:
            conflicts.append({'name': name or '(sem nome)', 'reason': 'Nome ausente ou inválido.'})
            continue
        if normalized in seen_file:
            duplicate_rows += 1
            continue
        seen_file.add(normalized)

        requested_login = str(student.get('login') or '').strip().lower()
        matching_students = by_name_students.get(normalized, [])
        if matching_students:
            active_matches = [row for row in matching_students if bool(_bulk_row_value(row, 'active', 0))]
            if len(active_matches) == 1:
                row = active_matches[0]
                existing.append({
                    'name': name,
                    'username': _bulk_row_value(row, 'username'),
                    'id': _bulk_row_value(row, 'id'),
                    'status': 'already_exists',
                })
                continue
            if len(active_matches) > 1 and requested_login:
                selected = [
                    row for row in active_matches
                    if str(_bulk_row_value(row, 'username')).lower() == requested_login
                ]
                if len(selected) == 1:
                    row = selected[0]
                    existing.append({
                        'name': name,
                        'username': _bulk_row_value(row, 'username'),
                        'id': _bulk_row_value(row, 'id'),
                        'status': 'already_exists',
                    })
                    continue
            if active_matches:
                conflicts.append({'name': name, 'reason': 'Há mais de uma conta de aluno com esse nome. Informe o login para desempatar.'})
            else:
                conflicts.append({'name': name, 'reason': 'Já existe uma conta de aluno desativada com esse nome. Reative-a no painel.'})
            continue

        if by_name_other.get(normalized):
            conflicts.append({'name': name, 'reason': 'Já existe uma conta de outro perfil com esse mesmo nome.'})
            continue

        generated = not bool(requested_login)
        if requested_login:
            try:
                login = username(requested_login)
            except ValueError as exc:
                conflicts.append({'name': name, 'reason': str(exc)})
                continue
            if login in used_logins:
                conflicts.append({'name': name, 'reason': f'O login {login} já está em uso.'})
                continue
        else:
            login = _bulk_unique_login(_bulk_login_base(name), used_logins)

        if account_count >= 10000:
            conflicts.append({'name': name, 'reason': 'Limite de 10.000 contas atingido.'})
            continue

        target_id = P.uid()
        stamp = P.now().isoformat()
        inserted = app.db.execute(
            c,
            'INSERT INTO hmay_users(id,username,name,password,role,active,must_change,created_at) '
            'VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(username) DO NOTHING',
            (target_id, login, name, password_digest, 'aluno', 1, 1, stamp),
        )
        if inserted.rowcount != 1:
            conflicts.append({'name': name, 'reason': f'O login {login} passou a ser utilizado por outra conta.'})
            used_logins.add(login)
            continue
        profile = P.default_profile(name, target_id)
        app.db.execute(
            c,
            'INSERT INTO hmay_state(user_id,profile,version,updated_at) VALUES (?,?,?,?)',
            (target_id, encode(profile), 1, stamp),
        )
        set_student_creation_year(app,c,user['id'],target_id)
        app.event(c, user, target_id, 'account_created_bulk_results')
        PROVISIONAL.start(app, c, target_id, user.get('id'))
        created.append({
            'name': name,
            'username': login,
            'id': target_id,
            'generatedLogin': generated,
            'historyCandidates': HISTORY.candidates(app,c,name,_academic_year_active(app,c,user['id'])-1),
            'status': 'created',
        })
        used_logins.add(login)
        by_name_students.setdefault(normalized, []).append({
            'id': target_id, 'username': login, 'name': name,
            'role': 'aluno', 'active': 1,
        })
        account_count += 1

    return {
        'created': created,
        'existing': existing,
        'conflicts': conflicts,
        'duplicateRows': duplicate_rows,
        'summary': {
            'rows': len(students),
            'uniqueNames': len(seen_file),
            'created': len(created),
            'existing': len(existing),
            'conflicts': len(conflicts),
            'duplicateRows': duplicate_rows,
        },
    }



# === MEU CRONOGRAMA: CICLOS DE ANO LETIVO V1 ===
def academic_year_schema(app,c):
    app.db.execute(c,'CREATE TABLE IF NOT EXISTS hmay_academic_year (user_id TEXT PRIMARY KEY REFERENCES hmay_users(id), active_year INTEGER NOT NULL, updated_at TEXT NOT NULL)')
    app.db.execute(c,'CREATE TABLE IF NOT EXISTS hmay_academic_cycles (id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES hmay_users(id), academic_year INTEGER NOT NULL, profile TEXT NOT NULL, opened_at TEXT NOT NULL, closed_at TEXT NOT NULL, UNIQUE(user_id,academic_year))')
    app.db.execute(c,'CREATE INDEX IF NOT EXISTS hmay_academic_cycles_user_year ON hmay_academic_cycles(user_id,academic_year)')

def _academic_year_target(app,c,user,target_id,HTTPError):
    if user.get('role') not in ('master','coordenador'):
        raise HTTPError(403,'A gestão de ano letivo é exclusiva do Master e da coordenação.')
    app.require_target(user,target_id,c)
    row=app.db.execute(c,'SELECT id,username,name,role,active FROM hmay_users WHERE id=?',(target_id,)).fetchone()
    if not row:raise HTTPError(404,'Conta não encontrada.')
    target=dict(row)
    own_account=str(target.get('id'))==str(user.get('id'))
    if target.get('role') not in ('user','aluno') and not (own_account and user.get('role') in ('master','coordenador')):
        raise HTTPError(400,'Selecione uma conta de aluno ou use a sua própria conta administrativa.')
    return target

def _academic_year_active(app,c,target_id):
    academic_year_schema(app,c)
    row=app.db.execute(c,'SELECT active_year FROM hmay_academic_year WHERE user_id=?',(target_id,)).fetchone()
    if row:
        return int(row['active_year'])
    account=app.db.execute(c,'SELECT role,created_at FROM hmay_users WHERE id=?',(target_id,)).fetchone()
    if account and account['role'] in ('user','aluno'):
        return int(account['created_at'][:4])
    if account and account['role']=='coordenador':
        owner=app.db.execute(c,'''SELECT y.active_year FROM hmay_academic_year y
            JOIN hmay_users u ON u.id=y.user_id WHERE u.username=?''',(app.owner,)).fetchone()
        if owner:return int(owner['active_year'])
    return int(P.now().year)

def set_student_creation_year(app,c,actor_id,student_id):
    year=_academic_year_active(app,c,actor_id)
    app.db.execute(c,'INSERT INTO hmay_academic_year(user_id,active_year,updated_at) VALUES (?,?,?)',
                   (student_id,year,P.now().isoformat()))

def master_accounts(app,c,user):
    year=_academic_year_active(app,c,user['id'])
    rows=app.db.execute(c,'''SELECT u.id,u.username,u.name,u.role,u.active,u.must_change,u.password,
        u.created_at,y.active_year,cy.academic_year AS archived_year
        FROM hmay_users u LEFT JOIN hmay_academic_year y ON y.user_id=u.id
        LEFT JOIN hmay_academic_cycles cy ON cy.user_id=u.id AND cy.academic_year=?
        WHERE u.role<>'deleted' ORDER BY u.name,u.username''',(year,)).fetchall()
    accounts=[]
    for row in rows:
        student=row['role'] in ('user','aluno')
        active_year=row['active_year'] or (int(row['created_at'][:4]) if student else None)
        accounts.append({**app.user_public(row),'passwordSet':row['password']!='!',
                         'canDelete':row['id']!=user['id'] and row['username']!=app.owner,
                         'activeAcademicYear':active_year,
                         'registeredForYear':not student or active_year==year or row['archived_year']==year})
    return {'accounts':accounts,'academicYear':year}

def academic_year_status(app,c,user,target_id,HTTPError):
    target=_academic_year_target(app,c,user,target_id,HTTPError)
    active=_academic_year_active(app,c,target_id)
    rows=app.db.execute(c,'SELECT academic_year,opened_at,closed_at FROM hmay_academic_cycles WHERE user_id=? AND academic_year<>? ORDER BY academic_year DESC',(target_id,active)).fetchall()
    archived=[dict(r) for r in rows]
    years=sorted({active,*[int(r['academic_year']) for r in archived]})
    return {'student':{'id':target['id'],'name':target['name'],'username':target['username'],'active':bool(target['active'])},'activeYear':active,'archived':archived,'availableYears':years,'nextYear':max(years)+1 if years else active+1}

def academic_year_open(app,c,user,target_id,new_year,HTTPError,registration=False):
    target=_academic_year_target(app,c,user,target_id,HTTPError)
    lock='' if app.db.local_path else ' FOR UPDATE'
    state=app.db.execute(c,'SELECT profile,version FROM hmay_state WHERE user_id=?'+lock,(target_id,)).fetchone()
    if not state:raise HTTPError(404,'Perfil acadêmico não encontrado.')
    current=_academic_year_active(app,c,target_id)
    try:new_year=int(new_year)
    except (TypeError,ValueError):raise ValueError('Ano letivo inválido.')
    if registration and new_year==current:
        return academic_year_status(app,c,user,target_id,HTTPError)
    if registration and new_year<current:
        raise ValueError('A matrícula deve ser feita em um ano posterior ao ciclo ativo.')
    if not registration and new_year!=current+1:raise ValueError('O próximo ano letivo deve ser '+str(current+1)+'.')
    if not 2020<=new_year<=2100:raise ValueError('Ano letivo fora do intervalo permitido.')
    stamp=P.now().isoformat()
    target_cycle=app.db.execute(c,'SELECT id FROM hmay_academic_cycles WHERE user_id=? AND academic_year=?',(target_id,new_year)).fetchone()
    if target_cycle:raise HTTPError(409,'O ano '+str(new_year)+' já existe. Selecione esse ano no controle para alternar de ciclo.')
    existing=app.db.execute(c,'SELECT id FROM hmay_academic_cycles WHERE user_id=? AND academic_year=?',(target_id,current)).fetchone()
    if existing:
        app.db.execute(c,'UPDATE hmay_academic_cycles SET profile=?,closed_at=? WHERE user_id=? AND academic_year=?',(state['profile'],stamp,target_id,current))
    else:
        app.db.execute(c,'INSERT INTO hmay_academic_cycles(id,user_id,academic_year,profile,opened_at,closed_at) VALUES (?,?,?,?,?,?)',(P.uid(),target_id,current,state['profile'],str(current)+'-01-01T00:00:00',stamp))
    fresh=P.default_profile(target['name'],target_id)
    app.db.execute(c,'UPDATE hmay_state SET profile=?,version=version+1,updated_at=? WHERE user_id=?',(encode(fresh),stamp,target_id))
    app.db.execute(c,'INSERT INTO hmay_academic_year(user_id,active_year,updated_at) VALUES (?,?,?) ON CONFLICT(user_id) DO UPDATE SET active_year=excluded.active_year,updated_at=excluded.updated_at',(target_id,new_year,stamp))
    app.event(c,user,target_id,'academic_year_open_'+str(new_year))
    return academic_year_status(app,c,user,target_id,HTTPError)

def academic_year_switch(app,c,user,target_id,selected_year,HTTPError):
    target=_academic_year_target(app,c,user,target_id,HTTPError)
    current=_academic_year_active(app,c,target_id)
    try:selected_year=int(selected_year)
    except (TypeError,ValueError):raise ValueError('Ano letivo inválido.')
    if selected_year==current:return academic_year_status(app,c,user,target_id,HTTPError)
    if not 2020<=selected_year<=2100:raise ValueError('Ano letivo fora do intervalo permitido.')
    selected=app.db.execute(c,'SELECT id,profile FROM hmay_academic_cycles WHERE user_id=? AND academic_year=?',(target_id,selected_year)).fetchone()
    if not selected:raise HTTPError(404,'O ano '+str(selected_year)+' ainda não existe para este aluno.')
    state=app.db.execute(c,'SELECT profile,version FROM hmay_state WHERE user_id=?',(target_id,)).fetchone()
    if not state:raise HTTPError(404,'Perfil acadêmico não encontrado.')
    stamp=P.now().isoformat()
    current_cycle=app.db.execute(c,'SELECT id FROM hmay_academic_cycles WHERE user_id=? AND academic_year=?',(target_id,current)).fetchone()
    if current_cycle:
        app.db.execute(c,'UPDATE hmay_academic_cycles SET profile=?,closed_at=? WHERE user_id=? AND academic_year=?',(state['profile'],stamp,target_id,current))
    else:
        app.db.execute(c,'INSERT INTO hmay_academic_cycles(id,user_id,academic_year,profile,opened_at,closed_at) VALUES (?,?,?,?,?,?)',(P.uid(),target_id,current,state['profile'],str(current)+'-01-01T00:00:00',stamp))
    app.db.execute(c,'UPDATE hmay_state SET profile=?,version=version+1,updated_at=? WHERE user_id=?',(selected['profile'],stamp,target_id))
    app.db.execute(c,'INSERT INTO hmay_academic_year(user_id,active_year,updated_at) VALUES (?,?,?) ON CONFLICT(user_id) DO UPDATE SET active_year=excluded.active_year,updated_at=excluded.updated_at',(target_id,selected_year,stamp))
    app.event(c,user,target_id,'academic_year_switch_'+str(current)+'_to_'+str(selected_year))
    return academic_year_status(app,c,user,target_id,HTTPError)

def academic_year_comparison(app,c,user,target_id,HTTPError):
    target=_academic_year_target(app,c,user,target_id,HTTPError)
    active=_academic_year_active(app,c,target_id);previous=active-1
    import model_data as AY_MODEL
    HISTORY.schema(app,c)
    data=AY_MODEL.student_summary(app,c,user,target,history_year=previous)
    buckets={previous:{'year':previous,'simulations':0,'correct':0,'marked':0,'valid':0,'areas':{}},active:{'year':active,'simulations':0,'correct':0,'marked':0,'valid':0,'areas':{}}}
    for sim in data.get('simulations',[]):
        try:year=int(str(sim.get('date',''))[:4])
        except (TypeError,ValueError):continue
        if year not in buckets:continue
        b=buckets[year];b['simulations']+=1;b['correct']+=int(sim.get('correct') or 0);b['marked']+=int(sim.get('marked') or 0);b['valid']+=int(sim.get('valid') or 0)
        for area in sim.get('areas') or []:
            name=str(area.get('name') or 'Não informado')
            a=b['areas'].setdefault(name,{'name':name,'correct':0,'marked':0,'total':0})
            a['correct']+=int(area.get('correct') or 0);a['marked']+=int(area.get('marked') or 0);a['total']+=int(area.get('total') or 0)
    def finish(b):
        b['accuracy']=None if not b['marked'] else round(100*b['correct']/b['marked'],2)
        b['averageCorrect']=None if not b['simulations'] else round(b['correct']/b['simulations'],2)
        rows=[]
        for a in b.pop('areas').values():
            a['accuracy']=None if not a['marked'] else round(100*a['correct']/a['marked'],2);rows.append(a)
        b['areas']=sorted(rows,key=lambda x:x['name'])
        return b
    prev=finish(buckets[previous]);cur=finish(buckets[active])
    delta=None if prev['accuracy'] is None or cur['accuracy'] is None else round(cur['accuracy']-prev['accuracy'],2)
    names=sorted({x['name'] for x in prev['areas']}|{x['name'] for x in cur['areas']})
    pa={x['name']:x for x in prev['areas']};ca={x['name']:x for x in cur['areas']}
    area_compare=[]
    for name in names:
        p=pa.get(name,{});n=ca.get(name,{})
        pv=p.get('accuracy');nv=n.get('accuracy')
        area_compare.append({'name':name,'previous':pv,'current':nv,'delta':None if pv is None or nv is None else round(nv-pv,2)})
    return {'student':{'id':target['id'],'name':target['name']},'linkedResults':HISTORY.linked_results(app,c,target_id,previous),'previous':prev,'current':cur,'delta':delta,'areas':area_compare,'notice':'A comparação usa os resultados registrados em cada ano. Conteúdos e revisões do ano anterior não entram no cronograma atual.'}


class App:
    def overview_year(self,c,user):
        return str(_academic_year_active(self,c,user['id']))

    def __init__(self,env=None):
        self.env=dict(os.environ if env is None else env);self.local=self.env.get('LOCAL_TEST')=='1'
        self.owner=username(self.env.get('MASTER_USERNAME','arcmb'))
        self.secret=self.env.get('SECRET_KEY','')
        if not self.secret and self.local:self.secret=secrets.token_urlsafe(48)
        self.db=Database(self.env.get('DATABASE_URL',''),self.env.get('LOCAL_DB',str(BASE/'local_test.sqlite3'))if self.local else None)
        self.hosts={x.strip().lower()for x in self.env.get('ALLOWED_HOSTS','meucronograma.onrender.com').split(',')if x.strip()}
        if self.env.get('RENDER_EXTERNAL_HOSTNAME'):self.hosts.add(self.env['RENDER_EXTERNAL_HOSTNAME'].lower())
        if self.local:self.hosts.update({'localhost','127.0.0.1','testserver'})
    def cookie(self,name,value,age):
        return ('Set-Cookie',f'{name}={value}; Path=/; Max-Age={age}; HttpOnly; SameSite=Lax'+(''if self.local else '; Secure'))
    def reply(self,start,status,body,content_type='application/json; charset=utf-8',headers=None):
        if isinstance(body,(dict,list)):body=encode(body)
        if isinstance(body,str):body=body.encode()
        base=[('Content-Type',content_type),('Content-Length',str(len(body))),('Cache-Control','no-store'),('X-Content-Type-Options','nosniff'),('X-Frame-Options','DENY'),('Referrer-Policy','same-origin'),('Permissions-Policy','camera=(), microphone=(), geolocation=()'),('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")]
        if not self.local:base.append(('Strict-Transport-Security','max-age=31536000'))
        start(f'{status} {HTTPStatus(status).phrase}',base+(headers or []));return [body]
    def body(self,environ):
        try:length=int(environ.get('CONTENT_LENGTH')or 0)
        except ValueError:raise HTTPError(400,'Tamanho inválido.')
        if not 0<=length<=MAX_BODY:raise HTTPError(413,'Arquivo muito grande. Limite de 5 MB.')
        raw=environ['wsgi.input'].read(length)
        try:
            if 'application/json'in environ.get('CONTENT_TYPE',''):
                result=json.loads(raw.decode(),parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
                if not isinstance(result,dict):raise ValueError()
                return result
            return {k:v[0]for k,v in parse_qs(raw.decode(),keep_blank_values=True).items()}
        except (ValueError,UnicodeError):raise HTTPError(400,'Dados inválidos.')
    def signed_login_token(self):
        value=str(int(time.time()))+'.'+secrets.token_urlsafe(24)
        return value+'.'+hmac.new(self.secret.encode(),value.encode(),'sha256').hexdigest()
    def valid_login_token(self,token):
        try:
            timestamp,nonce,signature=token.split('.');value=timestamp+'.'+nonce
            return 0<=time.time()-int(timestamp)<=3600 and hmac.compare_digest(signature,hmac.new(self.secret.encode(),value.encode(),'sha256').hexdigest())
        except (ValueError,AttributeError):return False
    def login_page(self,error='',csrf=''):
        return (BASE/'static/login.html').read_text().replace('@@ERROR@@',html.escape(error)).replace('@@CSRF@@',html.escape(csrf)).replace('@@NAME@@','Meu Cronograma')
    def current_user(self,c,cookies):
        token=cookies.get('hmay_session')
        if not token:return None
        digest=hashlib.sha256(token.value.encode()).hexdigest()
        row=self.db.execute(c,'SELECT u.*,s.csrf,s.token_hash FROM hmay_sessions s JOIN hmay_users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires>? AND u.active=1',(digest,int(time.time()))).fetchone()
        return dict(row)if row else None
    def user_public(self,u):return {k:u[k]for k in ('id','username','name','role','active','must_change')}
    def require_target(self,user,target,c=None):
        if user['role']=='master' or target==user['id']:return
        if user['role']=='coordenador' and c is not None:
            row=self.db.execute(c,'SELECT role,active FROM hmay_users WHERE id=?',(target,)).fetchone()
            if row and row['role'] in ('user','aluno') and row['active']:return
        raise HTTPError(403,'Você não tem acesso a esta conta.')
    def event(self,c,user,target,kind):self.db.execute(c,'INSERT INTO hmay_events(id,actor_id,target_id,kind,at) VALUES (?,?,?,?,?)',(P.uid(),user['id'],target,kind,P.now().isoformat()))
    def state(self,c,user,target):
        self.require_target(user,target,c)
        row=self.db.execute(c,'SELECT s.*,u.name,u.active FROM hmay_state s JOIN hmay_users u ON u.id=s.user_id WHERE s.user_id=?',(target,)).fetchone()
        if not row:raise HTTPError(404,'Conta não encontrada.')
        p=json.loads(row['profile']);p['name']=row['name']
        return dict(profile=p,version=row['version'],updatedAt=row['updated_at'],serverDate=P.today(),user=self.user_public(user),csrf=user['csrf'],advice=P.ADVICE)
    def __call__(self,e,start):
        # Só publica o status HTTP após o commit. Falhas no commit não podem
        # ser apresentadas como uma confirmação de salvamento ao navegador.
        pending={}
        def prepare(status,headers):pending.update(status=status,headers=headers)
        try:body=self.handle(e,prepare)
        except HTTPError as ex:body=self.reply(prepare,ex.status,dict(error=ex.message))
        except (ValueError,KeyError,TypeError,StopIteration,OverflowError)as ex:
            message=str(ex)if isinstance(ex,ValueError)else 'Dados incompletos ou registro não encontrado.'
            payload=dict(error=message)
            if getattr(ex,'issues',None) is not None:payload.update(issues=ex.issues,total=getattr(ex,'total',len(ex.issues)))
            body=self.reply(prepare,400,payload)
        except Exception:
            LOG.error('Falha interna (%s). Solicitação e credenciais omitidas.',__import__('sys').exc_info()[0].__name__)
            body=self.reply(prepare,503,dict(error='Serviço temporariamente indisponível. Nenhuma confirmação de salvamento foi emitida. Tente novamente.'))
        start(pending['status'],pending['headers']);return body
    def handle(self,e,start):
        host=e.get('HTTP_HOST','').split(':')[0].lower()
        if host not in self.hosts:raise HTTPError(400,'Endereço não autorizado.')
        path=e.get('PATH_INFO','/');method=e.get('REQUEST_METHOD','GET').upper()
        if method not in ('GET','POST'):raise HTTPError(405,'Método não permitido.')
        if path.startswith('/static/'):
            allowed={'app.js':'application/javascript; charset=utf-8','import_fixes.js':'application/javascript; charset=utf-8','style.css':'text/css; charset=utf-8','login.js':'application/javascript; charset=utf-8','performance.js':'application/javascript; charset=utf-8','adaptive.js':'application/javascript; charset=utf-8','selective.js':'application/javascript; charset=utf-8','import_wizard.js':'application/javascript; charset=utf-8','area_tabs.js':'application/javascript; charset=utf-8','coordinator_accounts.js':'application/javascript; charset=utf-8','routine_entries.js':'application/javascript; charset=utf-8','two_tab.js':'application/javascript; charset=utf-8','result_export.js':'application/javascript; charset=utf-8','result_import.js':'application/javascript; charset=utf-8','bulk_accounts_panel.js':'application/javascript; charset=utf-8','return_to_owner.js':'application/javascript; charset=utf-8','student_summary.js':'application/javascript; charset=utf-8','tri_scores.js':'application/javascript; charset=utf-8','study_schedule.js':'application/javascript; charset=utf-8','schedule_admin_refinement.js':'application/javascript; charset=utf-8','student_guidance.js':'application/javascript; charset=utf-8','review_table_page.js':'application/javascript; charset=utf-8','review_history.js':'application/javascript; charset=utf-8','review_calendar_table.js':'application/javascript; charset=utf-8','discipline_colors.js':'application/javascript; charset=utf-8','responsive_ui_refinement.js':'application/javascript; charset=utf-8','use_guide.js':'application/javascript; charset=utf-8','provisional_renewal.js':'application/javascript; charset=utf-8','student_view_v2.js':'application/javascript; charset=utf-8','motor_profiles.js':'application/javascript; charset=utf-8','school_reports.js':'application/javascript; charset=utf-8','disciplines_catalog.js':'application/javascript; charset=utf-8','enem_items.js':'application/javascript; charset=utf-8','onboarding.js':'application/javascript; charset=utf-8','csp_style_shim.js':'application/javascript; charset=utf-8','qi_extras.css':'text/css; charset=utf-8','academic_year.js':'application/javascript; charset=utf-8','qi-logo.svg':'image/svg+xml; charset=utf-8','model_data.js':'application/javascript; charset=utf-8','icon.svg':'image/svg+xml','manifest.webmanifest':'application/manifest+json'}
            name=path[len('/static/'):]
            if method!='GET' or name not in allowed:raise HTTPError(404,'Arquivo não encontrado.')
            return self.reply(start,200,(BASE/'static'/name).read_bytes(),allowed[name])
        configured=bool(self.db.configured and len(self.secret)>=32)
        if path=='/healthz':return self.reply(start,200 if configured else 503,dict(service='meucronograma',configured=configured))
        if not configured:
            if path.startswith('/api/'):raise HTTPError(503,'Configuração pendente: banco de dados e chave de segurança.')
            return self.reply(start,503,(BASE/'static/setup.html').read_text(),'text/html; charset=utf-8')
        self.db.initialize(self.owner,self.env.get('MASTER_PASSWORD',''),self.env.get('MAYRA_INITIAL_PASSWORD',''))
        if path=='/readyz' and method=='GET':
            with self.db.connection() as connection:
                self.db.execute(connection, 'SELECT 1').fetchone()
            return self.reply(start,200,dict(service='meucronograma',ready=True,version='2.8'))
        cookies=SimpleCookie()
        try:cookies.load(e.get('HTTP_COOKIE',''))
        except Exception:raise HTTPError(400,'Cookie inválido.')
        if method=='POST':
            origin=e.get('HTTP_ORIGIN')
            if origin:
                parsed=urlparse(origin)
                if parsed.netloc!=e.get('HTTP_HOST') or (not self.local and parsed.scheme!='https'):raise HTTPError(403,'Origem não autorizada.')
            if e.get('HTTP_SEC_FETCH_SITE')=='cross-site':raise HTTPError(403,'Origem não autorizada.')
        if path=='/login' and method=='GET':
            token=self.signed_login_token();return self.reply(start,200,self.login_page(csrf=token),'text/html; charset=utf-8',[self.cookie('hmay_login',token,3600)])
        if path=='/login' and method=='POST':
            data=self.body(e);cookie=cookies.get('hmay_login');token=data.get('csrf','')
            if not cookie or not hmac.compare_digest(token,cookie.value)or not self.valid_login_token(token):raise HTTPError(403,'Sessão do formulário expirou. Reabra a tela de login.')
            login=str(data.get('username','')).strip().lower()[:100];password=str(data.get('password',''))
            if len(password)>128:raise HTTPError(400,'Credenciais inválidas.')
            # Limite por login e um limite global por origem. Nunca grava a senha enviada.
            ip=e.get('HTTP_X_FORWARDED_FOR','').split(',')[-1].strip()or e.get('REMOTE_ADDR','local')
            keys=[('user:'+hashlib.sha256(login.encode()).hexdigest(),8),('ip:'+hashlib.sha256(ip.encode()).hexdigest(),40)]
            stamp=int(time.time());error='';new_session=None
            with self.db.connection(write=True)as c:
                for key,limit in keys:
                    self.db.execute(c,'INSERT INTO hmay_attempts(key,hits,until_at) VALUES (?,?,?) ON CONFLICT(key) DO NOTHING',(key,0,stamp+900))
                    row=self.db.execute(c,'SELECT hits,until_at FROM hmay_attempts WHERE key=?'+(''if self.db.local_path else ' FOR UPDATE'),(key,)).fetchone()
                    if row['until_at']<=stamp:self.db.execute(c,'UPDATE hmay_attempts SET hits=0,until_at=? WHERE key=?',(stamp+900,key))
                    elif row['hits']>=limit:error='Muitas tentativas. Aguarde 15 minutos antes de tentar novamente.'
                if not error:
                    user=self.db.execute(c,'SELECT * FROM hmay_users WHERE username=?',(login,)).fetchone()
                    stored=user['password']if user and user['password']!='!' else 'pbkdf2_sha256$600000$dummy$'+'0'*64
                    correct=password_ok(password,stored)
                    if user and correct and user['active'] and PROVISIONAL.expired(self,c,user):
                        error=PROVISIONAL.EXPIRED_MESSAGE
                    elif not user or not correct or not user['active']:
                        error='Login ou senha inválidos.'
                        for key,_ in keys:self.db.execute(c,'UPDATE hmay_attempts SET hits=hits+1 WHERE key=?',(key,))
                    else:
                        self.db.execute(c,'DELETE FROM hmay_attempts WHERE key=?',(keys[0][0],))
                        token=secrets.token_urlsafe(40);csrf=secrets.token_urlsafe(32);age=1209600 if data.get('remember')else 43200
                        self.db.execute(c,'DELETE FROM hmay_sessions WHERE expires<?',(stamp,))
                        self.db.execute(c,'INSERT INTO hmay_sessions(token_hash,user_id,csrf,expires) VALUES (?,?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),user['id'],csrf,stamp+age));new_session=(token,age)
                        self.event(c,user,user['id'],'login')
            if error:
                fresh=self.signed_login_token();return self.reply(start,429 if error.startswith('Muitas')else 401,self.login_page(error,fresh),'text/html; charset=utf-8',[self.cookie('hmay_login',fresh,3600)])
            return self.reply(start,303,'','text/html; charset=utf-8',[('Location','/'),self.cookie('hmay_session',new_session[0],new_session[1]),self.cookie('hmay_login','',0)])
        with self.db.connection(write=method=='POST')as c:
            user=self.current_user(c,cookies)
            if not user:
                if path.startswith('/api/'):raise HTTPError(401,'Sua sessão expirou. Entre novamente antes de salvar.')
                return self.reply(start,303,'','text/html; charset=utf-8',[('Location','/login')])
            if path=='/' and method=='GET':return self.reply(start,200,(BASE/'static/app.html').read_text(),'text/html; charset=utf-8')
            data=self.body(e)if method=='POST'else{}
            if method=='POST' and not hmac.compare_digest(str(e.get('HTTP_X_CSRF_TOKEN','')),user['csrf']):raise HTTPError(403,'Token de segurança inválido. Atualize a página.')
            if path=='/api/logout' and method=='POST':
                self.db.execute(c,'DELETE FROM hmay_sessions WHERE token_hash=?',(user['token_hash'],));return self.reply(start,200,dict(ok=True),headers=[self.cookie('hmay_session','',0)])
            if path!='/api/logout' and PROVISIONAL.expired(self,c,user):raise HTTPError(403,PROVISIONAL.EXPIRED_MESSAGE)
            if user['must_change'] and path not in ('/api/me','/api/password','/api/logout'):raise HTTPError(428,'Troque sua senha provisória antes de continuar.')
            if path=='/api/me' and method=='GET':return self.reply(start,200,dict(user=self.user_public(user),csrf=user['csrf'],serverDate=P.today(),databaseExpiration=self.env.get('DATABASE_EXPIRES_AT','')if user['role']=='master'else''))
            if path=='/api/password' and method=='POST':
                if not password_ok(str(data.get('current','')),user['password']):raise HTTPError(400,'A senha atual não confere.')
                new=valid_password(data.get('password'))
                if new!=data.get('confirm'):raise ValueError('A confirmação da senha não confere.')
                self.db.execute(c,'UPDATE hmay_users SET password=?,must_change=0 WHERE id=?',(password_hash(new),user['id']));PROVISIONAL.clear(self,c,user['id'])
                self.db.execute(c,'DELETE FROM hmay_sessions WHERE user_id=? AND token_hash<>?',(user['id'],user['token_hash']));self.event(c,user,user['id'],'change_password')
                return self.reply(start,200,dict(ok=True))
            query=parse_qs(e.get('QUERY_STRING',''));target=query.get('user',[user['id']])[0]
            if path.startswith('/api/provisional'):
                return PROVISIONAL.handle(self,c,user,path,method,data,query,start,HTTPError)
            if path.startswith('/api/enem-items/'):
                return ENEM_ITEMS.handle(self,c,user,path,method,data,query,start,HTTPError)
            if path.startswith('/api/disciplines/'):
                return DISCIPLINES.handle(self,c,user,path,method,data,query,start,HTTPError)
            if path.startswith('/api/school-reports/'):
                return SCHOOL_REPORTS.handle(self,c,user,path,method,data,query,start,HTTPError)
            if path.startswith('/api/motor/'):
                return MOTOR.handle(self,c,user,path,method,data,query,start,HTTPError)
            if path.startswith('/api/adaptive'):
                return ADAPT.handle(self,c,user,path,method,data,query,start,HTTPError)
            if path.startswith('/api/model-data'):
                return MODEL_DATA.handle(self,c,user,path,method,data,query,start,HTTPError)
            if path.startswith('/api/workbook'):
                return AREA_WORKBOOK.handle(self,c,user,path,method,data,query,start,HTTPError)
            if path.startswith('/api/exams'):
                return EXAMS.handle(self,c,user,path,method,data,query,start,HTTPError)
            if path.startswith('/api/performance'):
                return PERF.handle(self,c,user,path,method,data,query,start,HTTPError)
            if path=='/api/state' and method=='GET':return self.reply(start,200,self.state(c,user,target))
            if path=='/api/calendar' and method=='GET':
                self.require_target(user,target,c);state=self.state(c,user,target);w=P.week(query.get('week',[P.today()])[0]);p=state['profile']
                blocks=[b for i in range(7)for b in P.fixed_on(p,P.add(w,i))];return self.reply(start,200,dict(fixed=blocks))
            if path=='/api/action' and method=='POST':
                target=str(data.get('user')or user['id']);self.require_target(user,target,c)
                row=self.db.execute(c,'SELECT * FROM hmay_state WHERE user_id=?'+(''if self.db.local_path else ' FOR UPDATE'),(target,)).fetchone()
                if not row:raise HTTPError(404,'Conta não encontrada.')
                if type(data.get('version'))is not int or data['version']!=row['version']:raise HTTPError(409,'Outra sessão salvou alterações. Atualize a página antes de tentar novamente; esta alteração não foi gravada.')
                p=ADAPT.apply_action(self,c,user,target,json.loads(row['profile']),str(data.get('op','')),data.get('data',{}))
                if len(encode(p).encode())>MAX_BODY:raise ValueError('Perfil excede 5 MB. Exporte o histórico e contate o Master.')
                self.db.execute(c,'UPDATE hmay_state SET profile=?,version=version+1,updated_at=? WHERE user_id=?',(encode(p),P.now().isoformat(),target));self.event(c,user,target,'profile:'+data.get('op',''))
                return self.reply(start,200,self.state(c,user,target))
            if path=='/api/accounts/bulk-from-results':
                if user['role'] not in ('master','coordenador'):
                    raise HTTPError(403,'Cadastro em lote reservado ao Master e à coordenação.')
                if method!='POST':raise HTTPError(405,'Use o botão de cadastro em lote.')
                import model_data as BULK_MODEL_DATA
                parsed = BULK_MODEL_DATA._parse({
                    'file': data.get('file'),
                    'filename': data.get('filename',''),
                    'date': data.get('date',''),
                }, False)
                all_students = parsed.get('students', [])
                try:
                    offset = max(0, int(data.get('offset', 0) or 0))
                    raw_limit = data.get('limit')
                    limit = len(all_students) if raw_limit in (None, '') else max(1, min(50, int(raw_limit)))
                except (TypeError, ValueError):
                    raise ValueError('Intervalo do lote inválido.')
                selected_students = all_students[offset:offset + limit]
                try:
                    result = bulk_create_student_accounts(
                        self, c, user, selected_students, data.get('password')
                    )
                except PermissionError as exc:
                    raise HTTPError(403, str(exc))
                processed = len(selected_students)
                next_offset = min(len(all_students), offset + processed)
                result['historyYear']=_academic_year_active(self,c,user['id'])-1
                result['batch'] = {
                    'offset': offset, 'processed': processed,
                    'nextOffset': next_offset, 'total': len(all_students),
                    'done': next_offset >= len(all_students),
                }
                return self.reply(start,200,result)
            if path=='/api/academic-year':
                if method!='GET':raise HTTPError(405,'Use consulta GET.')
                target_id=query.get('user',[user['id']])[0]
                return self.reply(start,200,academic_year_status(self,c,user,target_id,HTTPError))
            if path=='/api/academic-year/open':
                if method!='POST':raise HTTPError(405,'Use POST para abrir o novo ano.')
                target_id=str(data.get('user') or '')
                result=academic_year_open(self,c,user,target_id,data.get('year'),HTTPError)
                return self.reply(start,200,result)
            if path=='/api/academic-year/switch':
                if method!='POST':raise HTTPError(405,'Use POST para alternar o ano.')
                target_id=str(data.get('user') or '')
                result=academic_year_switch(self,c,user,target_id,data.get('year'),HTTPError)
                return self.reply(start,200,result)
            if path=='/api/academic-year/comparison':
                if method!='GET':raise HTTPError(405,'Use consulta GET.')
                target_id=query.get('user',[user['id']])[0]
                return self.reply(start,200,academic_year_comparison(self,c,user,target_id,HTTPError))
            if path in ('/api/history/candidates','/api/history/search','/api/history/link','/api/history/link-profile'):
                if user['role'] not in ('master','coordenador'):raise HTTPError(403,'Acesso reservado à gestão.')
                year=_academic_year_active(self,c,user['id'])-1
                if path=='/api/history/candidates' and method=='GET':
                    return self.reply(start,200,dict(year=year,accounts=HISTORY.candidates(self,c,query.get('name',[''])[0].strip(),year)))
                target_id=data.get('target') if method=='POST' else query.get('target',[''])[0]
                student=_academic_year_target(self,c,user,target_id,HTTPError)
                if student['role'] not in ('user','aluno') or _academic_year_active(self,c,target_id)!=year+1:
                    raise ValueError('Selecione um aluno com o ciclo ativo em '+str(year+1)+'.')
                if path=='/api/history/search' and method=='GET':
                    return self.reply(start,200,dict(year=year,results=HISTORY.search(self,c,query.get('q',[''])[0],year,target_id)))
                if path=='/api/history/link-profile' and method=='POST':
                    HISTORY.link_on_creation(self,c,user,target_id,student['name'],data,year+1)
                    return self.reply(start,200,dict(ok=True))
                if path!='/api/history/link' or method!='POST':raise HTTPError(405,'Método inválido.')
                row=self.db.execute(c,"SELECT p.user_id FROM hmay_performance p JOIN hmay_users u ON u.id=p.user_id WHERE p.id=? AND p.applied_on LIKE ? AND u.role IN ('user','aluno','deleted')",(data.get('result'),str(year)+'-%')).fetchone()
                if not row or data.get('year')!=year:raise ValueError('Resultado indisponível para este ano.')
                HISTORY.link(self,c,user,target_id,year,row['user_id'],data['result'])
                return self.reply(start,200,dict(ok=True))
            if path=='/api/coordinator/accounts':
                # Dedicated create-only action. The existing Master administration
                # endpoint and target-account permissions remain unchanged.
                if user['role']!='coordenador':
                    raise HTTPError(403,'Cadastro reservado ao coordenador. O Master utiliza o Painel Master.')
                if method!='POST':raise HTTPError(405,'Use o formulário Cadastrar aluno.')
                if set(data)-{'username','name','password','role','historySource','historyYear'} or data.get('role','aluno')!='aluno':
                    raise HTTPError(403,'O coordenador pode criar somente contas de Aluno. Não pode alterar acessos existentes.')
                if not isinstance(data.get('username'),str) or not isinstance(data.get('name'),str):
                    raise ValueError('Informe o nome e o login do aluno.')
                login=username(data['username']);name=data['name'].strip()
                if not 1<=len(name)<=150:raise ValueError('Nome precisa ter de 1 a 150 caracteres.')
                password=valid_password(data.get('password'))
                if self.db.execute(c,'SELECT id FROM hmay_users WHERE username=?',(login,)).fetchone():
                    raise HTTPError(409,'Esse login já está em uso. Escolha outro login ou solicite revisão ao Master.')
                if self.db.execute(c,"SELECT COUNT(*) AS n FROM hmay_users WHERE role<>'deleted'").fetchone()['n']>=10000:
                    raise ValueError('Limite de 10.000 contas nesta versão.')
                target_id=P.uid();stamp=P.now().isoformat()
                # Conflict handling protects existing accounts even if two staff
                # members submit the same login concurrently.
                created=self.db.execute(c,'INSERT INTO hmay_users(id,username,name,password,role,active,must_change,created_at) VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(username) DO NOTHING',(target_id,login,name,password_hash(password),'aluno',1,1,stamp))
                if created.rowcount!=1:
                    raise HTTPError(409,'Esse login já está em uso. Escolha outro login ou solicite revisão ao Master.')
                profile=P.default_profile(name,target_id)
                self.db.execute(c,'INSERT INTO hmay_state(user_id,profile,version,updated_at) VALUES (?,?,?,?)',(target_id,encode(profile),1,stamp))
                set_student_creation_year(self,c,user['id'],target_id)
                HISTORY.link_on_creation(self,c,user,target_id,name,data,_academic_year_active(self,c,user['id']))
                self.event(c,user,target_id,'account_created_by_coordinator');PROVISIONAL.start(self,c,target_id,user['id'])
                return self.reply(start,200,dict(ok=True,id=target_id,username=login,role='aluno',must_change=True))
            if path=='/api/accounts/delete':
                if user['role']!='master':raise HTTPError(403,'Área exclusiva do Master.')
                if method!='POST':raise HTTPError(405,'Use POST.')
                target_id=data.get('id')
                lock='' if self.db.local_path else ' FOR UPDATE'
                account=self.db.execute(c,'SELECT username,role FROM hmay_users WHERE id=?'+lock,(target_id,)).fetchone()
                if not account:raise HTTPError(404,'Conta não encontrada.')
                if account['role']=='deleted':return self.reply(start,200,dict(ok=True))
                if target_id==user['id'] or account['username']==self.owner:
                    raise HTTPError(403,'Esta conta Master está protegida.')
                if account['username']!=data.get('username'):
                    raise HTTPError(409,'Confira o login antes de excluir.')
                self.db.execute(c,"UPDATE hmay_users SET role='deleted',active=0,password='!',must_change=0,username=? WHERE id=?",('deleted:'+target_id,target_id))
                self.db.execute(c,'DELETE FROM hmay_sessions WHERE user_id=?',(target_id,))
                self.event(c,user,target_id,'account_deleted')
                return self.reply(start,200,dict(ok=True))
            if path=='/api/accounts/reset-password':
                if user['role']!='master':raise HTTPError(403,'Área exclusiva do Master.')
                if method!='POST':raise HTTPError(405,'Use POST.')
                account=self.db.execute(c,"SELECT id,username FROM hmay_users WHERE id=? AND role<>'deleted'"+('' if self.db.local_path else ' FOR UPDATE'),(data.get('id'),)).fetchone()
                if not account:raise HTTPError(404,'Conta não encontrada.')
                if account['id']==user['id'] or account['username']==self.owner:
                    raise HTTPError(403,'Use Minha senha na própria conta.')
                password=password_hash(valid_password(data.get('password','')))
                self.db.execute(c,'UPDATE hmay_users SET password=?,must_change=1 WHERE id=?',(password,account['id']))
                self.db.execute(c,'DELETE FROM hmay_sessions WHERE user_id=?',(account['id'],))
                PROVISIONAL.start_if_student(self,c,account['id'],user['id'])
                self.event(c,user,account['id'],'password_reset')
                return self.reply(start,200,dict(ok=True))
            if path=='/api/accounts/enroll':
                if user['role']!='master':raise HTTPError(403,'Área exclusiva do Master.')
                if method!='POST':raise HTTPError(405,'Use POST para matricular o aluno.')
                target_id=str(data.get('id') or '')
                if target_id==user['id']:raise HTTPError(400,'Selecione uma conta de aluno.')
                year=_academic_year_active(self,c,user['id'])
                if data.get('year')!=year:raise HTTPError(409,'O ano letivo mudou. Atualize o painel.')
                return self.reply(start,200,academic_year_open(self,c,user,target_id,year,HTTPError,registration=True))
            if path=='/api/accounts':
                if user['role']=='coordenador' and method=='GET':
                    year=_academic_year_active(self,c,user['id'])
                    rows=self.db.execute(c,'''SELECT u.id,u.username,u.name,u.role,u.active,u.must_change
                        FROM hmay_users u LEFT JOIN hmay_academic_year y ON y.user_id=u.id
                        WHERE u.active=1 AND (u.id=? OR (u.role IN ('user','aluno') AND
                        (COALESCE(y.active_year,CAST(substr(u.created_at,1,4) AS INTEGER))=?
                        OR EXISTS (SELECT 1 FROM hmay_academic_cycles cy WHERE cy.user_id=u.id AND cy.academic_year=?))))
                        ORDER BY u.name,u.username''',(user['id'],year,year)).fetchall()
                    return self.reply(start,200,dict(accounts=[self.user_public(row) for row in rows],academicYear=year))
                if user['role']!='master':raise HTTPError(403,'Área exclusiva do Master.')
                if method=='GET':
                    return self.reply(start,200,master_accounts(self,c,user))
                login=username(data.get('username',''));name=str(data.get('name','')).strip()
                if not 1<=len(name)<=150:raise ValueError('Nome precisa ter de 1 a 150 caracteres.')
                target_id=data.get('id');password=data.get('password','')
                role=data.get('role')
                if role is not None and role not in ('master','coordenador','especial','aluno','user'):raise ValueError('Perfil de acesso inválido.')
                if target_id:
                    old=self.db.execute(c,"SELECT * FROM hmay_users WHERE id=? AND role<>'deleted'"+('' if self.db.local_path else ' FOR UPDATE'),(target_id,)).fetchone()
                    if not old:raise HTTPError(404,'Conta não encontrada.')
                    if login!=old['username']:raise ValueError('O login de uma conta existente não pode ser alterado.')
                    active=bool(data.get('active',True))
                    role=role or old['role']
                    if old['username']==self.owner and role!='master':raise ValueError('arcmb permanece Master.')
                    if old['username']==self.owner and not active:raise ValueError('O Master proprietário não pode ser desativado.')
                    if old['username']==self.owner and password:raise ValueError('Use “Minha senha” para alterar a senha do Master proprietário.')
                    self.db.execute(c,'UPDATE hmay_users SET name=?,active=?,role=? WHERE id=?',(name,int(active),role,target_id))
                    if password:
                        self.db.execute(c,'UPDATE hmay_users SET password=?,must_change=1 WHERE id=?',(password_hash(valid_password(password)),target_id));PROVISIONAL.start_if_student(self,c,target_id,user['id'])
                    if password or not active or role!=old['role']:self.db.execute(c,'DELETE FROM hmay_sessions WHERE user_id=?',(target_id,))
                    # Mudar o nome também incrementa versão e evita gravação concorrente silenciosa.
                    row=self.db.execute(c,'SELECT profile FROM hmay_state WHERE user_id=?'+(''if self.db.local_path else ' FOR UPDATE'),(target_id,)).fetchone();p=json.loads(row['profile']);p['name']=name
                    self.db.execute(c,'UPDATE hmay_state SET profile=?,version=version+1,updated_at=? WHERE user_id=?',(encode(p),P.now().isoformat(),target_id))
                    self.event(c,user,target_id,'account_updated')
                else:
                    if self.db.execute(c,'SELECT id FROM hmay_users WHERE username=?',(login,)).fetchone():raise ValueError('Esse login já está cadastrado.')
                    if self.db.execute(c,"SELECT COUNT(*) AS n FROM hmay_users WHERE role<>'deleted'").fetchone()['n']>=10000:raise ValueError('Limite de 10.000 contas nesta versão.')
                    target_id=self.db.create_user(c,login,name,valid_password(password),role or 'user')
                    if role in (None,'user','aluno'):
                        set_student_creation_year(self,c,user['id'],target_id)
                        HISTORY.link_on_creation(self,c,user,target_id,name,data,_academic_year_active(self,c,user['id']))
                    self.event(c,user,target_id,'account_created')
                    PROVISIONAL.start_if_student(self,c,target_id,user['id'])
                return self.reply(start,200,dict(ok=True,id=target_id))
            if path=='/api/audit' and method=='GET':
                if user['role']!='master':raise HTTPError(403,'Área exclusiva do Master.')
                rows=self.db.execute(c,'SELECT e.kind,e.at,a.username AS actor,t.username AS target FROM hmay_events e LEFT JOIN hmay_users a ON a.id=e.actor_id LEFT JOIN hmay_users t ON t.id=e.target_id ORDER BY e.at DESC LIMIT 100').fetchall()
                return self.reply(start,200,dict(events=[dict(x)for x in rows]))
            if path=='/api/backup' and method=='GET':
                self.require_target(user,target,c)
                if query.get('all',[''])[0]=='1':
                    if user['role']!='master':raise HTTPError(403,'Área exclusiva do Master.')
                    profiles=[json.loads(x['profile'])for x in self.db.execute(c,'SELECT profile FROM hmay_state').fetchall()]
                else:profiles=[self.state(c,user,target)['profile']]
                backup=dict(app='ritmo-local',version=1,exportedAt=P.now().isoformat(),scope='all'if len(profiles)>1 else'profile',profiles=profiles)
                return self.reply(start,200,backup,headers=[('Content-Disposition',f'attachment; filename="Meu_Cronograma_{P.today()}.json"')])
            raise HTTPError(404,'Página não encontrada.')

application=App()
if __name__=='__main__':
    from wsgiref.simple_server import make_server
    port=int(os.environ.get('PORT','8765'))
    print(f'Meu Cronograma: http://127.0.0.1:{port} — teste local, não use este servidor em produção.')
    make_server('127.0.0.1',port,application).serve_forever()
