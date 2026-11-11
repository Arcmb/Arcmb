"""Add a dedicated TRI/redaction workbook and Qi Vestibulares visual identity."""
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parent
PY_MARKER = '# === QI TRI E REDACAO V1 ==='
JS_MARKER = '// === QI TRI E REDACAO V1 ==='
CSS_MARKER = '/* === QI VESTIBULARES PASTEL RED V1 === */'

PY_EXT = r'''
# === QI TRI E REDACAO V1 ===
import base64 as _qi_b64

_TRI_ALIASES.update({
    'redactionTheme': {'tema', 'tema da redacao', 'tema redacao', 'proposta de redacao'},
    'c1': {'c1', 'nota c1', 'competencia 1', 'competencia i'},
    'c2': {'c2', 'nota c2', 'competencia 2', 'competencia ii'},
    'c3': {'c3', 'nota c3', 'competencia 3', 'competencia iii'},
    'c4': {'c4', 'nota c4', 'competencia 4', 'competencia iv'},
    'c5': {'c5', 'nota c5', 'competencia 5', 'competencia v'},
})
_TRI_META_KEYS.update({
    'c1': ('_redaction_c1', 'C1', 'NOTA C1', 'COMPETÊNCIA 1', 'COMPETENCIA 1'),
    'c2': ('_redaction_c2', 'C2', 'NOTA C2', 'COMPETÊNCIA 2', 'COMPETENCIA 2'),
    'c3': ('_redaction_c3', 'C3', 'NOTA C3', 'COMPETÊNCIA 3', 'COMPETENCIA 3'),
    'c4': ('_redaction_c4', 'C4', 'NOTA C4', 'COMPETÊNCIA 4', 'COMPETENCIA 4'),
    'c5': ('_redaction_c5', 'C5', 'NOTA C5', 'COMPETÊNCIA 5', 'COMPETENCIA 5'),
})
_QI_TRI_NUMERIC_KEYS = ('ranking', 'tri', 'triBonus', 'lc', 'ch', 'cn', 'mt', 'redaction', 'c1', 'c2', 'c3', 'c4', 'c5')
_QI_TRI_SIGNATURE_KEYS = _QI_TRI_NUMERIC_KEYS + ('redactionTheme',)


def _tri_detect_table(sheets):
    candidates = []
    accepted = ('tri', 'lc', 'ch', 'cn', 'mt', 'redaction', 'c1', 'c2', 'c3', 'c4', 'c5')
    for sheet_order, sheet in enumerate(sheets):
        rows = sheet['rows']
        for row_index in range(min(40, len(rows))):
            current = rows[row_index]
            next_row = rows[row_index + 1] if row_index + 1 < len(rows) else []
            width = max(len(current), len(next_row))
            combined = []
            for col in range(width):
                one = current[col] if col < len(current) else ''
                two = next_row[col] if col < len(next_row) else ''
                combined.append((str(one or '') + ' ' + str(two or '')).strip())
            for span, header in ((1, current), (2, combined)):
                columns = _tri_header_columns(header)
                score = 8 if 'name' in columns else 0
                score += 2 * sum(key in columns for key in accepted)
                score += int('ranking' in columns)
                preferred = _tri_norm(sheet['name']) in ('ranking', 'ranking geral', 'ranking geral alunos', 'tri e redacao', 'tri redacao')
                score += 4 if preferred else 0
                if 'name' in columns and any(key in columns for key in accepted):
                    candidates.append((score, -sheet_order, -row_index, sheet, row_index, span, columns, header))
    if not candidates:
        raise ValueError('Não encontrei NOME e colunas de TRI ou redação no arquivo.')
    candidates.sort(reverse=True, key=lambda item: item[:3])
    _, _, _, sheet, row_index, span, columns, header = candidates[0]
    return sheet, row_index, span, columns, header


def _tri_parse_ranking(data):
    sheets = _tri_xlsx_rows(data)
    sheet, header_row, header_span, columns, header = _tri_detect_table(sheets)
    records = []
    for source_index, row in enumerate(sheet['rows'][header_row + header_span:], start=header_row + header_span + 1):
        def value(key):
            index = columns.get(key)
            return row[index] if index is not None and index < len(row) else ''
        name = F.text(value('name'), 250)
        if not name:
            continue
        scores = {key: _tri_number(value(key)) for key in _QI_TRI_NUMERIC_KEYS}
        scores['redactionTheme'] = F.text(value('redactionTheme'), 500) or None
        competencies = [scores[key] for key in ('c1', 'c2', 'c3', 'c4', 'c5')]
        for index, number in enumerate(competencies, start=1):
            if number is not None and not 0 <= number <= 200:
                raise ValueError(f'Linha {source_index}: C{index} deve estar entre 0 e 200.')
        if scores['redaction'] is not None and not 0 <= scores['redaction'] <= 1000:
            raise ValueError(f'Linha {source_index}: a nota de redação deve estar entre 0 e 1000.')
        if all(number is not None for number in competencies):
            total = round(sum(competencies), 4)
            if scores['redaction'] is None:
                scores['redaction'] = total
            elif abs(scores['redaction'] - total) > .01:
                raise ValueError(f'Linha {source_index}: a nota de redação ({scores["redaction"]}) difere da soma C1–C5 ({total}).')
        if all(scores.get(key) is None for key in _QI_TRI_SIGNATURE_KEYS):
            continue
        if scores['tri'] is None and all(scores[key] is not None for key in ('lc', 'ch', 'cn', 'mt', 'redaction')):
            scores['tri'] = round(sum(scores[key] for key in ('lc', 'ch', 'cn', 'mt', 'redaction')) / 5, 3)
        records.append({
            'name': name,
            'nameKey': F.norm(name),
            'group': F.text(value('group'), 150),
            'activity': F.text(value('activity'), 200),
            'date': _tri_iso_date(value('date')),
            'language': F.text(value('language'), 40),
            'scores': scores,
            'line': source_index,
        })
    if not records:
        raise ValueError('A planilha foi encontrada, mas não contém notas TRI ou de redação preenchidas.')
    detected = {}
    for key, index in columns.items():
        detected[key] = F.text(header[index] if index < len(header) else '', 120)
    return {'sheet': sheet['name'], 'headerRow': header_row + 1, 'columns': detected, 'records': records}


def _tri_scores_from_metadata(metadata):
    result = {key: _tri_meta_number(metadata, key) for key in _TRI_META_KEYS}
    result['redactionTheme'] = F.text(
        metadata.get('_redaction_theme') or metadata.get('TEMA DA REDAÇÃO') or metadata.get('TEMA REDAÇÃO'), 500
    ) or None
    if result['tri'] is None and all(result[key] is not None for key in ('lc', 'ch', 'cn', 'mt', 'redaction')):
        result['tri'] = round(sum(result[key] for key in ('lc', 'ch', 'cn', 'mt', 'redaction')) / 5, 3)
    return result


def _tri_choose_record(records, activity, applied_on):
    if len(records) == 1:
        return records[0], ''
    dated = [row for row in records if row.get('date') == applied_on]
    if len(dated) == 1:
        return dated[0], ''
    if dated:
        records = dated
    activity_key = F.norm(activity)
    titled = [row for row in records if row.get('activity') and F.norm(row['activity']) == activity_key]
    if len(titled) == 1:
        return titled[0], ''
    if titled:
        records = titled
    signatures = {tuple(row['scores'].get(key) for key in _QI_TRI_SIGNATURE_KEYS) for row in records}
    if len(signatures) == 1:
        return records[0], ''
    return None, 'Há mais de uma linha para o mesmo nome e não foi possível escolher o simulado correto.'


def _tri_preview(app, c, data):
    parsed = _tri_parse_ranking(data)
    activity_key = F.text(data.get('activityKey'), 250)
    applied_on = F.date_value(data.get('date'))
    match = _tri_match(app, c, parsed, activity_key, applied_on)
    sample = []
    changed = unchanged = 0
    for pair in match['matched']:
        metadata = _rx_json(pair['target'].get('metadata'))
        old = _tri_scores_from_metadata(metadata)
        new = pair['source']['scores']
        has_change = any(new.get(key) is not None and old.get(key) != new.get(key) for key in new)
        changed += int(has_change); unchanged += int(not has_change)
        if len(sample) < 20:
            sample.append({
                'name': pair['target']['student_name'], 'login': pair['target']['student_login'],
                **{key: new.get(key) for key in _QI_TRI_SIGNATURE_KEYS}, 'changed': has_change,
            })
    return parsed, match, {
        'sheet': parsed['sheet'], 'sourceRows': len(parsed['records']),
        'students': len(match['targets']), 'matched': len(match['matched']),
        'changed': changed, 'unchanged': unchanged,
        'unmatched': len(match['unmatched']), 'conflicts': len(match['conflicts']),
        'withoutScore': len(match['withoutScore']), 'sample': sample,
    }


def _tri_apply_metadata(metadata, scores, source_sheet, user):
    changed = False
    numeric_mapping = {
        'ranking': '_ranking', 'tri': '_tri_general', 'triBonus': '_tri_bonus',
        'lc': '_tri_lc', 'ch': '_tri_ch', 'cn': '_tri_cn', 'mt': '_tri_mt',
        'redaction': '_tri_redaction', 'c1': '_redaction_c1', 'c2': '_redaction_c2',
        'c3': '_redaction_c3', 'c4': '_redaction_c4', 'c5': '_redaction_c5',
    }
    for key, destination in numeric_mapping.items():
        value = scores.get(key)
        if value is None:
            continue
        stored = int(value) if key == 'ranking' and float(value).is_integer() else round(float(value), 4)
        if metadata.get(destination) != stored:
            metadata[destination] = stored
            changed = True
    theme = F.text(scores.get('redactionTheme'), 500)
    if theme and metadata.get('_redaction_theme') != theme:
        metadata['_redaction_theme'] = theme
        changed = True
    if changed:
        metadata['_tri_source_sheet'] = source_sheet
        metadata['_tri_imported_at'] = P.now().isoformat()
        metadata['_tri_imported_by'] = user['id']
    return changed


def _qi_tri_template_workbook():
    headers = [
        'NOME', 'LOGIN (opcional)', 'NOME DO SIMULADO', 'DATA DE APLICAÇÃO', 'TURMA',
        'RANKING', 'NOTA TRI GERAL', 'TRI LINGUAGENS', 'TRI HUMANAS',
        'TRI NATUREZA', 'TRI MATEMÁTICA', 'NOTA COM BONIFICAÇÃO',
        'TEMA DA REDAÇÃO', 'C1', 'C2', 'C3', 'C4', 'C5', 'NOTA DA REDAÇÃO',
    ]
    rows = [['' for _ in headers] for _ in range(200)]
    help_headers = ['Campo', 'Orientação']
    help_rows = [
        ['NOME', 'Obrigatório. Deve corresponder ao nome usado no resultado já importado.'],
        ['LOGIN', 'Opcional. Serve apenas como apoio; o vínculo principal continua pelo nome.'],
        ['NOME DO SIMULADO', 'Informe o mesmo nome da avaliação já importada.'],
        ['DATA DE APLICAÇÃO', 'Use dd/mm/aaaa ou aaaa-mm-dd.'],
        ['RANKING', 'Posição do aluno no simulado, quando disponível.'],
        ['NOTA TRI GERAL', 'Nota oficial geral. Não é recalculada a partir dos acertos.'],
        ['TRI POR ÁREA', 'Linguagens, Humanas, Natureza e Matemática. Deixe vazio quando a área não foi aplicada.'],
        ['TEMA DA REDAÇÃO', 'Opcional. Texto do tema/proposta da redação.'],
        ['C1–C5', 'Cada competência deve estar entre 0 e 200.'],
        ['NOTA DA REDAÇÃO', 'De 0 a 1000. Se ficar vazia e C1–C5 estiverem completos, o sistema calcula a soma.'],
        ['REGRA DE ATUALIZAÇÃO', 'Campos vazios não apagam notas existentes. Respostas A–E, acertos, mapa de questões e cronograma são preservados.'],
        ['ARQUIVO', 'Use XLSX sem fórmulas, macros, proteção ou vínculos externos.'],
    ]
    return T.export(headers, rows, first_name='TRI e Redação', extra_sheets=[('Como preencher', help_headers, help_rows)])


_qi_tri_original_summary = student_summary

def student_summary(app, c, user, target):
    result = _qi_tri_original_summary(app, c, user, target)
    metadata_by_simulation = _tri_simulation_metadata(app, c, target['id'])
    for simulation in result.get('simulations', []):
        metadata = metadata_by_simulation.get((F.norm(simulation.get('activity')), simulation.get('date')), {})
        scores = _tri_scores_from_metadata(metadata)
        simulation['redaction'] = {
            'score': scores.get('redaction'), 'theme': scores.get('redactionTheme'),
            'c1': scores.get('c1'), 'c2': scores.get('c2'), 'c3': scores.get('c3'),
            'c4': scores.get('c4'), 'c5': scores.get('c5'),
        }
    return result


_qi_tri_original_handle = handle

def handle(app, c, user, path, method, data, query, start, HTTPError):
    if path == '/api/model-data/tri-template':
        _rx_role_guard(user, HTTPError)
        if method != 'POST':
            raise HTTPError(405, 'Use o botão Gerar modelo TRI + Redação.')
        workbook = _qi_tri_template_workbook()
        return app.reply(start, 200, {
            'filename': 'MODELO_TRI_E_REDACAO.xlsx',
            'mime': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'file': _qi_b64.b64encode(workbook).decode('ascii'),
        })
    return _qi_tri_original_handle(app, c, user, path, method, data, query, start, HTTPError)
'''

