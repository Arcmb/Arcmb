"""Single-workbook templates and atomic imports. No scheduling or account mutations."""
from __future__ import annotations
import base64, csv, hashlib, hmac, io, json, time
import performance as F
import selective as S
import exams as E
import templates_v23 as T
import planner as P

RESULTS='Resultados'
QUESTIONS='Questoes'
CONFIG='Simulado'
CONFIG_HEADERS=['TIPO de prova','data de aplicação','COR DA PROVA','ÁREA DAS HABILIDADES']

def encode(x):
    return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)

def template(data):
    chosen=data.get('fields',[])
    if not isinstance(chosen,list) or not 1<=len(chosen)<=300:
        raise ValueError('Selecione entre 1 e 300 colunas.')
    headers=[S.label(S.canonical(F.text(x,200))) for x in chosen]
    canonical=[S.canonical(x) for x in headers]
    if len(set(canonical))!=len(canonical):raise ValueError('Há campos repetidos.')
    if not all(x in canonical for x in ('NOME','TIPO','data')):
        raise ValueError('Nome, tipo de prova e data de aplicação identificam os resultados.')
    # Validate accepted fields through the existing template path as well.
    S.template({'fields':chosen,'format':'csv'})
    numbers=sorted(int(x.rsplit(' ',1)[-1]) for x in headers if x.startswith('Acerto/erro questão '))
    first=F.count_value(data.get('questionFirst',1),'Questão inicial')
    last=F.count_value(data.get('questionLast',180),'Questão final')
    if first is None or last is None or not 1<=first<=last<=180:
        raise ValueError('As questões variam de 01 a 180; a inicial não pode ser maior que a final.')
    if not numbers:numbers=list(range(first,last+1))
    guide=[
        ['1. Resultados','Uma linha por aluno e avaliação. Somente as colunas marcadas foram incluídas. Nome, tipo de prova e data identificam o registro.'],
        ['2. Questoes','Uma linha por questão: área, disciplina, tópico, assunto e habilidade. O mesmo mapa serve a todos os alunos deste simulado e cor.'],
        ['3. Simulado','Informe nome da avaliação, data e cor (Única para prova sem cores). Esses dados devem coincidir com os resultados. Um arquivo combinado corresponde a uma avaliação e cor.'],
        ['Importação','Desempenho → Importar arquivo único. Confira as contas dos alunos, o mapa e a prévia. Nada é gravado antes da confirmação.'],
        ['Acerto/erro','Use somente 1 = acerto e 0 = erro. Vazio = resultado não informado. Não use Acerto/Erro, C/E nem a alternativa marcada.'],
        ['Questões e habilidades','Questões de 01 a 180; habilidades H01 a H30, sempre identificadas junto da área LC/CH/CN/MT.'],
        ['Totais por habilidade','São opcionais. Com acerto/erro e mapa completo, o site calcula o detalhamento sem preencher os totais manualmente. Se enviar Acertos Hab, informe ÁREA DAS HABILIDADES em Simulado.'],
        ['Percentuais','Aproveitamento = acertos / questões com resultado. Cobertura = questões com resultado / questões do mapa. Percentual final só é mostrado quando não há resultados pendentes.'],
        ['Dados parciais','Colunas ou células vazias não apagam resultados. Linhas da aba Questoes com apenas o número são ignoradas. Classificações faltantes podem ser completadas depois.'],
        ['Língua estrangeira','Para versões Inglês/Espanhol com o mesmo número, duplique a linha na aba Questoes e informe a língua. No resultado, informe a língua escolhida pelo aluno.'],
        ['Conferência','O site separa totais importados e valores calculados. Eles não são somados nem tratados como equivalentes quando incompletos.'],
        ['Reimportação','Mantenha a mesma conta, avaliação, data e cor. Dados novos complementam; substituir valores existentes exige opção explícita.'],
        ['Sem inferências','O sistema não infere assunto, habilidade ou domínio de uma nota TRI; não calcula novo TRI e não altera o cronograma nesta importação.']]
    return T.export(headers,kind='xlsx',guide=guide,first_name=RESULTS,
        extra_sheets=[(QUESTIONS,E.HEADERS,[[n]+['']*7 for n in numbers]),(CONFIG,CONFIG_HEADERS,[['','','','']])])

