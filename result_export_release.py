"""Add collective converted-result export by imported simulation.

Runs after the two-tab result model release. It reuses the converted question
metrics already persisted by the importer and adds a manager-only export page.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
PY_MARKER = '# === MEU CRONOGRAMA: EXPORTAÇÃO COLETIVA POR SIMULADO ==='
JS_MIME = "'result_export.js':'application/javascript; charset=utf-8'"
JS_URL = '/static/result_export.js?v=2.8.3'

PY_EXTENSION = r'''

# === MEU CRONOGRAMA: EXPORTAÇÃO COLETIVA POR SIMULADO ===
_RX_AREA_LABELS = {
    'LC': 'Linguagens',
    'CH': 'Humanas',
    'CN': 'Natureza',
    'MT': 'Matemática',
}
_RX_GROUP_KINDS = ('Área', 'Disciplina', 'Tópico', 'Assunto', 'Habilidade')


def _rx_json(value):
    try:
        loaded = json.loads(value or '{}')
    except (TypeError, ValueError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _rx_role_guard(user, HTTPError):
    if user.get('role') not in ('master', 'coordenador'):
        raise HTTPError(403, 'A exportação coletiva é exclusiva do Master e da coordenação.')


def _rx_rows(app, c, activity_key='', applied_on=''):
    sql = (
        'SELECT p.*,u.name AS student_name,u.username AS student_login,'
        'u.role AS student_role FROM hmay_performance p '
        'JOIN hmay_users u ON u.id=p.user_id'
    )
    args = []
    conditions = []
    if activity_key:
        conditions.append('p.activity_key=?'); args.append(activity_key)
    if applied_on:
        conditions.append('p.applied_on=?'); args.append(applied_on)
    if conditions:
        sql += ' WHERE ' + ' AND '.join(conditions)
    sql += ' ORDER BY p.applied_on DESC,p.activity,u.name,u.username'
    rows = []
    for source in app.db.execute(c, sql, tuple(args)).fetchall():
        row = dict(source)
        # A exportação coletiva é de alunos. Perfis especiais nunca aparecem,
        # inclusive quando o solicitante é Master.
        if row.get('student_role') != 'user':
            continue
        metadata = _rx_json(row.get('metadata'))
        if not metadata.get('_exam_id'):
            continue
        row['_metadata'] = metadata
        rows.append(row)
    return rows


def result_export_simulations(app, c, user):
    grouped = {}
    for row in _rx_rows(app, c):
        key = (row['activity_key'], row['applied_on'])
        group = grouped.setdefault(key, {
            'activityKey': row['activity_key'],
            'activity': row['activity'],
            'date': row['applied_on'],
            'students': set(),
            'colors': set(),
            'updatedAt': row.get('updated_at', ''),
        })
        group['students'].add(row['user_id'])
        color = F.text(row['_metadata'].get('COR DA PROVA'), 80)
        if color:
            group['colors'].add(color)
        if row.get('updated_at', '') > group['updatedAt']:
            group['updatedAt'] = row['updated_at']
    result = []
    for index, group in enumerate(sorted(
            grouped.values(), key=lambda x: (x['date'], F.norm(x['activity'])), reverse=True)):
        result.append({
            'id': 'sim_' + hashlib.sha256(
                (group['activityKey'] + '\x1f' + group['date']).encode('utf-8')
            ).hexdigest()[:20],
            'activityKey': group['activityKey'],
            'activity': group['activity'],
            'date': group['date'],
            'participants': len(group['students']),
            'colors': sorted(group['colors']),
            'updatedAt': group['updatedAt'],
        })
    return result


def _rx_percent(numerator, denominator):
    return None if not denominator else round(100 * numerator / denominator, 2)


def _rx_add_group(groups, kind, name, number, result):
    label = F.text(name, 250) or 'Não informado'
    bucket = groups[kind].setdefault(label, {
        'name': label, 'correct': 0, 'errors': 0, 'marked': 0, 'total': 0,
        'correctQuestions': [], 'errorQuestions': [], 'pendingQuestions': [],
    })
    bucket['total'] += 1
    if result in (0, 1):
        bucket['marked'] += 1
        if result == 1:
            bucket['correct'] += 1
            bucket['correctQuestions'].append(number)
        else:
            bucket['errors'] += 1
            bucket['errorQuestions'].append(number)
    else:
        bucket['pendingQuestions'].append(number)


def _rx_analyse(exam, metrics, metadata):
    language = F.text(metadata.get('L.E'), 40)
    groups = {kind: {} for kind in _RX_GROUP_KINDS}
    overall = {'correct': 0, 'errors': 0, 'marked': 0, 'total': 0}
    for item in exam.get('items', []):
        item_language = F.text(item.get('language'), 40)
        if item_language and item_language != language:
            continue
        answer = F.text(item.get('answer'), 30).upper()
        if not answer or answer == 'ANULADA':
            continue
        number = int(item.get('number') or 0)
        if not 1 <= number <= 180:
            continue
        metric = metrics.get(f'questao:{number:03d}', {})
        result = metric.get('correct') if isinstance(metric, dict) else None
        if result not in (0, 1):
            result = None
        overall['total'] += 1
        if result in (0, 1):
            overall['marked'] += 1
            if result == 1:
                overall['correct'] += 1
            else:
                overall['errors'] += 1
        area_code = F.text(item.get('area'), 10).upper()
        area_name = _RX_AREA_LABELS.get(area_code, area_code or 'Não informado')
        skill = F.text(item.get('skill'), 40)
        labels = {
            'Área': area_name,
            'Disciplina': item.get('discipline'),
            'Tópico': item.get('topic'),
            'Assunto': item.get('subject'),
            # H01 de áreas diferentes continua sendo uma métrica diferente.
            'Habilidade': f'{area_name} · {skill}' if skill else f'{area_name} · Não informada',
        }
        for kind, label in labels.items():
            _rx_add_group(groups, kind, label, number, result)
    overall['accuracy'] = _rx_percent(overall['correct'], overall['marked'])
    overall['coverage'] = _rx_percent(overall['marked'], overall['total'])
    normalized = {}
    for kind, values in groups.items():
        rows = []
        for item in values.values():
            item['accuracy'] = _rx_percent(item['correct'], item['marked'])
            item['coverage'] = _rx_percent(item['marked'], item['total'])
            rows.append(item)
        normalized[kind] = sorted(rows, key=lambda x: F.norm(x['name']))
    return {'overall': overall, 'groups': normalized}


def result_export_workbook(app, c, user, activity_key, applied_on):
    rows = _rx_rows(app, c, activity_key, applied_on)
    if not rows:
        raise ValueError('Nenhum resultado de aluno foi encontrado para esse simulado.')
    exam_cache = {}
    summary_rows = []
    detail_rows = {kind: [] for kind in _RX_GROUP_KINDS}
    for row in rows:
        metadata = row['_metadata']
        exam_id = metadata.get('_exam_id')
        if exam_id not in exam_cache:
            exam_cache[exam_id] = E.get_exam(app, c, exam_id)
        exam = exam_cache[exam_id]
        if not exam:
            raise ValueError('Um resultado possui mapa de questões inexistente. Corrija o mapa antes de exportar.')
        metrics = _rx_json(row.get('metrics'))
        analysis = _rx_analyse(exam, metrics, metadata)
        overall = analysis['overall']
        common = [
            row.get('student_name', ''), row.get('student_login', ''),
            F.text(metadata.get('TURMA'), 150), row['activity'], row['applied_on'],
            F.text(metadata.get('COR DA PROVA'), 80), F.text(metadata.get('L.E'), 40),
        ]
        summary_rows.append(common + [
            overall['correct'], overall['errors'], overall['marked'], overall['total'],
            '' if overall['accuracy'] is None else overall['accuracy'],
            '' if overall['coverage'] is None else overall['coverage'],
        ])
        for kind in _RX_GROUP_KINDS:
            for item in analysis['groups'][kind]:
                detail_rows[kind].append(common[:3] + [
                    item['name'], item['correct'], item['errors'], item['marked'], item['total'],
                    '' if item['accuracy'] is None else item['accuracy'],
                    '' if item['coverage'] is None else item['coverage'],
                    ', '.join(str(x) for x in item['correctQuestions']),
                    ', '.join(str(x) for x in item['errorQuestions']),
                    ', '.join(str(x) for x in item['pendingQuestions']),
                ])
    summary_rows.sort(key=lambda x: (F.norm(x[0]), F.norm(x[1])))
    summary_headers = [
        'Aluno', 'Login', 'Turma', 'Simulado', 'Data', 'Cor da prova',
        'Língua estrangeira', 'Acertos', 'Erros', 'Questões calculadas',
        'Questões válidas', 'Aproveitamento (%)', 'Cobertura (%)',
    ]
    extra_sheets = []
    sheet_names = {
        'Área': 'Por área', 'Disciplina': 'Por disciplina', 'Tópico': 'Por tópico',
        'Assunto': 'Por assunto', 'Habilidade': 'Por habilidade',
    }
    group_headers = [
        'Aluno', 'Login', 'Turma', 'Classificação', 'Acertos', 'Erros',
        'Questões calculadas', 'Questões válidas', 'Aproveitamento (%)',
        'Cobertura (%)', 'Questões acertadas', 'Questões erradas', 'Sem resultado',
    ]
    for kind in _RX_GROUP_KINDS:
        values = detail_rows[kind]
        values.sort(key=lambda x: (F.norm(x[0]), F.norm(x[3])))
        extra_sheets.append((sheet_names[kind], group_headers, values))
    return T.export(
        summary_headers, summary_rows, first_name='Resumo dos alunos',
        extra_sheets=extra_sheets,
    )


_rx_original_handle = handle


def handle(app, c, user, path, method, data, query, start, HTTPError):
    if path == '/api/model-data/simulations' and method == 'GET':
        _rx_role_guard(user, HTTPError)
        return app.reply(start, 200, {'simulations': result_export_simulations(app, c, user)})
    if path == '/api/model-data/export-results' and method == 'POST':
        _rx_role_guard(user, HTTPError)
        activity_key = F.text(data.get('activityKey'), 250)
        applied_on = F.text(data.get('date'), 40)
        if not activity_key or not applied_on:
            raise ValueError('Selecione um simulado para exportar.')
        blob, mime = result_export_workbook(app, c, user, activity_key, applied_on)
        title_row = app.db.execute(
            c, 'SELECT activity FROM hmay_performance WHERE activity_key=? AND applied_on=? ORDER BY activity LIMIT 1',
            (activity_key, applied_on),
        ).fetchone()
        title = title_row['activity'] if title_row else 'simulado'
        filename = re.sub(r'[^A-Za-z0-9_-]+', '_', title).strip('_') or 'simulado'
        app.event(c, user, user['id'], 'model_data_results_export')
        return app.reply(
            start, 200, blob, mime,
            [('Content-Disposition', f'attachment; filename="Resultados_convertidos_{filename}_{applied_on}.xlsx"')],
        )
    return _rx_original_handle(app, c, user, path, method, data, query, start, HTTPError)
'''

JS_SOURCE = r''''use strict';
// Exportação coletiva dos resultados já convertidos pelo gabarito.
let resultExportSimulations=null;
let resultExportLoading=false;
let resultExportSelected='';

async function loadResultExportSimulations(force=false){
 if(resultExportLoading)return;
 if(resultExportSimulations!==null&&!force)return;
 resultExportLoading=true;
 try{
  const data=await api('/api/model-data/simulations');
  resultExportSimulations=Array.isArray(data.simulations)?data.simulations:[];
  if(!resultExportSimulations.some(x=>x.id===resultExportSelected))resultExportSelected=resultExportSimulations[0]?.id||'';
 }finally{
  resultExportLoading=false;
  if(view==='result-export')render();
 }
}

function resultExportView(){
 if(!manages())return head('Exportar resultados','Acesso reservado ao Master e à coordenação.');
 if(resultExportSimulations===null&&!resultExportLoading)queueMicrotask(()=>loadResultExportSimulations());
 if(resultExportLoading||resultExportSimulations===null)return head('Exportar resultados','Resultados convertidos por simulado.')+'<section class="card">Carregando simulados importados…</section>';
 if(!resultExportSimulations.length)return head('Exportar resultados','Resultados convertidos por simulado.')+
  '<section class="card"><h2>Nenhum simulado importado</h2><p>Depois de confirmar uma importação em Desempenho, o simulado aparecerá aqui.</p><div class="actions">'+button('Atualizar lista','result-export-refresh','secondary')+'</div></section>';
 const selected=resultExportSimulations.find(x=>x.id===resultExportSelected)||resultExportSimulations[0];
 resultExportSelected=selected.id;
 const options=resultExportSimulations.map(x=>`<option value="${esc(x.id)}" ${x.id===selected.id?'selected':''}>${esc(x.activity)} · ${esc(x.date)} · ${x.participants} aluno(s)</option>`).join('');
 return head('Exportar resultados','Escolha um simulado importado e baixe os resultados convertidos dos alunos.')+
 `<section class="card"><h2>Selecionar simulado</h2><label>Simulado<select name="result-export-simulation">${options}</select></label><div class="stats"><div class="stat"><strong>${selected.participants}</strong><span>aluno(s)</span></div><div class="stat"><strong>${esc(selected.date)}</strong><span>data de aplicação</span></div><div class="stat"><strong>${esc((selected.colors||[]).join(', ')||'—')}</strong><span>cores encontradas</span></div></div><div class="actions">${button('Exportar resultados convertidos','result-export-download','primary')}${button('Atualizar lista','result-export-refresh','secondary')}</div><p class="micro">O Excel terá Resumo dos alunos, Por área, Por disciplina, Por tópico, Por assunto e Por habilidade. Habilidades iguais permanecem separadas por área.</p></section>`+
 `<section class="card"><h2>Regra utilizada</h2><p>Resposta igual ao gabarito = 1 acerto. Resposta diferente ou vazia = 0. Questão anulada ou sem gabarito fica fora do cálculo.</p><p>Nas questões 01–05 de Linguagens, o sistema utiliza a versão de Inglês ou Espanhol indicada para cada aluno.</p></section>`;
}

acts['result-export-refresh']=async()=>{resultExportSimulations=null;await loadResultExportSimulations(true);};
acts['result-export-download']=async()=>{
 const selected=resultExportSimulations?.find(x=>x.id===resultExportSelected);
 if(!selected)throw new Error('Selecione um simulado.');
 const safe=String(selected.activity||'simulado').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^A-Za-z0-9_-]+/g,'_').replace(/^_+|_+$/g,'')||'simulado';
 await downloadPost('/api/model-data/export-results',{activityKey:selected.activityKey,date:selected.date},`Resultados_convertidos_${safe}_${selected.date}.xlsx`);
 toast('Resultados convertidos exportados.');
};

document.addEventListener('change',event=>{
 if(event.target?.name!=='result-export-simulation')return;
 resultExportSelected=event.target.value;
 render();
});
'''


def prepare():
    model_path = ROOT / 'model_data.py'
    source = model_path.read_text(encoding='utf-8')
    metadata_old = "metadata = {'COR DA PROVA': student['color'], 'L.E': student['language'],"
    metadata_new = "metadata = {'COR DA PROVA': student['color'], 'L.E': student['language'], 'TURMA': student['group'],"
    if metadata_new not in source:
        if source.count(metadata_old) != 1:
            raise RuntimeError('Ponto de inclusão da turma não encontrado em model_data.py.')
        source = source.replace(metadata_old, metadata_new, 1)
    if PY_MARKER not in source:
        source = source.rstrip() + PY_EXTENSION + '\n'
    model_path.write_text(source, encoding='utf-8')

    static = ROOT / 'static'
    (static / 'result_export.js').write_text(JS_SOURCE, encoding='utf-8')

    app_js_path = static / 'app.js'
    app_js = app_js_path.read_text(encoding='utf-8')
    if "['result-export','Exportar resultados']" not in app_js:
        old = "['performance','Desempenho'],['exams','Mapa de questões']"
        new = "['performance','Desempenho'],['result-export','Exportar resultados'],['exams','Mapa de questões']"
        if app_js.count(old) != 1:
            raise RuntimeError('Lista principal de navegação não encontrada.')
        app_js = app_js.replace(old, new, 1)
    app_js = app_js.replace(
        "!['exams','result-model'].includes(x[0])||manages()",
        "!['exams','result-model','result-export'].includes(x[0])||manages()",
        1,
    )
    if "'result-export':resultExportView" not in app_js:
        old = "mapping:mappingView,exams:examsView,'result-model':resultModelView"
        new = "mapping:mappingView,exams:examsView,'result-model':resultModelView,'result-export':resultExportView"
        if app_js.count(old) != 1:
            raise RuntimeError('Mapa de páginas não encontrado.')
        app_js = app_js.replace(old, new, 1)
    app_js_path.write_text(app_js, encoding='utf-8')

    app_path = ROOT / 'webapp.py'
    webapp = app_path.read_text(encoding='utf-8')
    if JS_MIME not in webapp:
        entries = list(re.finditer(
            r"'[^'\n]+\.js'\s*:\s*'application/javascript; charset=utf-8'", webapp,
        ))
        if not entries:
            raise RuntimeError('Lista de arquivos JavaScript não encontrada em webapp.py.')
        anchor = entries[-1]
        webapp = webapp[:anchor.end()] + ',' + JS_MIME + webapp[anchor.end():]
    app_path.write_text(webapp, encoding='utf-8')

    html_path = static / 'app.html'
    html = html_path.read_text(encoding='utf-8')
    if JS_URL not in html:
        html = html.replace('</body>', f'<script src="{JS_URL}" defer></script>\n</body>', 1)
    html_path.write_text(html, encoding='utf-8')

    print('MEUCRONOGRAMA_RESULT_EXPORT_READY: manager page and collective converted XLSX prepared.', flush=True)


if __name__ == '__main__':
    prepare()