JS_EXT = r'''
// === QI TRI E REDACAO V1 ===
function qiTriDownloadBase64(filename,mime,encoded){
 const binary=atob(encoded),bytes=new Uint8Array(binary.length);
 for(let i=0;i<binary.length;i++)bytes[i]=binary.charCodeAt(i);
 const url=URL.createObjectURL(new Blob([bytes],{type:mime}));
 const a=document.createElement('a');a.href=url;a.download=filename;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1500);
}
function triImportCard(){
 if(!manages())return '';
 return `<section class="card"><h2>Importar TRI e Redação <button type="button" class="help-button" data-act="tri-import-help" aria-label="Explicar notas TRI e redação">?</button></h2><p>Importe ranking, TRI geral e por área, tema da redação, competências C1–C5 e nota total. O arquivo atualiza somente essas notas; respostas, acertos e mapa de questões são preservados.</p><fieldset class="tri-import-controls" ${triImportBusy?'disabled':''}><div class="actions">${button('Gerar modelo TRI + Redação','tri-import-template','secondary')}</div><label>Arquivo de notas (.xlsx, até 8 MB)<input id="tri-import-file" type="file" accept=".xlsx"></label><p id="tri-import-filename">${esc(triImportDraft?.filename||'Nenhum arquivo selecionado.')}</p><div class="actions">${button('Ler notas TRI/Redação','tri-import-inspect','primary')}${button('Limpar','tri-import-clear','secondary')}</div><div id="tri-import-status">${triImportStatus()}</div></fieldset><div class="actions">${button('Consultar notas no banco','tri-coverage','secondary')}</div><div id="tri-coverage">${triCoverageHtml()}</div></section>`;
}
function triImportStatus(){
 if(!triImportDraft?.inspection)return '';
 const d=triImportDraft.inspection,options=(d.simulations||[]).map(x=>`<option value="${esc(x.id)}" ${(triImportDraft.simulationId||d.simulations?.[0]?.id)===x.id?'selected':''}>${esc(x.activity)} · ${esc(x.date)} · ${x.participants} aluno(s)</option>`).join('');
 const sample=(d.sample||[]).slice(0,8).map(x=>`<tr><td>${esc(x.name)}</td><td>${triFormat(x.scores?.tri)}</td><td>${triFormat(x.scores?.lc)}</td><td>${triFormat(x.scores?.ch)}</td><td>${triFormat(x.scores?.cn)}</td><td>${triFormat(x.scores?.mt)}</td><td>${triFormat(x.scores?.redaction,0)}</td><td>${triFormat(x.scores?.c1,0)}</td><td>${triFormat(x.scores?.c2,0)}</td><td>${triFormat(x.scores?.c3,0)}</td><td>${triFormat(x.scores?.c4,0)}</td><td>${triFormat(x.scores?.c5,0)}</td></tr>`).join('');
 return `<hr><h3>Aba reconhecida: ${esc(d.sheet)}</h3><p><strong>${d.rows}</strong> linha(s) com nota · cabeçalho na linha ${d.headerRow}.</p><div class="student-home-chips">${triColumnsText(d.columns)}</div><label>Vincular ao simulado<select name="tri-import-simulation">${options}</select></label><p class="micro">${esc(d.notice||'')}</p>${sample?`<div class="table-wrap"><table><thead><tr><th>Aluno</th><th>TRI geral</th><th>LC</th><th>CH</th><th>CN</th><th>MT</th><th>Redação</th><th>C1</th><th>C2</th><th>C3</th><th>C4</th><th>C5</th></tr></thead><tbody>${sample}</tbody></table></div>`:''}<div class="actions">${button('Conferir vínculos das notas','tri-import-preview','primary')}</div><div id="tri-import-preview">${triImportPreviewData?triImportPreviewHtml(triImportPreviewData):''}</div>`;
}
function triImportPreviewHtml(d){
 const sample=(d.sample||[]).map(x=>`<tr><td>${esc(x.name)}</td><td>${esc(x.login||'')}</td><td>${triFormat(x.tri)}</td><td>${triFormat(x.lc)}</td><td>${triFormat(x.ch)}</td><td>${triFormat(x.cn)}</td><td>${triFormat(x.mt)}</td><td>${triFormat(x.redaction,0)}</td><td>${triFormat(x.c1,0)}</td><td>${triFormat(x.c2,0)}</td><td>${triFormat(x.c3,0)}</td><td>${triFormat(x.c4,0)}</td><td>${triFormat(x.c5,0)}</td><td>${x.changed?'Atualizar':'Sem mudança'}</td></tr>`).join('');
 const warnings=[];if(d.unmatched)warnings.push(`${d.unmatched} nome(s) não encontrados no simulado.`);if(d.conflicts)warnings.push(`${d.conflicts} conflito(s) de nomes repetidos.`);if(d.withoutScore)warnings.push(`${d.withoutScore} aluno(s) sem linha de nota.`);
 return `<div class="notice ${warnings.length?'warning':'success'}"><strong>${d.matched}/${d.students}</strong> aluno(s) vinculados · ${d.changed} atualização(ões) · ${d.unchanged} sem mudança.${warnings.length?'<br>'+warnings.map(esc).join(' '):''}</div>${sample?`<div class="table-wrap"><table><thead><tr><th>Aluno</th><th>Login</th><th>TRI</th><th>LC</th><th>CH</th><th>CN</th><th>MT</th><th>Redação</th><th>C1</th><th>C2</th><th>C3</th><th>C4</th><th>C5</th><th>Situação</th></tr></thead><tbody>${sample}</tbody></table></div>`:''}<div class="actions">${button(triImportBusy?'Salvando notas…':triImportProcess?.state==='error'?'Retomar envio':'Confirmar vínculo das notas','tri-import-confirm','primary',triImportBusy?'disabled':'')}</div>`;
}
acts['tri-import-template']=async()=>{const d=await api('/api/model-data/tri-template',{});qiTriDownloadBase64(d.filename,d.mime,d.file);toast('Modelo TRI e Redação gerado.');};
acts['tri-import-help']=()=>modal('TRI e Redação por simulado','<p><strong>TCT/acertos</strong> continuam sendo calculados pelas respostas e pelo gabarito.</p><p><strong>TRI</strong>, ranking e redação são importados separadamente e vinculados ao mesmo aluno e simulado.</p><p>C1–C5 aceitam valores de 0 a 200. A nota total aceita 0 a 1000; se ficar vazia e as cinco competências estiverem completas, o sistema calcula a soma.</p><p>Campos vazios preservam o valor já salvo.</p>',null);
const qiOriginalTriStudentPanel=triStudentPanel;
triStudentPanel=function(d){
 let base=qiOriginalTriStudentPanel(d),latest=(d?.simulations||[])[0],red=latest?.redaction||{};
 const values=['c1','c2','c3','c4','c5'].map(k=>triScore(red[k]));
 if(!base||(!red.theme&&values.every(v=>v===null)))return base;
 const cards=values.map((v,i)=>`<div><strong>${v===null?'—':triFormat(v,0)}</strong><span>C${i+1}</span></div>`).join('');
 const block=`<div class="qi-redaction-detail"><h4>Redação</h4>${red.theme?`<p><strong>Tema:</strong> ${esc(red.theme)}</p>`:''}<div class="student-home-mini-stats qi-redaction-grid">${cards}</div></div>`;
 return base.replace('<p class="micro">TCT/acertos',block+'<p class="micro">TCT/acertos');
};
'''

