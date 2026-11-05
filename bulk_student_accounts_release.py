"""Add bulk student-account creation to the two-tab result importer.

Master and Coordinator can create all missing student accounts from the
DADOS DOS ALUNOS sheet, using a provisional password supplied in the UI.
Existing accounts are preserved and matched by normalized full name.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
PY_MARKER = '# === MEU CRONOGRAMA: CADASTRO EM LOTE A PARTIR DOS RESULTADOS ==='
JS_MARKER = '// === MEU CRONOGRAMA: CADASTRO EM LOTE DE ALUNOS ==='


def replace_once(text, old, new, label):
    if old not in text:
        raise RuntimeError(f'{label}: trecho esperado não encontrado.')
    return text.replace(old, new, 1)


PY_HELPERS = r'''

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
    if not isinstance(students, list) or not students:
        raise ValueError('O arquivo não possui alunos para cadastrar.')
    if len(students) > 5000:
        raise ValueError('O cadastro em lote aceita até 5.000 linhas por arquivo.')

    rows = app.db.execute(
        c,
        'SELECT id,username,name,role,active FROM hmay_users ORDER BY name,username'
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
    account_count = int(app.db.execute(c, 'SELECT COUNT(*) AS n FROM hmay_users').fetchone()['n'])

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
            (target_id, login, name, password_hash(password), 'aluno', 1, 1, stamp),
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
        app.event(c, user, target_id, 'account_created_bulk_results')
        created.append({
            'name': name,
            'username': login,
            'id': target_id,
            'generatedLogin': generated,
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
'''


PY_ROUTE = r'''            if path=='/api/accounts/bulk-from-results':
                if user['role'] not in ('master','coordenador'):
                    raise HTTPError(403,'Cadastro em lote reservado ao Master e à coordenação.')
                if method!='POST':raise HTTPError(405,'Use o botão de cadastro em lote.')
                import model_data as BULK_MODEL_DATA
                parsed = BULK_MODEL_DATA._parse({
                    'file': data.get('file'),
                    'filename': data.get('filename',''),
                    'date': data.get('date',''),
                }, False)
                try:
                    result = bulk_create_student_accounts(
                        self, c, user, parsed.get('students', []), data.get('password')
                    )
                except PermissionError as exc:
                    raise HTTPError(403, str(exc))
                return self.reply(start,200,result)
'''


JS_APPENDIX = r'''

// === MEU CRONOGRAMA: CADASTRO EM LOTE DE ALUNOS ===
let resultImportBulkResult=null;
let resultImportBulkPassword='';

function resultImportBulkResultHtml(){
 const r=resultImportBulkResult;
 if(!r)return '';
 const s=r.summary||{};
 const conflicts=(r.conflicts||[]).slice(0,20).map(x=>`<li><strong>${esc(x.name)}</strong>: ${esc(x.reason)}</li>`).join('');
 const more=(r.conflicts||[]).length>20?`<p class="micro">Mais ${(r.conflicts||[]).length-20} conflito(s) não exibido(s).</p>`:'';
 return `<div class="notice ${s.conflicts?'warning':''}"><strong>${s.created||0} conta(s) criada(s); ${s.existing||0} já existente(s); ${s.conflicts||0} conflito(s).</strong>${s.duplicateRows?`<p>${s.duplicateRows} linha(s) repetida(s) no arquivo foram ignoradas.</p>`:''}${conflicts?`<ul>${conflicts}</ul>${more}`:''}${(r.created||[]).length?`<div class="actions">${button('Baixar lista de acessos','result-import-bulk-download','secondary')}</div><p class="micro">O arquivo de acessos contém a senha provisória comum definida nesta tela. Trate-o como informação confidencial.</p>`:''}</div>`;
}

function resultImportBulkAccountsPanel(){
 return `<section class="card" style="margin-top:1rem"><h3>Cadastrar contas ausentes em lote</h3><p>O sistema usa os nomes da aba <strong>DADOS DOS ALUNOS</strong>. Contas existentes são preservadas; para novos alunos, o login da planilha será usado ou será gerado automaticamente.</p><div class="form-grid">${input('Senha provisória comum para os novos alunos','result-import-bulk-password','','password','required minlength="8" maxlength="128" autocomplete="new-password"')}</div><div class="actions">${button('Criar contas ausentes e vincular','result-import-bulk-create','primary')}${button('?','result-import-bulk-help','secondary','aria-label="Explicar cadastro em lote" title="Explicar cadastro em lote"')}</div><p class="micro">Todos os novos usuários serão do perfil Aluno, ativos e obrigados a trocar a senha no primeiro acesso.</p><div id="result-import-bulk-output">${resultImportBulkResultHtml()}</div></section>`;
}

acts['result-import-bulk-help']=()=>modal(
 'Cadastro de alunos em lote',
 '<p>O arquivo atual será lido novamente. Para cada nome que ainda não possuir uma conta de Aluno, o sistema criará uma conta ativa.</p><p>Se a coluna LOGIN estiver preenchida, ela será usada. Quando estiver vazia, o login será gerado a partir do primeiro e do último nome, com numeração automática em caso de repetição.</p><p>A senha provisória é comum ao lote e deve ter pelo menos 8 caracteres. Cada aluno será obrigado a trocá-la no primeiro acesso.</p>',
 null
);

acts['result-import-bulk-create']=async()=>{
 if(!resultImportDraft?.file)throw new Error('Selecione e leia o arquivo antes de cadastrar os alunos.');
 const field=document.querySelector('[name=result-import-bulk-password]');
 const password=field?.value||'';
 if(password.length<8||password.length>128)throw new Error('A senha provisória deve ter de 8 a 128 caracteres.');
 const rows=resultImportDraft.inspection?.rows||0;
 if(!confirm(`Criar as contas de Aluno ausentes entre ${rows} participante(s), usando a senha provisória informada?`))return;
 const base=resultImportPayload();
 const result=await api('/api/accounts/bulk-from-results',{
  file:base.file,filename:base.filename,date:base.date,password
 });
 resultImportBulkResult=result;
 resultImportBulkPassword=password;
 if(field)field.value='';
 const inspection=resultImportDraft.inspection;
 const previewPayload={...base,mapping:{}};
 const preview=await api('/api/model-data/preview',previewPayload);
 resultImportDraft={...previewPayload,inspection,preview,token:preview.token,mapping:preview.mapping};
 const inspectionBox=$('#result-import-inspection');if(inspectionBox)inspectionBox.innerHTML=resultImportInspection(inspection);
 const previewBox=$('#result-import-preview');if(previewBox)previewBox.innerHTML=resultImportPreview(preview);
 toast(`${result.summary.created||0} conta(s) criada(s). ${preview.summary.linked||0} aluno(s) vinculado(s) na nova prévia.`);
};

acts['result-import-bulk-download']=()=>{
 const rows=resultImportBulkResult?.created||[];
 if(!rows.length)throw new Error('Nenhuma conta nova foi criada neste lote.');
 if(!resultImportBulkPassword)throw new Error('A senha provisória não está mais disponível nesta sessão.');
 csv('Acessos_provisorios_alunos.csv',[
  ['Nome','Login','Senha provisória','Troca obrigatória no primeiro acesso'],
  ...rows.map(x=>[x.name,x.username,resultImportBulkPassword,'SIM'])
 ]);
};
'''


def patch_python():
    path = ROOT / 'webapp.py'
    source = path.read_text(encoding='utf-8')
    if PY_MARKER not in source:
        source = replace_once(source, '\nclass App:\n', PY_HELPERS + '\n\nclass App:\n', 'helpers do cadastro em lote')
        source = replace_once(
            source,
            "            if path=='/api/coordinator/accounts':\n",
            PY_ROUTE + "            if path=='/api/coordinator/accounts':\n",
            'rota do cadastro em lote',
        )
        path.write_text(source, encoding='utf-8')


def patch_javascript():
    path = ROOT / 'static' / 'result_import.js'
    source = path.read_text(encoding='utf-8')
    if JS_MARKER not in source:
        old = "<p class=\"micro\">O sistema recalcula acertos e percentuais pelas respostas e pelo gabarito. A coluna % ACERTOS da planilha, quando existir, é apenas informativa.</p>${button('Vincular alunos e gerar prévia','result-import-preview','primary')}"
        new = "<p class=\"micro\">O sistema recalcula acertos e percentuais pelas respostas e pelo gabarito. A coluna % ACERTOS da planilha, quando existir, é apenas informativa.</p>${resultImportBulkAccountsPanel()}${button('Vincular alunos e gerar prévia','result-import-preview','primary')}"
        source = replace_once(source, old, new, 'painel de cadastro em lote')
        source = source.replace(
            "  resultImportLastSummary=null;\n",
            "  resultImportLastSummary=null;resultImportBulkResult=null;resultImportBulkPassword='';\n",
            1,
        )
        source += JS_APPENDIX
        path.write_text(source, encoding='utf-8')

    html_path = ROOT / 'static' / 'app.html'
    html = html_path.read_text(encoding='utf-8')
    html = re.sub(r'/static/result_import\.js\?v=[^\"\s<]+', '/static/result_import.js?v=2.8.5', html, count=1)
    html_path.write_text(html, encoding='utf-8')


def main():
    patch_python()
    patch_javascript()
    print('MEUCRONOGRAMA_BULK_STUDENT_ACCOUNTS_READY: bulk account creation and automatic re-linking prepared.', flush=True)


if __name__ == '__main__':
    main()
