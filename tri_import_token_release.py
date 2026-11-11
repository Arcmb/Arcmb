"""Replace TRI confirmation XLSX re-upload with a signed structured import token."""
from pathlib import Path

ROOT=Path(__file__).resolve().parent
BACKEND_MARK="# === TRI IMPORT TOKEN V1 ==="
FRONTEND_MARK="// === TRI IMPORT TOKEN V1 ==="

BACKEND = r'''
# === TRI IMPORT TOKEN V1 ===
import os as _tri_tok_os
import time as _tri_tok_time
import hmac as _tri_tok_hmac
import hashlib as _tri_tok_hashlib
import base64 as _tri_tok_base64

_TRI_TOKEN_TTL_SECONDS = 1800
_TRI_TOKEN_BATCH_SIZE = 80
_TRI_TOKEN_SCORE_TO_META = {
    'ranking': '_ranking',
    'tri': '_tri_general',
    'triBonus': '_tri_bonus',
    'lc': '_tri_lc',
    'ch': '_tri_ch',
    'cn': '_tri_cn',
    'mt': '_tri_mt',
    'redaction': '_tri_redaction',
    'c1': '_redaction_c1',
    'c2': '_redaction_c2',
    'c3': '_redaction_c3',
    'c4': '_redaction_c4',
    'c5': '_redaction_c5',
    'redactionTheme': '_redaction_theme',
}

def _tri_token_b64e(raw):
    return _tri_tok_base64.urlsafe_b64encode(raw).decode('ascii').rstrip('=')

def _tri_token_b64d(value):
    value = str(value or '')
    value += '=' * (-len(value) % 4)
    return _tri_tok_base64.urlsafe_b64decode(value.encode('ascii'))

def _tri_token_secret():
    secret = _tri_tok_os.environ.get('SECRET_KEY', '')
    if not secret:
        raise RuntimeError('SECRET_KEY ausente; não é possível assinar a importação.')
    return secret.encode('utf-8')

def _tri_make_import_token(pairs, parsed, activity_key, applied_on, user, final=True):
    now = int(_tri_tok_time.time())
    records = []
    for pair in pairs:
        records.append({
            'id': str(pair['target']['id']),
            'scores': pair['source'].get('scores') or {},
        })
    payload = {
        'v': 1,
        'final': final,
        'actor': str(user.get('id') or ''),
        'activityKey': str(activity_key or ''),
        'date': str(applied_on or ''),
        'sheet': str(parsed.get('sheet') or ''),
        'iat': now,
        'exp': now + _TRI_TOKEN_TTL_SECONDS,
        'records': records,
    }
    raw = json.dumps(payload, ensure_ascii=False, separators=(',', ':'), sort_keys=True).encode('utf-8')
    signature = _tri_tok_hmac.new(_tri_token_secret(), raw, _tri_tok_hashlib.sha256).digest()
    return _tri_token_b64e(raw) + '.' + _tri_token_b64e(signature)

def _tri_read_import_token(token, user):
    token = str(token or '')
    if len(token) < 20 or len(token) > 1000000 or '.' not in token:
        raise ValueError('Pacote de importação inválido ou ausente.')
    encoded, signed = token.split('.', 1)
    raw = _tri_token_b64d(encoded)
    supplied = _tri_token_b64d(signed)
    expected = _tri_tok_hmac.new(_tri_token_secret(), raw, _tri_tok_hashlib.sha256).digest()
    if not _tri_tok_hmac.compare_digest(supplied, expected):
        raise ValueError('A assinatura da importação é inválida. Gere uma nova conferência.')
    try:
        payload = json.loads(raw.decode('utf-8'))
    except Exception as exc:
        raise ValueError('O pacote de importação está corrompido.') from exc
    if not isinstance(payload, dict) or payload.get('v') != 1:
        raise ValueError('Versão do pacote de importação não suportada.')
    if str(payload.get('actor') or '') != str(user.get('id') or ''):
        raise ValueError('Este pacote pertence a outra sessão de usuário.')
    if int(payload.get('exp') or 0) < int(_tri_tok_time.time()):
        raise ValueError('A conferência expirou. Confira os vínculos novamente antes de salvar.')
    records = payload.get('records')
    if not isinstance(records, list) or not records:
        raise ValueError('O pacote não possui registros para salvar.')
    if len(records) > 5000:
        raise ValueError('Quantidade de registros acima do limite de segurança.')
    return payload

def _tri_token_fetch_targets(app, c, ids, lock=False):
    rows = {}
    for offset in range(0, len(ids), 500):
        chunk = ids[offset:offset + 500]
        placeholders = ','.join('?' for _ in chunk)
        query = (
            'SELECT id,activity_key,applied_on,metadata FROM hmay_performance '
            'WHERE id IN (' + placeholders + ')'
        )
        if lock and not app.db.local_path:
            query += ' ORDER BY id FOR UPDATE'
        for row in app.db.execute(c, query, tuple(chunk)).fetchall():
            item = dict(row)
            rows[str(item['id'])] = item
    return rows

def _tri_token_verify_metadata(app, c, ids, records):
    targets = _tri_token_fetch_targets(app, c, ids)
    expected = {key: 0 for key in _TRI_TOKEN_SCORE_TO_META}
    actual = {key: 0 for key in _TRI_TOKEN_SCORE_TO_META}
    source_by_id = {str(item['id']): item.get('scores') or {} for item in records}
    for record_id, scores in source_by_id.items():
        if record_id not in targets:
            raise ValueError('Um resultado deixou de existir durante a gravação.')
        metadata = _rx_json(targets[record_id].get('metadata'))
        if _tri_apply_metadata(dict(metadata), scores, '', {'id': ''}):
            raise ValueError('As notas lidas no banco diferem das notas enviadas.')
        for score_key, meta_key in _TRI_TOKEN_SCORE_TO_META.items():
            source_value = scores.get(score_key)
            if source_value is None or source_value == '':
                continue
            expected[score_key] += 1
            stored = metadata.get(meta_key)
            if stored is not None and stored != '':
                actual[score_key] += 1
    return {
        key: {'expected': expected[key], 'stored': actual[key]}
        for key in expected
        if expected[key]
    }

_tri_token_original_handle = handle

def handle(app, c, user, path, method, data, query, start, HTTPError):
    if path == '/api/model-data/tri-coverage' and method == 'GET':
        _rx_role_guard(user, HTTPError)
        json_field = ("json_extract(p.metadata, '$.%s')" if app.db.local_path
                      else "(p.metadata::jsonb ->> '%s')")
        stamp = json_field % '_tri_imported_at'
        exam = json_field % '_exam_id'
        rows = app.db.execute(c, (
            "SELECT MIN(p.activity) AS activity, p.applied_on AS date, "
            "COUNT(DISTINCT p.user_id) AS total, "
            f"COUNT(DISTINCT CASE WHEN NULLIF({stamp}, '') IS NOT NULL THEN p.user_id END) AS saved "
            "FROM hmay_performance p JOIN hmay_users u ON u.id=p.user_id "
            f"WHERE u.role IN ('user','aluno') AND NULLIF({exam}, '') IS NOT NULL "
            "GROUP BY p.activity_key, p.applied_on ORDER BY p.applied_on DESC, MIN(p.activity)"
        )).fetchall()
        return app.reply(start, 200, {'simulations': [dict(row) for row in rows]})

    if path == '/api/model-data/tri-preview':
        _rx_role_guard(user, HTTPError)
        parsed, match, preview = _tri_preview(app, c, data)
        activity_key = F.text(data.get('activityKey'), 250)
        applied_on = F.date_value(data.get('date'))
        preview['unmatchedNames'] = match['unmatched'][:50]
        preview['conflictRows'] = match['conflicts'][:50]
        preview['withoutScoreNames'] = match['withoutScore'][:50]
        pairs = match['matched']
        if len(pairs) > 5000:
            raise ValueError('A conferência excede o limite de 5.000 registros.')
        if data.get('batchMode') is True:
            preview['batches'] = []
            for offset in range(0, len(pairs), _TRI_TOKEN_BATCH_SIZE):
                batch = pairs[offset:offset + _TRI_TOKEN_BATCH_SIZE]
                token = _tri_make_import_token(batch, parsed, activity_key, applied_on, user,
                                               final=(offset + len(batch) == len(pairs)))
                preview['batches'].append({'count': len(batch), 'importToken': token})
        else:
            preview['importToken'] = _tri_make_import_token(pairs, parsed, activity_key, applied_on, user)
        preview['tokenExpiresMinutes'] = _TRI_TOKEN_TTL_SECONDS // 60
        print(
            f'MEUCRONOGRAMA_TRI_TOKEN_PREVIEW matched={len(match["matched"])} token_records={len(match["matched"])}',
            flush=True,
        )
        return app.reply(start, 200, preview)


    if path == '/api/model-data/tri-confirm-prepare':
        _rx_role_guard(user, HTTPError)
        payload = _tri_read_import_token(data.get('importToken'), user)
        records = payload['records']
        ids = [str(item.get('id') or '') for item in records]
        if any(not item for item in ids) or len(set(ids)) != len(ids):
            raise ValueError('O pacote contém identificadores inválidos ou duplicados.')

        targets = _tri_token_fetch_targets(app, c, ids)
        if len(targets) != len(ids):
            raise ValueError('Um ou mais resultados vinculados não existem mais no banco.')

        activity_key = str(payload.get('activityKey') or '')
        applied_on = str(payload.get('date') or '')
        for record_id in ids:
            target = targets[record_id]
            if str(target.get('activity_key') or '') != activity_key or str(target.get('applied_on') or '') != applied_on:
                raise ValueError('O pacote não corresponde mais ao simulado selecionado.')

        print(
            f'MEUCRONOGRAMA_TRI_TOKEN_RECEIVED records={len(records)} activity={activity_key} date={applied_on}',
            flush=True,
        )
        return app.reply(start, 200, {
            'ready': True,
            'receivedRecords': len(records),
            'activityKey': activity_key,
            'date': applied_on,
        })

    if path == '/api/model-data/tri-confirm':
        _rx_role_guard(user, HTTPError)
        payload = _tri_read_import_token(data.get('importToken'), user)
        records = payload['records']
        ids = [str(item.get('id') or '') for item in records]
        if any(not item for item in ids) or len(set(ids)) != len(ids):
            raise ValueError('O pacote contém identificadores inválidos ou duplicados.')

        targets = _tri_token_fetch_targets(app, c, sorted(ids), lock=True)
        if len(targets) != len(ids):
            raise ValueError('Um ou mais resultados vinculados não existem mais no banco.')

        activity_key = str(payload.get('activityKey') or '')
        applied_on = str(payload.get('date') or '')
        for record_id in ids:
            target = targets[record_id]
            if str(target.get('activity_key') or '') != activity_key or str(target.get('applied_on') or '') != applied_on:
                raise ValueError('O pacote não corresponde mais ao simulado selecionado.')

        pending = []
        unchanged = 0
        for item in records:
            record_id = str(item['id'])
            metadata = _rx_json(targets[record_id].get('metadata'))
            if _tri_apply_metadata(
                metadata,
                item.get('scores') or {},
                str(payload.get('sheet') or ''),
                user,
            ):
                pending.append((
                    record_id,
                    json.dumps(metadata, ensure_ascii=False, separators=(',', ':')),
                ))
            else:
                unchanged += 1

        print(
            f'MEUCRONOGRAMA_TRI_TOKEN_CONFIRM_RECEIVED records={len(records)} pending={len(pending)} unchanged={unchanged}',
            flush=True,
        )

        updated = 0
        stamp = P.now().isoformat()
        for offset in range(0, len(pending), _TRI_TOKEN_BATCH_SIZE):
            chunk = pending[offset:offset + _TRI_TOKEN_BATCH_SIZE]
            cases = ' '.join('WHEN ? THEN ?' for _ in chunk)
            placeholders = ','.join('?' for _ in chunk)
            params = []
            for row_id, metadata_json in chunk:
                params.extend((row_id, metadata_json))
            params.append(stamp)
            params.extend(row_id for row_id, _ in chunk)
            sql = (
                'UPDATE hmay_performance SET metadata=CASE id ' + cases +
                ' ELSE metadata END,updated_at=? WHERE id IN (' + placeholders + ')'
            )
            app.db.execute(c, sql, tuple(params))
            updated += len(chunk)
            print(
                f'MEUCRONOGRAMA_TRI_TOKEN_BATCH_DONE updated={updated}/{len(pending)}',
                flush=True,
            )

        verification = _tri_token_verify_metadata(app, c, ids, records)
        mismatches = {
            key: value for key, value in verification.items()
            if value['expected'] != value['stored']
        }
        if mismatches:
            raise RuntimeError('A verificação final das notas no banco não coincidiu com o pacote enviado.')

        if payload.get('final', True):
            app.event(c, user, user['id'], 'tri_scores_import')
        print(
            f'MEUCRONOGRAMA_TRI_TOKEN_DONE updated={updated} unchanged={unchanged} verified={len(records)}',
            flush=True,
        )
        return app.reply(start, 200, {
            'summary': {
                'updated': updated,
                'unchanged': unchanged,
                'matched': len(records),
                'unmatched': 0,
                'conflicts': 0,
                'withoutScore': 0,
            },
            'verification': verification,
            'verifiedRecords': len(records),
            'tokenMode': True,
        })

    return _tri_token_original_handle(app, c, user, path, method, data, query, start, HTTPError)
'''