CSS_EXT = r'''
.tri-import-controls{min-inline-size:0;border:0;padding:0;margin:0}.tri-import-process-card progress{display:block;width:min(100%,24rem);margin:.35rem 0;accent-color:var(--primary,#91394b)}
/* === QI VESTIBULARES PASTEL RED V1 === */
:root{--ink:#3b2026;--muted:#7b5c62;--line:#ecd2d7;--paper:#fff;--bg:#fff7f8;--purple:#b65362;--soft:#f8e2e6;--mint:#e1f1e9;--rose:#f8dce2;--amber:#fff0d4;--primary:#b65362;--border:#ecd2d7;--text:#3b2026}
body{background:linear-gradient(180deg,#fff9fa 0,#fff5f7 100%);color:var(--ink)}
aside{background:linear-gradient(180deg,#8f3b49 0%,#71303b 100%);color:#fff8f9}
aside .wordmark small,.sidebar-foot,.sidebar-foot small{color:#f3d9de}
nav button{color:#f7e5e8}nav button:hover{background:#ffffff16;color:#fff}nav button.active{background:#c26775;color:#fff;box-shadow:inset 3px 0 #ffd9df}
.logo{background:#fff7f8;color:#8f3b49;border-radius:14px;width:50px;height:50px;padding:5px;box-shadow:0 8px 22px #4b152333}.logo img{display:block;width:100%;height:100%;object-fit:contain}
.primary{background:#b65362;color:#fff}.primary:hover{background:#9f4351}.secondary{background:#f8e2e6;color:#75313d}.secondary:hover{background:#f2cfd6}.link-button,a{color:#a74453}
button:focus-visible,a:focus-visible,input:focus-visible,select:focus-visible,textarea:focus-visible{outline-color:#db8d99}
header{border-bottom-color:#ecd2d7}.card{border-color:#ecd2d7;box-shadow:0 8px 26px #7f34450a}.hero,.notice{background:#fbe9ec;border-color:#efcbd2}.notice.success{background:#e7f4ed}.notice.warning{background:#fff1d8}.notice.danger{background:#f8dce2}
.eyebrow{color:#aa4655}.tag{background:#f8e2e6;color:#873947}.progress span,input[type=checkbox]{accent-color:#b65362}.progress span{background:#b65362}
.student-home-ring{background:conic-gradient(#b65362 var(--student-progress),#f3e0e4 0)}.student-home-bar{background:#f3e0e4}.student-home-bar span,.student-home-evolution-track span,.student-home-evolution-track.tri-track span{background:linear-gradient(90deg,#b65362,#db8d99)}.student-home-chip{background:#f8e2e6;color:#71303b}.student-tri-panel{border-color:#ecd2d7;background:#fffafb}.student-tri-main strong{color:#9f4351}.help-button{background:#f8e2e6;color:#8f3b49}
.login-body{background:radial-gradient(circle at top,#f8dfe4 0,#fff7f8 50%,#f2d2d8 100%)}.login-card{box-shadow:0 24px 80px #6f283a20;border:1px solid #efd3d8}
.qi-redaction-detail{margin-top:.8rem;padding-top:.9rem;border-top:1px solid #ecd2d7}.qi-redaction-grid{grid-template-columns:repeat(5,minmax(0,1fr))}
@media(max-width:760px){.qi-redaction-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
'''