def _load(data,sheet):
    matrix,ep,sheets,selected,blob=S.matrix({**data,'sheet':sheet})
    return matrix,ep,sheets,selected,blob

def _has_data(row):return any(v is not None and str(v).strip() for v in row)

def inspect(data):
    if not str(data.get('filename','')).lower().endswith('.xlsx'):
        raise ValueError('O arquivo único com várias abas deve ser Excel .xlsx. Use a importação anterior para CSV.')
    rows,ep,sheets,_,blob=_load(data,'')
    for name in (RESULTS,QUESTIONS,CONFIG):
        if name not in sheets:raise ValueError('Use o modelo único com as abas Resultados, Questoes e Simulado. Para outro formato, use a importação de resultados ou mapa separadamente.')
    rr,rep,_,_,_=_load(data,RESULTS)
    qq,_,_,_,_=_load(data,QUESTIONS)
    cc,cep,_,_,_=_load(data,CONFIG)
    if not rr or not qq or not cc:raise ValueError('Mantenha os cabeçalhos das três abas.')
    config_rows=[r for r in cc[1:] if _has_data(r)]
    if len(config_rows)>1:raise ValueError('A aba Simulado deve conter somente uma avaliação/cor. Separe avaliações em arquivos diferentes.')
    cfg={}
    if config_rows:
        row=config_rows[0]
        for i,h in enumerate(cc[0]):
            val=row[i] if i<len(row) else None
            if val is None or not str(val).strip():continue
            k=S.canonical(h)
            if k=='data':val=F.date_value(val,cep)
            cfg[k]=str(val).strip()
    rrows=[r for r in rr[1:] if _has_data(r)]
    # Infer only identification metadata from supplied cells, never classifications.
    for i,h in enumerate(rr[0]):
        k=S.canonical(h)
        if k not in ('TIPO','data','COR DA PROVA'):continue
        values=[]
        for row in rrows:
            v=row[i] if i<len(row) else None
            if v is None or not str(v).strip():continue
            val=F.date_value(v,rep) if k=='data' else str(v).strip()
            if val not in values:values.append(val)
        if len({F.norm(x) for x in values})>1:raise ValueError('O arquivo único deve conter a mesma avaliação, data e cor em todas as linhas. Separe as provas em lotes.')
        if values:
            if k in cfg and F.norm(cfg[k])!=F.norm(values[0]):raise ValueError('As abas Simulado e Resultados divergem em '+k+'.')
            cfg.setdefault(k,values[0])
    question_columns={i:E.ALIASES.get(F.norm(S.fix_header(h)),'') for i,h in enumerate(qq[0])}
    relevant=[]
    for r in qq[1:]:
        if any(i<len(r) and v and v!='QUESTÃO' and r[i] is not None and str(r[i]).strip() for i,v in question_columns.items()):relevant.append(r)
    return dict(sheets=sheets,headers=rr[0],rows=len(rrows),classifiedRows=len(relevant),
                title=cfg.get('TIPO',''),date=cfg.get('data',''),color=cfg.get('COR DA PROVA',''),
                skillArea=cfg.get('ÁREA DAS HABILIDADES',''),_questionRows=[qq[0]]+relevant,_config=cfg,
                hash=hashlib.sha256(blob).hexdigest())

def _csv(rows):
    out=io.StringIO();w=csv.writer(out,delimiter=';',lineterminator='\n');w.writerows(rows)
    return {'filename':'mapa.csv','file':base64.b64encode(out.getvalue().encode('utf-8')).decode()}