FRONTEND = r'''
// === TRI IMPORT TOKEN V1 ===
function triPercent(count,total){
 if(!total)return '0%';
 const value=count===total?100:Math.min(99.9,Math.round(1000*count/total)/10);
 return value.toLocaleString('pt-BR')+'%';
}

let triCoverage=null;
let triCoverageLoading=false;
function triCoverageHtml(){
 if(!triCoverage)return '';
 if(triCoverage.error)return '<p role="alert">'+esc(triCoverage.error)+'</p>';
 if(!triCoverage.length)return '<p>Nenhum simulado com resultados cadastrados.</p>';
 const rows=triCoverage.map(row=>'<tr><td>'+esc(row.activity)+'</td><td>'+esc(br(row.date))+'</td><td>'+row.total+'</td><td>'+row.saved+'</td><td>'+triPercent(row.saved,row.total)+'</td></tr>').join('');
 return '<div class="table-wrap"><table><caption>Alunos com importação de notas TRI/Redação registrada no banco</caption><thead><tr><th>Simulado</th><th>Aplicação</th><th>Participantes</th><th>Com notas importadas</th><th>% do simulado</th></tr></thead><tbody>'+rows+'</tbody></table></div>';
}
async function triLoadCoverage(){
 if(triCoverageLoading)return;
 triCoverageLoading=true;
 try{triCoverage=(await api('/api/model-data/tri-coverage')).simulations;}
 catch(error){triCoverage={error:error.message};}
 finally{
  triCoverageLoading=false;
  const el=document.getElementById('tri-coverage');
  if(el)el.innerHTML=triCoverageHtml();
 }
}
acts['tri-coverage']=triLoadCoverage;

acts['tri-import-preview']=async()=>{
 if(triImportBusy)return;
 const sim=triSelectedSimulation();
 if(!sim)throw new Error('Selecione o simulado que receberá as notas.');
 triImportDraft.simulationId=sim.id;
 triImportPreviewData=null;
 triImportProcess=null;
 triImportSaveSummary=null;
 triImportBusy=true;
 render();
 try{
  const preview=await api('/api/model-data/tri-preview',{
   file:triImportDraft.file,filename:triImportDraft.filename,
   activityKey:sim.activityKey,date:sim.date,batchMode:true
  });
  if(!Array.isArray(preview.batches)||preview.batches.some(b=>!b.importToken||!Number.isInteger(b.count)||b.count<1)||
     preview.batches.reduce((n,b)=>n+b.count,0)!==preview.matched){
   throw new Error('O servidor não confirmou os lotes desta prévia. Confira os vínculos novamente.');
  }
  triImportPreviewData=preview;
  triImportProcess={state:'preview',matched:preview.matched,students:preview.students,
   received:0,verified:0,updated:0,unchanged:0,nextBatch:0};
 }finally{
  triImportBusy=false;
  render();
 }
};

function triImportProcessHtml(){
 const p=triImportProcess;
 if(!triImportDraft?.inspection||!p)return '';
 const step=(n,label,note,complete,active=false,failed=false)=>{
  const cls=failed?'error':complete?'done':active?'active':'pending';
  const icon=failed?'!':complete?'✓':active?'…':String(n);
  return '<div class="tri-import-step '+cls+'"><span>'+icon+'</span><div><strong>'+n+'. '+label+'</strong><small>'+note+'</small></div></div>';
 };
 const total=p.matched;
 const meter=(count,label)=>{
  const text=count+' de '+total+' ('+triPercent(count,total)+')';
  return text+'<progress aria-label="'+label+'" aria-valuetext="'+text+'" value="'+count+'" max="'+Math.max(total,1)+'"></progress>';
 };
 const done=p.state==='done';
 let message='Aguardando confirmação da gravação.';
 if(!total)message='Nenhum resultado vinculado para enviar.';
 if(done)message=p.verified+' confirmados no banco. '+p.updated+' atualizados e '+p.unchanged+' já conferiam com a planilha.';
 if(p.state==='error')message=esc(p.error)+' Confira os totais acima. Use Retomar envio ou faça uma nova conferência se a prévia expirou.';
 return '<section class="tri-import-process-card"><h3>Etapas da importação</h3>'+
  step(1,'Arquivo lido',esc(triImportDraft.inspection.sheet||'Planilha reconhecida'),true)+
  step(2,'Alunos vinculados',p.matched+' de '+p.students+' alunos do simulado.',true)+
  step(3,'Envio ao servidor','Recebidos pelo servidor: '+meter(p.received,'Resultados recebidos pelo servidor'),total>0&&p.received===total,p.state==='sending',p.state==='error'&&p.stage===3)+
  step(4,'Gravação das notas','Confirmados no banco: '+meter(p.verified,'Resultados confirmados no banco'),done,p.state==='saving',p.state==='error'&&p.stage===4)+
  step(5,'Finalização',message,done)+'</section>';
}

acts['tri-import-confirm']=async()=>{
 if(triImportBusy)return;
 const sim=triSelectedSimulation(),preview=triImportPreviewData,p=triImportProcess;
 if(!sim||!preview||!p||sim.id!==triImportDraft.simulationId)throw new Error('Confira os vínculos antes de enviar.');
 if(!p.matched)throw new Error('Não há resultados vinculados para enviar.');
 if(!confirm('Salvar as notas conferidas de '+sim.activity+' ('+br(sim.date)+')?'))return;
 triImportBusy=true;
 p.state='sending';
 render();
 try{
  while(p.nextBatch<preview.batches.length){
   const {importToken,count}=preview.batches[p.nextBatch];
   p.stage=3;
   p.state='sending';
   triImportUpdateProcessDom();
   const receipt=await api('/api/model-data/tri-confirm-prepare',{importToken});
   if(!receipt.ready||receipt.receivedRecords!==count)throw new Error('O servidor não confirmou o recebimento do lote.');
   p.received=p.verified+count;
   p.stage=4;
   p.state='saving';
   triImportUpdateProcessDom();
   const result=await api('/api/model-data/tri-confirm',{importToken});
   const {updated,unchanged}=result.summary||{};
   if(result.verifiedRecords!==count||!Number.isInteger(updated)||!Number.isInteger(unchanged)||
      updated<0||unchanged<0||updated+unchanged!==count){
    throw new Error('Falta a confirmação da gravação deste lote.');
   }
   p.verified+=count;
   p.updated+=updated;
   p.unchanged+=unchanged;
   p.nextBatch++;
   triImportUpdateProcessDom();
  }
  p.state='done';
  triImportSaveSummary={summary:{updated:p.updated,unchanged:p.unchanged,unmatched:preview.unmatched,
   conflicts:preview.conflicts,withoutScore:preview.withoutScore},issues:preview};
  triImportPreviewData=null;
  toast('Importação concluída: '+p.verified+' resultados confirmados no banco.');
 }catch(error){
  p.state='error';
  p.error=error.message||'A conexão foi interrompida.';
  toast(p.error,true);
 }finally{
  triImportBusy=false;
  if(p.verified){
   if(typeof studentSummaryCache!=='undefined')studentSummaryCache?.clear?.();
   if(typeof resultExportSimulations!=='undefined')resultExportSimulations=null;
   if(typeof managementDashboardCache!=='undefined')managementDashboardCache=null;
   if(typeof managementClassAnalyticsCache!=='undefined'){
    managementClassAnalyticsCache=null;
    managementClassDetailCache.clear();
    managementStudentDetailCache.clear();
   }
  }
  render();
  if(triCoverage)await triLoadCoverage();
 }
};

document.addEventListener('change',event=>{
 if(event.target?.name==='tri-import-simulation'){
  triImportProcess=null;
  triImportSaveSummary=null;
 }
},true);
'''

