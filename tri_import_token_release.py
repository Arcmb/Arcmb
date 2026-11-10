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

def _tri_make_import_token(match, parsed, activity_key, applied_on, user):
    now = int(_tri_tok_time.time())
    records = []
    for pair in match.get('matched', []):
        records.append({
            'id': str(pair['target']['id']),
            'scores': pair['source'].get('scores') or {},
        })
    payload = {
        'v': 1,
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

def _tri_token_fetch_targets(app, c, ids):
    rows = {}
    for offset in range(0, len(ids), 500):
        chunk = ids[offset:offset + 500]
        placeholders = ','.join('?' for _ in chunk)
        query = (
            'SELECT id,activity_key,applied_on,metadata FROM hmay_performance '
            'WHERE id IN (' + placeholders + ')'
        )
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
        metadata = _rx_json((targets.get(record_id) or {}).get('metadata'))
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
    if path == '/api/model-data/tri-preview':
        _rx_role_guard(user, HTTPError)
        parsed, match, preview = _tri_preview(app, c, data)
        activity_key = F.text(data.get('activityKey'), 250)
        applied_on = F.date_value(data.get('date'))
        preview['unmatchedNames'] = match['unmatched'][:50]
        preview['conflictRows'] = match['conflicts'][:50]
        preview['withoutScoreNames'] = match['withoutScore'][:50]
        preview['importToken'] = _tri_make_import_token(
            match, parsed, activity_key, applied_on, user
        )
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

        targets = _tri_token_fetch_targets(app, c, ids)
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
acts['tri-import-preview']=async()=>{
 const sim=triSelectedSimulation();if(!sim)throw new Error('Selecione o simulado que receberá as notas.');
 triImportDraft.simulationId=sim.id;triImportBusy=true;
 try{
  triImportPreviewData=await api('/api/model-data/tri-preview',{
   file:triImportDraft.file,
   filename:triImportDraft.filename,
   activityKey:sim.activityKey,
   date:sim.date
  });
  if(!triImportPreviewData||!triImportPreviewData.importToken)throw new Error('O servidor não devolveu o pacote seguro da importação.');
  triImportDraft.importToken=triImportPreviewData.importToken;
  triImportProcess={
   state:'preview',
   matched:triImportPreviewData.matched||0,
   students:triImportPreviewData.students||0
  };
  render();
 }finally{triImportBusy=false;}
};

function triImportProcessHtml(){
 const p=triImportProcess;
 const inspection=triImportDraft?.inspection;
 const preview=triImportPreviewData;
 if(!inspection&&!p)return '<div id="tri-import-process"></div>';
 const matched=Number(p?.matched??preview?.matched??0);
 const students=Number(p?.students??preview?.students??0);
 const received=Number(p?.received??0);
 const verified=Number(p?.verified??0);
 const state=p?.state||'preview';
 const errorStage=Number(p?.errorStage||0);

 const isDone=n=>{
  if(state==='done')return true;
  if(state==='saving'||state==='received')return n<=3;
  if(state==='sending')return n<=2;
  if(state==='preview')return n<=2;
  if(state==='error')return n<errorStage;
  return false;
 };
 const isActive=n=>{
  if(state==='sending'&&n===3)return true;
  if((state==='received'||state==='saving')&&n===4)return true;
  if(state==='error'&&n===errorStage)return true;
  return false;
 };
 const cls=n=>isDone(n)?'done':isActive(n)?(state==='error'?'error':'active'):'pending';
 const icon=n=>isDone(n)?'✓':isActive(n)?(state==='error'?'!':'…'):String(n);

 let note3=matched?matched+' registro(s) preparados para envio.':'Dados preparados para envio.';
 if(state==='sending')note3='Enviando '+matched+' registro(s) ao servidor…';
 if(received>0)note3=received+'/'+matched+' registro(s) recebidos e validados pelo servidor.';
 if(state==='error'&&errorStage===3)note3='O servidor não confirmou o recebimento dos registros.';

 let note4='Aguardando a confirmação de recebimento do servidor.';
 if(state==='received')note4='Recebimento confirmado. Iniciando gravação de '+received+' registro(s).';
 if(state==='saving')note4='Servidor gravando '+received+' registro(s) no banco online.';
 if(state==='done')note4=(p?.updated??0)+' atualizado(s) e '+(p?.unchanged??0)+' sem alteração.';
 if(state==='error'&&errorStage===4)note4='Falha durante a gravação no banco online.';

 let note5='Aguardando verificação final no banco.';
 if(state==='done')note5=verified+' registro(s) confirmados no banco online.';
 if(state==='error'&&errorStage===5)note5='A verificação final não foi concluída.';

 return '<section class="tri-import-process-card"><h3>Etapas da importação</h3>'+
  '<div class="tri-import-step '+cls(1)+'"><span>'+icon(1)+'</span><div><strong>1. Arquivo lido</strong><small>'+esc(inspection?.sheet||'Planilha reconhecida')+'</small></div></div>'+
  '<div class="tri-import-step '+cls(2)+'"><span>'+icon(2)+'</span><div><strong>2. Alunos vinculados</strong><small>'+matched+'/'+students+' aluno(s) vinculados ao simulado.</small></div></div>'+
  '<div class="tri-import-step '+cls(3)+'"><span>'+icon(3)+'</span><div><strong>3. Envio ao servidor</strong><small>'+note3+'</small></div></div>'+
  '<div class="tri-import-step '+cls(4)+'"><span>'+icon(4)+'</span><div><strong>4. Gravação das notas</strong><small>'+note4+'</small></div></div>'+
  '<div class="tri-import-step '+cls(5)+'"><span>'+icon(5)+'</span><div><strong>5. Finalização</strong><small>'+note5+'</small></div></div>'+
  '</section>';
}

acts['tri-import-confirm']=async()=>{
 const sim=triSelectedSimulation();
 if(!sim||!triImportPreviewData)throw new Error('Gere a conferência antes de confirmar.');
 const importToken=(triImportDraft&&triImportDraft.importToken)||triImportPreviewData.importToken;
 if(!importToken)throw new Error('Pacote seguro ausente. Faça a conferência novamente.');
 if(!confirm('Salvar as notas conferidas de '+sim.activity+' ('+sim.date+')?'))return;

 const expected=Number(triImportPreviewData.matched||0);
 triImportBusy=true;
 triImportProcess={
  state:'sending',
  matched:expected,
  students:Number(triImportPreviewData.students||0),
  received:0,
  verified:0
 };
 triImportUpdateProcessDom();
 const saveButton=document.querySelector('[data-act="tri-import-confirm"]');
 if(saveButton){saveButton.disabled=true;saveButton.textContent='Enviando '+expected+' registros…';}

 let confirmedReceived=false;
 try{
  const receipt=await api('/api/model-data/tri-confirm-prepare',{importToken});
  const received=Number(receipt?.receivedRecords||0);
  if(!receipt?.ready||received!==expected){
   throw new Error('O servidor confirmou '+received+' de '+expected+' registros. A gravação foi cancelada.');
  }

  confirmedReceived=true;
  triImportProcess={...triImportProcess,state:'received',received};
  triImportUpdateProcessDom();
  if(saveButton)saveButton.textContent='Recebidos '+received+' · gravando…';

  triImportProcess={...triImportProcess,state:'saving'};
  triImportUpdateProcessDom();

  const d=await api('/api/model-data/tri-confirm',{importToken});
  if(typeof studentSummaryCache!=='undefined')studentSummaryCache?.clear?.();
  if(typeof resultExportSimulations!=='undefined')resultExportSimulations=null;
  triImportSaveSummary=d;
  const verified=Number(d.verifiedRecords!=null?d.verifiedRecords:((d.summary&&d.summary.matched)||0));
  triImportProcess={
   state:'done',
   matched:expected,
   students:triImportProcess.students||0,
   received,
   verified,
   updated:Number(d.summary?.updated||0),
   unchanged:Number(d.summary?.unchanged||0)
  };
  triImportPreviewData=null;
  if(triImportDraft)triImportDraft.importToken=null;
  toast('Importação concluída: '+verified+' registro(s) confirmados no banco.');
 }catch(error){
  const message=(error&&error.message)||'erro inesperado ao gravar as notas';
  triImportProcess={
   ...(triImportProcess||{}),
   state:'error',
   errorStage:confirmedReceived?4:3
  };
  toast('Não foi possível concluir a importação: '+message,true);
 }finally{
  triImportBusy=false;
  render();
 }
};

document.addEventListener('change',event=>{
 if(event.target&&event.target.name==='tri-import-simulation'&&triImportDraft){
  triImportDraft.importToken=null;
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
        js_text=js_text.rstrip()+"\n\n"+FRONTEND.strip()+"\n"
        js.write_text(js_text,encoding="utf-8")

    html=ROOT/"static"/"app.html"
    html_text=html.read_text(encoding="utf-8")
    html_text=html_text.replace('/static/tri_scores.js?v=3.2.0','/static/tri_scores.js?v=3.2.2')
    html.write_text(html_text,encoding="utf-8")

    print("MEUCRONOGRAMA_TRI_IMPORT_TOKEN_READY: XLSX is parsed only during preview; confirm uses a signed structured token.",flush=True)

if __name__=="__main__":
    main()