def prepare(app,c,user,data):
    info=inspect(data)
    values={}
    for key in ('title','date','color','skillArea'):
        v=F.text(data.get(key) or info[key],200 if key=='title' else 80)
        if key=='date' and v:v=F.date_value(v)
        if info[key] and v and F.norm(v)!=F.norm(info[key]):raise ValueError('O campo '+key+' diverge do arquivo. Corrija a planilha ou mantenha a informação lida.')
        values[key]=v
    if values['skillArea']:values['skillArea']=E.area(values['skillArea'])
    if values['skillArea'] not in S.AREAS+['']:raise ValueError('Área das habilidades inválida.')
    if not values['title'] or not values['date'] or not values['color']:
        raise ValueError('Informe nome da avaliação, data e cor na aba Simulado ou na conferência. Use Única para uma prova sem cores.')
    for flag in ('replace','replaceMap'):
        if type(data.get(flag,False))is not bool:raise ValueError('Opção de substituição inválida.')
    identity=hashlib.sha256(E.enc([F.norm(values['title']),values['date'],F.norm(values['color'])]).encode()).hexdigest()
    found=_exam_metadata.find_import_map(app, c, values['title'], values['date'], values['color'])
    old=E.get_exam(app,c,found['id']) if found else None
    exam=old;map_summary=dict(new=0,updated=0,conflicts=0,total=len(old['items']) if old else 0)
    map_changed=False
    if info['classifiedRows']:
        args={**_csv(info['_questionRows']),**values,'area':old['area'] if old else '','replace':data.get('replaceMap',False),'examId':old['id'] if old else ''}
        if old and not _exam_metadata.can_edit(user):
            supplied=E.parse(args)['items'];existing={(x['number'],x['language']):x for x in old['items']}
            for item in supplied:
                current=existing.get((item['number'],item['language']))
                if current is None or any(v not in ('',None) and current.get(k)!=v for k,v in item.items()):
                    raise ValueError('A edição dos mapas é exclusiva do Master e da coordenação.')
        else:
            exam,map_summary,_=E.prepared(app,c,user,args)
            map_changed=not old or exam['items']!=old['items'] or exam['area']!=old['area']
            if not old:exam['id']=_exam_metadata.available_import_id(app, c, 'wb_' + identity[:32])
            exam['version']=(old['version'] if old else 0)+(1 if map_changed else 0)
    if info['rows']:
        payload={'file':data['file'],'filename':data['filename'],'sheet':RESULTS,'skillArea':values['skillArea'],
                 'replace':data.get('replace',False),'mapping':data.get('mapping',{})}
        if exam:payload['_validatedExam']=exam;payload['examId']=exam['id']
        parsed,accounts,resolved,prepared,conflicts,unresolved,fpayload=F.prepare_import(app,c,user,payload)
        for r in parsed['records']:
            if F.norm(r['activity'])!=F.norm(values['title']) or r['date']!=values['date']:
                raise ValueError('Todas as linhas precisam coincidir com a avaliação e data da aba Simulado.')
            if r['metadata'].get('COR DA PROVA') and F.norm(r['metadata']['COR DA PROVA'])!=F.norm(values['color']):raise ValueError('Cor diferente entre as abas.')
            # A file without a classified map still stores the declared color.
        if not exam:
            for item in prepared:
                before=dict(item['metadata']);S.guard_merge(item['metadata'],{'COR DA PROVA':values['color']})
                item['metadata']['COR DA PROVA']=values['color'];item['changed']=item['changed'] or item['metadata']!=before
    else:
        parsed={'students':[],'subjects':[]};accounts=[];resolved={};prepared=[];conflicts=unresolved=0;fpayload='no-results'
    if not info['rows'] and not info['classifiedRows']:raise ValueError('O arquivo está vazio. Preencha ao menos resultados ou a classificação de uma questão.')
    summary=dict(rows=info['rows'],linked=len(prepared),new=sum(x['existing']is None for x in prepared),
                 updated=sum(x['existing']is not None and x['changed'] for x in prepared),
                 unchanged=sum(not x['changed'] for x in prepared),conflicts=conflicts,unresolved=unresolved,
                 skipped=info['rows']-len(prepared),map=map_summary,mapChanged=map_changed,
                 linkedMap=bool(exam),title=values['title'],date=values['date'],color=values['color'])
    signed=encode(['workbook-2.4',user['id'],info['hash'],values,fpayload,exam,map_changed,
                   old['version'] if old else 0,data.get('replaceMap',False)])
    return dict(info=info,values=values,exam=exam,old=old,mapChanged=map_changed,identity=identity,
                prepared=prepared,parsed=parsed,accounts=accounts,mapping=resolved,summary=summary,signed=signed)