QI_LOGO = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 160" role="img" aria-labelledby="title"><title id="title">Qi Vestibulares</title><rect width="160" height="160" rx="34" fill="#fff7f8"/><circle cx="67" cy="75" r="42" fill="none" stroke="#b65362" stroke-width="18"/><path d="M91 99l27 27" stroke="#8f3b49" stroke-width="18" stroke-linecap="round"/><rect x="112" y="59" width="17" height="52" rx="8.5" fill="#8f3b49"/><circle cx="120.5" cy="38" r="10" fill="#b65362"/><circle cx="38" cy="28" r="6" fill="#d98592"/><circle cx="22" cy="43" r="5" fill="#efb9c1"/><circle cx="26" cy="22" r="4" fill="#8f3b49"/></svg>'''


def patch_backend():
    path = ROOT / 'model_data.py'
    text = path.read_text(encoding='utf-8')
    if PY_MARKER not in text:
        path.write_text(text.rstrip() + '\n\n' + PY_EXT + '\n', encoding='utf-8')


def patch_ui():
    path = ROOT / 'static' / 'tri_scores.js'
    text = path.read_text(encoding='utf-8')
    if JS_MARKER not in text:
        path.write_text(text.rstrip() + '\n\n' + JS_EXT + '\n', encoding='utf-8')