def main():
    model=ROOT/"model_data.py"
    model_text=model.read_text(encoding="utf-8")
    if BACKEND_MARK not in model_text:
        model_text=model_text.rstrip()+"\n\n"+BACKEND.strip()+"\n"
        model.write_text(model_text,encoding="utf-8")

    js=ROOT/"static"/"tri_scores.js"
    js_text=js.read_text(encoding="utf-8")
    if FRONTEND_MARK not in js_text:
        # The inspect action must release the controls before its final render.
        js_text = js_text.replace('triImportPreviewData=null;render();}finally{triImportBusy=false;}',
                                  'triImportPreviewData=null;}finally{triImportBusy=false;render();}')
        js_text=js_text.rstrip()+"\n\n"+FRONTEND.strip()+"\n"
        js.write_text(js_text,encoding="utf-8")

    html=ROOT/"static"/"app.html"
    html_text=html.read_text(encoding="utf-8")
    html_text=html_text.replace('/static/tri_scores.js?v=3.2.0','/static/tri_scores.js?v=3.2.2')
    html.write_text(html_text,encoding="utf-8")

    print("MEUCRONOGRAMA_TRI_IMPORT_TOKEN_READY: XLSX is parsed only during preview; confirm uses a signed structured token.",flush=True)

if __name__=="__main__":
    main()