def confirm(app,c,user,p,HTTPError):
    at=P.now().isoformat();exam=p['exam'];old=p['old'];db=app.db
    if p['mapChanged']:
        import disciplines_catalog as _DC;_DC.canon_items(app,c,exam['items'])  # === DISCIPLINES CATALOG V3.12.0 ===
        if old:
            cur=db.execute(c,'UPDATE hmay_exams SET items=?,area=?,version=version+1,updated_at=? WHERE id=? AND version=?',
                (E.enc(exam['items']),exam['area'],at,exam['id'],old['version']))
        else:
            _exam_metadata.release_obsolete_key(app, c, p['identity'])
            cur=db.execute(c,'INSERT INTO hmay_exams(id,identity_key,owner_id,title,applied_on,color,area,items,version,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(identity_key) DO NOTHING',
                (exam['id'],p['identity'],user['id'],exam['title'],exam['applied_on'],exam['color'],exam['area'],E.enc(exam['items']),1,at))
        if cur.rowcount!=1:raise HTTPError(409,'O mapa mudou durante a importação. Nada deste lote foi salvo; refaça a conferência.')
    for item in sorted(p['prepared'],key=lambda x:(x['target'],x['record']['activityKey'],x['record']['date'])):
        if not item['changed']:continue
        r=item['record'];previous=item['existing']
        if previous:
            cur=db.execute(c,'UPDATE hmay_performance SET metrics=?,metadata=?,version=version+1,updated_at=? WHERE id=? AND version=?',
               (encode(item['metrics']),encode(item['metadata']),at,previous['id'],previous['version']))
        else:
            cur=db.execute(c,'INSERT INTO hmay_performance(id,user_id,activity_key,activity,applied_on,metrics,metadata,version,updated_at) VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(user_id,activity_key,applied_on) DO NOTHING',
                (P.uid(),item['target'],r['activityKey'],r['activity'],r['date'],encode(item['metrics']),encode(item['metadata']),1,at))
        if cur.rowcount!=1:raise HTTPError(409,'Os resultados mudaram durante a importação. Nada deste lote foi salvo; refaça a conferência.')
    if p['mapChanged']:app.event(c,user,user['id'],'unified_exam_import')
    for target in {x['target']for x in p['prepared']if x['changed']}:app.event(c,user,target,'unified_results_import')