def patch_branding():
    static = ROOT / 'static'
    (static / 'qi-logo.svg').write_text(QI_LOGO, encoding='utf-8')
    (static / 'icon.svg').write_text(QI_LOGO, encoding='utf-8')
    style = static / 'style.css'
    text = style.read_text(encoding='utf-8')
    if CSS_MARKER not in text:
        style.write_text(text.rstrip() + '\n\n' + CSS_EXT + '\n', encoding='utf-8')
    replacements = {
        '<span class="logo">m</span>': '<span class="logo"><img src="/static/qi-logo.svg" alt="Qi Vestibulares"></span>',
        '<small>PLANEJAMENTO ADAPTATIVO</small>': '<small>QI VESTIBULARES · PLANEJAMENTO ADAPTATIVO</small>',
        '<small>Uma rotina possível. Um passo de cada vez.</small>': '<small>QI VESTIBULARES · UMA ROTINA POSSÍVEL</small>',
        '<meta name="theme-color" content="#22213c">': '<meta name="theme-color" content="#8f3b49">',
    }
    for filename in ('app.html', 'login.html', 'setup.html'):
        path = static / filename
        text = path.read_text(encoding='utf-8')
        for before, after in replacements.items():
            text = text.replace(before, after)
        text = re.sub(r'/static/style\.css(?:\?v=[^"\']+)?', '/static/style.css?v=3.0.0', text)
        if filename == 'app.html':
            text = re.sub(r'/static/tri_scores\.js\?v=[^"\']+', '/static/tri_scores.js?v=3.0.0', text)
        path.write_text(text, encoding='utf-8')
    manifest = static / 'manifest.webmanifest'
    try:
        data = json.loads(manifest.read_text(encoding='utf-8'))
        data['name'] = 'Meu Cronograma · Qi Vestibulares'
        data['short_name'] = 'Cronograma Qi'
        data['theme_color'] = '#8f3b49'
        data['background_color'] = '#fff7f8'
        manifest.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    except Exception:
        pass


def main():
    patch_backend(); patch_ui(); patch_branding()
    print('MEUCRONOGRAMA_QI_TRI_REDACAO_READY: model, C1-C5, essay total and pastel-red Qi branding prepared.', flush=True)


if __name__ == '__main__':
    main()
