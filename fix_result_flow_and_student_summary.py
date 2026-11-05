"""Fix the bulk-account reader, export list and add an individual student summary.

This release runs after the result import/export and bulk-account releases.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / 'static'
MARKER = '# === MEU CRONOGRAMA: RESUMO INDIVIDUAL DO ALUNO ==='
JS_NAME = 'student_summary.js'
JS_URL = '/static/student_summary.js?v=2.8.7'
JS_MIME = "'student_summary.js':'application/javascript; charset=utf-8'"

BACKEND = r'''

# === MEU CRONOGRAMA: RESUMO INDIVIDUAL DO ALUNO ===
def _ss_num(value):
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _ss_target(app, c, user, query, HTTPError):
    raw = query.get('user', ['']) if isinstance(query, dict) else ['']
    target_id = F.text(raw[0] if raw else '', 100) or user['id']
    row = app.db.execute(
        c, 'SELECT id,username,name,role,active FROM hmay_users WHERE id=?', (target_id,)
    ).fetchone()
    if not row:
        raise HTTPError(404, 'Aluno não encontrado.')
    account = dict(row)
    if target_id != user['id']:
        if user.get('role') == 'master':
            pass
        elif user.get('role') == 'coordenador' and account.get('role') in ('user', 'aluno') and account.get('active'):
            pass
        else:
            raise HTTPError(403, 'Você não pode consultar esse perfil.')
    return account


def _ss_profile_summary(profile):
    subjects = profile.get('subjects') if isinstance(profile.get('subjects'), list) else []
    contents = profile.get('contents') if isinstance(profile.get('contents'), list) else []
    feedback = profile.get('feedback') if isinstance(profile.get('feedback'), list) else []
    by_subject = {}
    subject_names = {}
    for subject in subjects:
        if not isinstance(subject, dict):
            continue
        sid = F.text(subject.get('id'), 100)
        name = F.text(subject.get('name'), 150) or 'Sem disciplina'
        if sid:
            subject_names[sid] = name
        by_subject.setdefault(name, {
            'name': name, 'contents': 0, 'studied': 0, 'plannedMinutes': 0,
            'actualMinutes': 0, 'paused': 0,
        })
    content_subject = {}
    recent = []
    for content in contents:
        if not isinstance(content, dict):
            continue
        sid = F.text(content.get('subjectId'), 100)
        name = subject_names.get(sid, 'Sem disciplina')
        bucket = by_subject.setdefault(name, {
            'name': name, 'contents': 0, 'studied': 0, 'plannedMinutes': 0,
            'actualMinutes': 0, 'paused': 0,
        })
        bucket['contents'] += 1
        if F.text(content.get('status'), 40).lower() == 'studied':
            bucket['studied'] += 1
        if content.get('paused'):
            bucket['paused'] += 1
        bucket['plannedMinutes'] += max(0, _ss_num(content.get('studyMinutes')))
        cid = F.text(content.get('id'), 100)
        if cid:
            content_subject[cid] = name
        recent.append({
            'title': F.text(content.get('title'), 250) or 'Conteúdo sem título',
            'topic': F.text(content.get('topic'), 250),
            'subject': name,
            'status': F.text(content.get('status'), 40) or 'planned',
            'studiedOn': F.text(content.get('studiedOn'), 40),
            'nextDue': F.text(content.get('nextDue'), 40),
            'difficulty': _ss_num(content.get('difficulty')),
        })
    actual_total = 0
    for item in feedback:
        if not isinstance(item, dict):
            continue
        minutes = max(0, _ss_num(item.get('actualMin')))
        actual_total += minutes
        name = content_subject.get(F.text(item.get('contentId'), 100), 'Sem disciplina')
        bucket = by_subject.setdefault(name, {
            'name': name, 'contents': 0, 'studied': 0, 'plannedMinutes': 0,
            'actualMinutes': 0, 'paused': 0,
        })
        bucket['actualMinutes'] += minutes
    recent.sort(key=lambda x: (x.get('studiedOn') or x.get('nextDue') or '', F.norm(x.get('title'))), reverse=True)
    rows = sorted(by_subject.values(), key=lambda x: F.norm(x['name']))
    return {
        'subjects': len([x for x in subjects if isinstance(x, dict) and x.get('active', True)]),
        'contents': len([x for x in contents if isinstance(x, dict)]),
        'studied': sum(x['studied'] for x in rows),
        'paused': sum(x['paused'] for x in rows),
        'plannedMinutes': sum(x['plannedMinutes'] for x in rows),
        'actualMinutes': actual_total,
        'bySubject': rows,
        'recentContents': recent[:12],
    }


def _ss_rollup_add(target, source):
    for item in source:
        name = F.text(item.get('name'), 300) or 'Não informado'
        bucket = target.setdefault(name, {
            'name': name, 'correct': 0, 'errors': 0, 'marked': 0, 'total': 0,
        })
        for key in ('correct', 'errors', 'marked', 'total'):
            bucket[key] += max(0, _ss_num(item.get(key)))


def _ss_rollup_rows(values):
    rows = []
    for item in values.values():
        marked = item['marked']
        total = item['total']
        item['accuracy'] = None if not marked else round(100 * item['correct'] / marked, 2)
        item['coverage'] = None if not total else round(100 * marked / total, 2)
        rows.append(item)
    return sorted(rows, key=lambda x: (-x['marked'], F.norm(x['name'])))


def student_summary(app, c, user, target):
    state_row = app.db.execute(c, 'SELECT profile FROM hmay_state WHERE user_id=?', (target['id'],)).fetchone()
    profile = _rx_json(state_row['profile']) if state_row else {}
    study = _ss_profile_summary(profile)
    performance_rows = app.db.execute(
        c,
        'SELECT * FROM hmay_performance WHERE user_id=? ORDER BY applied_on DESC,activity',
        (target['id'],),
    ).fetchall()
    exam_cache = {}
    simulations = []
    aggregate = {kind: {} for kind in _RX_GROUP_KINDS}
    total_correct = total_errors = total_marked = total_valid = 0
    for raw in performance_rows:
        row = dict(raw)
        metadata = _rx_json(row.get('metadata'))
        exam_id = metadata.get('_exam_id')
        if not exam_id:
            continue
        if exam_id not in exam_cache:
            exam_cache[exam_id] = E.get_exam(app, c, exam_id)
        exam = exam_cache.get(exam_id)
        if not exam:
            continue
        analysis = _rx_analyse(exam, _rx_json(row.get('metrics')), metadata)
        overall = analysis['overall']
        total_correct += overall['correct']
        total_errors += overall['errors']
        total_marked += overall['marked']
        total_valid += overall['total']
        for kind in _RX_GROUP_KINDS:
            _ss_rollup_add(aggregate[kind], analysis['groups'][kind])
        simulations.append({
            'activity': row.get('activity', ''),
            'date': row.get('applied_on', ''),
            'color': F.text(metadata.get('COR DA PROVA'), 80),
            'language': F.text(metadata.get('L.E'), 40),
            'correct': overall['correct'],
            'errors': overall['errors'],
            'marked': overall['marked'],
            'valid': overall['total'],
            'accuracy': overall['accuracy'],
            'coverage': overall['coverage'],
            'areas': analysis['groups']['Área'],
            'disciplines': analysis['groups']['Disciplina'],
        })
    simulations.sort(key=lambda x: (x['date'], F.norm(x['activity'])), reverse=True)
    return {
        'student': {
            'id': target['id'], 'name': target['name'], 'username': target['username'],
        },
        'study': study,
        'performance': {
            'simulations': len(simulations),
            'correct': total_correct,
            'errors': total_errors,
            'marked': total_marked,
            'valid': total_valid,
            'accuracy': None if not total_marked else round(100 * total_correct / total_marked, 2),
            'coverage': None if not total_valid else round(100 * total_marked / total_valid, 2),
        },
        'simulations': simulations,
        'aggregates': {
            'area': _ss_rollup_rows(aggregate['Área']),
            'discipline': _ss_rollup_rows(aggregate['Disciplina']),
            'topic': _ss_rollup_rows(aggregate['Tópico']),
            'subject': _ss_rollup_rows(aggregate['Assunto']),
            'skill': _ss_rollup_rows(aggregate['Habilidade']),
        },
    }


_ss_original_handle = handle


def handle(app, c, user, path, method, data, query, start, HTTPError):
    if path == '/api/model-data/student-summary' and method == 'GET':
        target = _ss_target(app, c, user, query, HTTPError)
        return app.reply(start, 200, student_summary(app, c, user, target))
    return _ss_original_handle(app, c, user, path, method, data, query, start, HTTPError)
'''

JS_SOURCE = r'''"use strict";
// Resumo individual integrado à página Desempenho.
let studentSummaryCache=new Map();
let studentSummaryLoading=new Set();

function studentSummaryTarget(){return (typeof target!=='undefined'&&target)||(typeof P!=='undefined'&&P?.id)||(typeof ME!=='undefined'&&ME?.id)||'';}
function studentSummaryPercent(value){return value===null||value===undefined?'—':Number(value).toLocaleString('pt-BR',{minimumFractionDigits:1,maximumFractionDigits:1})+'%';}
function studentSummaryMinutes(value){const n=Number(value||0);if(n<60)return n+' min';const h=Math.floor(n/60),m=n%60;return h+'h'+(m?' '+m+'min':'');}
function studentSummaryRows(rows,limit=12){return (rows||[]).slice(0,limit).map(x=>`<tr><td>${esc(x.name)}</td><td>${x.correct||0}</td><td>${x.errors||0}</td><td>${studentSummaryPercent(x.accuracy)}</td><td>${x.marked||0}/${x.total||0}</td></tr>`).join('');}

async function loadStudentSummary(force=false){
 const id=studentSummaryTarget();if(!id)return;
 if(studentSummaryLoading.has(id))return;
 if(studentSummaryCache.has(id)&&!force)return;
 studentSummaryLoading.add(id);
 try{studentSummaryCache.set(id,await api('/api/model-data/student-summary?user='+encodeURIComponent(id)));}
 catch(err){studentSummaryCache.set(id,{error:err.message||'Não foi possível carregar o resumo.'});}
 finally{studentSummaryLoading.delete(id);if(view==='performance')render();}
}

function studentSummaryPanel(){
 const id=studentSummaryTarget();
 if(!studentSummaryCache.has(id)&&!studentSummaryLoading.has(id))queueMicrotask(()=>loadStudentSummary());
 if(studentSummaryLoading.has(id)||!studentSummaryCache.has(id))return `<section class="card"><h2>Resumo individual</h2><p>Carregando trajetória acadêmica…</p></section>`;
 const d=studentSummaryCache.get(id);if(d?.error)return `<section class="card"><h2>Resumo individual</h2><div class="notice warning">${esc(d.error)}</div>${button('Tentar novamente','student-summary-refresh','secondary')}</section>`;
 const s=d.study||{},p=d.performance||{};
 const subjects=(s.bySubject||[]).map(x=>`<tr><td>${esc(x.name)}</td><td>${x.studied||0}/${x.contents||0}</td><td>${studentSummaryMinutes(x.actualMinutes||0)}</td><td>${studentSummaryMinutes(x.plannedMinutes||0)}</td></tr>`).join('');
 const sims=(d.simulations||[]).map(x=>`<tr><td>${esc(x.activity)}</td><td>${esc(x.date)}</td><td>${esc(x.color||'—')}</td><td>${x.correct||0}/${x.valid||0}</td><td>${studentSummaryPercent(x.accuracy)}</td></tr>`).join('');
 const recent=(s.recentContents||[]).map(x=>`<li><strong>${esc(x.title)}</strong>${x.subject?' · '+esc(x.subject):''}${x.topic?' · '+esc(x.topic):''}<br><small>${x.status==='studied'?'Estudado':'Planejado'}${x.studiedOn?' em '+esc(x.studiedOn):''}</small></li>`).join('');
 return `<section class="card student-summary-card"><div class="item"><div><h2>Resumo individual de ${esc(d.student?.name||'aluno')}</h2><p>Conteúdos, tempo registrado e simulados consolidados no mesmo perfil.</p></div><div class="item-actions">${button('Atualizar resumo','student-summary-refresh','secondary')}</div></div><div class="stats"><div class="stat"><strong>${s.studied||0}/${s.contents||0}</strong><span>conteúdos estudados</span></div><div class="stat"><strong>${p.simulations||0}</strong><span>simulados</span></div><div class="stat"><strong>${p.correct||0}</strong><span>acertos acumulados</span></div><div class="stat"><strong>${studentSummaryPercent(p.accuracy)}</strong><span>aproveitamento</span></div><div class="stat"><strong>${studentSummaryMinutes(s.actualMinutes||0)}</strong><span>tempo registrado</span></div></div>${subjects?`<h3>Estudo por disciplina</h3><div class="table-wrap"><table><thead><tr><th>Disciplina</th><th>Conteúdos estudados</th><th>Tempo realizado</th><th>Tempo planejado</th></tr></thead><tbody>${subjects}</tbody></table></div>`:'<div class="notice">Ainda não há conteúdos de estudo cadastrados.</div>'}${sims?`<h3>Simulados realizados</h3><div class="table-wrap"><table><thead><tr><th>Simulado</th><th>Data</th><th>Cor</th><th>Acertos</th><th>Aproveitamento</th></tr></thead><tbody>${sims}</tbody></table></div>`:'<div class="notice">Ainda não há simulados associados a este perfil.</div>'}${(d.aggregates?.area||[]).length?`<h3>Desempenho acumulado por área</h3><div class="table-wrap"><table><thead><tr><th>Área</th><th>Acertos</th><th>Erros</th><th>Aproveitamento</th><th>Cobertura</th></tr></thead><tbody>${studentSummaryRows(d.aggregates.area)}</tbody></table></div>`:''}${(d.aggregates?.discipline||[]).length?`<h3>Desempenho acumulado por disciplina</h3><div class="table-wrap"><table><thead><tr><th>Disciplina</th><th>Acertos</th><th>Erros</th><th>Aproveitamento</th><th>Cobertura</th></tr></thead><tbody>${studentSummaryRows(d.aggregates.discipline,30)}</tbody></table></div>`:''}${recent?`<details><summary>Conteúdos mais recentes</summary><ul>${recent}</ul></details>`:''}<details><summary>Detalhamento por tópico, assunto e habilidade</summary>${['topic','subject','skill'].map(k=>{const title={topic:'Tópicos',subject:'Assuntos',skill:'Habilidades'}[k],rows=studentSummaryRows(d.aggregates?.[k]||[],40);return rows?`<h4>${title}</h4><div class="table-wrap"><table><thead><tr><th>Classificação</th><th>Acertos</th><th>Erros</th><th>Aproveitamento</th><th>Cobertura</th></tr></thead><tbody>${rows}</tbody></table></div>`:'';}).join('')}</details></section>`;
}

acts['student-summary-refresh']=async()=>{await loadStudentSummary(true);};

if(typeof performanceView==='function'){
 const studentSummaryOriginalPerformanceView=performanceView;
 performanceView=function(){
  const base=studentSummaryOriginalPerformanceView();
  const panel=studentSummaryPanel();
  const marker='<section class="card"';
  const pos=base.indexOf(marker);
  return pos>=0?base.slice(0,pos)+panel+base.slice(pos):base+panel;
 };
}
'''


def insert_mime(source):
    if JS_MIME in source:
        return source
    matches=list(re.finditer(r"'[^'\n]+\.js'\s*:\s*'application/javascript; charset=utf-8'", source))
    if not matches:
        raise RuntimeError('Lista de JavaScript estático não encontrada.')
    anchor=matches[-1]
    return source[:anchor.end()]+','+JS_MIME+source[anchor.end():]


def main():
    # Fix the disabled reader after a file has been selected.
    bulk_path=STATIC/'bulk_accounts_panel.js'
    bulk=bulk_path.read_text(encoding='utf-8')
    old="  const create=document.querySelector('[data-act=\"bulk-accounts-create\"]');if(create)create.disabled=true;\n  bulkAccountsSetStatus(1,'Arquivo selecionado. Clique em Ler e conferir arquivo.','success');"
    new="  const create=document.querySelector('[data-act=\"bulk-accounts-create\"]');if(create)create.disabled=true;\n  const inspect=document.querySelector('[data-act=\"bulk-accounts-inspect\"]');if(inspect)inspect.disabled=false;\n  bulkAccountsSetStatus(1,'Arquivo selecionado. Clique em Ler e conferir arquivo.','success');"
    if old in bulk:
        bulk=bulk.replace(old,new,1)
    elif "if(inspect)inspect.disabled=false" not in bulk:
        raise RuntimeError('Trecho do botão Ler e conferir não encontrado.')
    bulk_path.write_text(bulk,encoding='utf-8')

    model_path=ROOT/'model_data.py'
    model=model_path.read_text(encoding='utf-8')
    model=model.replace("if row.get('student_role') != 'user':", "if row.get('student_role') not in ('user', 'aluno'):")
    if MARKER not in model:
        model += BACKEND
    model_path.write_text(model,encoding='utf-8')

    (STATIC/JS_NAME).write_text(JS_SOURCE,encoding='utf-8')
    html_path=STATIC/'app.html';html=html_path.read_text(encoding='utf-8')
    if JS_URL not in html:
        html=html.replace('</body>',f'<script src="{JS_URL}" defer></script>\n</body>',1)
    html_path.write_text(html,encoding='utf-8')
    web_path=ROOT/'webapp.py';web_path.write_text(insert_mime(web_path.read_text(encoding='utf-8')),encoding='utf-8')
    print('MEUCRONOGRAMA_STUDENT_SUMMARY_READY: reader, export list and individual summary prepared.',flush=True)

if __name__=='__main__':
    main()