def analyse(exam,metrics,metadata):
    lang=E.language(metadata.get('L.E',''));groups={k:{}for k in ('Área','Disciplina','Tópico','Assunto','Habilidade')}
    details=[];known=set();missing_language=False
    for item in exam['items']:
        if item['language']:
            if not lang:missing_language=True;continue
            if item['language']!=lang:continue
        n=item['number'];known.add(n);value=metrics.get(f'questao:{n:03d}',{}).get('correct')
        value=value if type(value)in (int,float) and value in (0,1) else None
        details.append({**item,'result':value,'status':'não informado' if value is None else 'acerto' if value==1 else 'erro'})
        pairs=[('Área',item['area']),('Disciplina',item['discipline']),
           ('Tópico',item['discipline']+' · '+item['topic']if item['topic']else''),
           ('Assunto',item['discipline']+' · '+item['subject']if item['subject']else''),
           ('Habilidade',item['area']+' · '+item['skill']if item['skill']else'')]
        for kind,name in pairs:
            if not name:continue
            group=groups[kind].setdefault(name,dict(name=name,correct=0,errors=0,marked=0,total=0,correctQuestions=[],errorQuestions=[],pendingQuestions=[]))
            group['total']+=1
            if value is None:group['pendingQuestions'].append(n)
            else:
                group['marked']+=1
                if value==1:group['correct']+=1;group['correctQuestions'].append(n)
                else:group['errors']+=1;group['errorQuestions'].append(n)
    def ratios(x):
        x['pending']=x['total']-x['marked']
        x['accuracy']=round(100*x['correct']/x['marked'],2) if x['marked'] else None
        x['coverage']=round(100*x['marked']/x['total'],2) if x['total'] else None
        x['percentFinal']=round(100*x['correct']/x['total'],2) if x['total'] and x['marked']==x['total'] else None
        return x
    for values in groups.values():
        for group in values.values():ratios(group)
    overall=ratios(dict(total=len(details),marked=sum(x['result']is not None for x in details),correct=sum(x['result']==1 for x in details),errors=sum(x['result']==0 for x in details)))
    if missing_language:overall['percentFinal']=None
    unknown=[int(k.split(':')[1]) for k,v in metrics.items() if k.startswith('questao:') and int(k.split(':')[1])not in known and v.get('correct')is not None]
    if unknown:overall['percentFinal']=None
    return dict(exam=exam['title'],version=exam['version'],color=exam['color'],groups={k:list(v.values()) for k,v in groups.items()},
        overall=overall,questions=details,unclassified=len(unknown),unclassifiedQuestions=unknown,languageMissing=missing_language,
        notice='Aproveitamento = acertos entre questões com resultado; cobertura = resultados informados sobre questões do mapa. Percentual final do mapa somente com todas as questões informadas e sem resultados fora do mapa. No modelo DADOS, resposta vazia é erro quando existe gabarito válido; questões anuladas ou sem gabarito ficam fora do cálculo. Totais importados são exibidos separadamente.')

def handle(app,c,user,path,method,data,query,start,HTTPError):
    if user['role'] not in ('master','coordenador'):raise HTTPError(403,'Área exclusiva do Master e da coordenação.')
    if method!='POST':raise HTTPError(405,'Método não permitido.')
    if path=='/api/workbook/template':
        blob,mime=template(data)
        return app.reply(start,200,blob,mime,[('Content-Disposition','attachment; filename="Modelo_unico_resultados_questoes.xlsx"')])
    if path=='/api/workbook/inspect':
        info=inspect(data);return app.reply(start,200,{k:v for k,v in info.items() if not k.startswith('_') and k!='hash'})
    if path not in ('/api/workbook/preview','/api/workbook/confirm'):raise HTTPError(404,'Página não encontrada.')
    p=prepare(app,c,user,data)
    if path.endswith('/preview'):
        stamp=int(time.time())
        sample=[dict(name=x['record']['name'],activity=x['record']['activity'],date=x['record']['date'],
                   analysis=analyse(p['exam'],x['metrics'],x['metadata']) if p['exam'] else None) for x in p['prepared'][:3]]
        return app.reply(start,200,dict(summary=p['summary'],students=p['parsed']['students'],accounts=p['accounts'],mapping=p['mapping'],sample=sample,
            token=str(stamp)+'.'+F.sign(app,p['signed'],stamp)))
    try:raw,sig=data.get('token','').split('.');stamp=int(raw)
    except (ValueError,AttributeError):raise ValueError('Confira o arquivo antes de confirmar.')
    if not 0<=time.time()-stamp<=1800 or not hmac.compare_digest(sig,F.sign(app,p['signed'],stamp)):
        raise HTTPError(409,'Arquivo, vínculos, mapa ou resultados mudaram. Refaça a conferência.')
    if p['summary']['rows'] and not p['prepared']:raise ValueError('Vincule ao menos um aluno a uma conta existente.')
    if p['summary']['unresolved'] and data.get('skipUnmapped')is not True:raise ValueError('Confirme que os alunos sem vínculo não serão importados.')
    confirm(app,c,user,p,HTTPError)
    return app.reply(start,200,dict(ok=True,summary=p['summary'],examId=p['exam']['id'] if p['exam'] else None))

import exam_metadata as _exam_metadata
