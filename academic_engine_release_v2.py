"""Compatibility wrapper for the academic-engine release."""
from pathlib import Path
import academic_engine_release as base

ROOT = Path(__file__).resolve().parent


def replace_once(text, old, new, label):
    if old not in text:
        raise RuntimeError(f'{label}: trecho esperado não encontrado.')
    return text.replace(old, new, 1)


def patch_adaptive_compat():
    path = ROOT / 'adaptive.py'
    source = path.read_text(encoding='utf-8')
    marker = '# === MEU CRONOGRAMA: RESULTADOS ACADÊMICOS NO MOTOR MATEMÁTICO ==='
    if marker not in source:
        source = replace_once(source, '\ndef delta(before,after):\n', base.ACADEMIC_HELPERS + '\n\ndef delta(before,after):\n', 'funções acadêmicas')
    source = source.replace("VERSION = '2.2'", "VERSION = '2.3'", 1)

    get_anchor = "    if path=='/api/adaptive' and method=='GET':\n        weights,own,shared=bonuses(app,c,user,target,p)\n"
    if 'academic=academic_priority(app,c,target,p)' not in source:
        source = replace_once(
            source,
            get_anchor,
            get_anchor + "        academic=academic_priority(app,c,target,p)\n",
            'cálculo acadêmico do diagnóstico',
        )
    if 'collective=shared,academic=academic,history=' not in source:
        source = replace_once(
            source,
            'personal=own,collective=shared,history=',
            'personal=own,collective=shared,academic=academic,history=',
            'resposta acadêmica do diagnóstico',
        )

    preview_anchor = """        weights,own,shared=bonuses(app,c,user,target,p)
        new=P.generate(copy.deepcopy(p),w,mode=mode,bonuses=weights);P.validate(new)
"""
    preview_replacement = """        weights,own,shared=bonuses(app,c,user,target,p)
        use_academic=data.get('academic','yes')!='no'
        academic=academic_priority(app,c,target,p) if use_academic else {'enabled':False,'used':False,'bonuses':{},'subjects':[],'unmatched':[],'notice':'Resultados acadêmicos desativados para esta prévia.'}
        new=P.generate(copy.deepcopy(p),w,mode=mode,bonuses=weights,subject_bonuses=academic.get('bonuses',{}));P.validate(new)
"""
    if 'subject_bonuses=academic.get' not in source:
        source = replace_once(source, preview_anchor, preview_replacement, 'uso acadêmico na prévia')
    if 'collective=shared,academic=academic)' not in source:
        source = replace_once(
            source,
            'report.update(mode=mode,week=w,own=own,collective=shared)',
            'report.update(mode=mode,week=w,own=own,collective=shared,academic=academic)',
            'resumo acadêmico da prévia',
        )
    path.write_text(source, encoding='utf-8')


def patch_frontend_compat():
    path = ROOT / 'static' / 'adaptive.js'
    source = path.read_text(encoding='utf-8')

    if 'function academicPriorityHtml' not in source:
        anchor = "const objectiveValue=(key,v)=>key==='preferred'?(objectivePeriods[v]||v):typeof v==='boolean'?(v?'Sim':'Não'):String(v);\n"
        helper = r'''const objectiveValue=(key,v)=>key==='preferred'?(objectivePeriods[v]||v):typeof v==='boolean'?(v?'Sim':'Não'):String(v);
function academicPriorityHtml(info,compact=false){
 const rows=(info?.subjects||[]).map(x=>`<div class="item"><div><strong>${esc(x.subject)}</strong><p>${x.correct}/${x.questions} acertos (${Math.round(x.accuracy*100)}%) em ${x.simulations} simulado(s)${x.used?` · prioridade +${x.boostPct}%`:' · sem aumento de prioridade'}</p><small>${esc(x.reason)}${x.latest?' · resultado mais recente: '+br(x.latest):''}</small></div></div>`).join('');
 const unmatched=(info?.unmatched||[]).length&&!compact?`<p class="micro"><strong>Sem disciplina correspondente:</strong> ${(info.unmatched||[]).map(esc).join(', ')}. Cadastre a disciplina com nome equivalente para que ela entre no cálculo.</p>`:'';
 return `<p>${esc(info?.notice||'Sem informação acadêmica.')}</p>${rows||empty('Nenhuma disciplina do cronograma recebeu evidência acadêmica suficiente.')}${unmatched}`;
}
'''
        source = replace_once(source, anchor, helper, 'função visual acadêmica')

    collective_anchor = '`<section class="card"><h2>Contribuição coletiva opcional</h2>'
    if 'Resultados acadêmicos no motor matemático' not in source:
        academic_section = '`<section class="card"><h2>Resultados acadêmicos no motor matemático</h2>${academicPriorityHtml(d.academic)}<p class="micro">O resultado altera somente a distribuição relativa entre disciplinas ativas. Não cria horários, não muda a carga total e não salva nada sem prévia e confirmação.</p></section>`+\n '
        source = replace_once(source, collective_anchor, academic_section + collective_anchor, 'seção acadêmica do mapeamento')

    mode_select = "${select('Como organizar?','mode','fill',[['fill','Completar espaços livres sem retirar os blocos existentes'],['reorganize','Reorganizar blocos futuros não fixados']])}"
    academic_select = "${select('Usar resultados acadêmicos recentes?','academic','yes',[['yes','Sim — ajustar prioridades por disciplina com limites'],['no','Não — usar somente metas, dificuldade, importância e prazo']])}"
    if "'Usar resultados acadêmicos recentes?'" not in source:
        source = replace_once(source, mode_select, mode_select + academic_select, 'controle acadêmico da prévia')

    preview_anchor = '<p>${esc(s.own.notice)}</p><p>${esc(s.collective.notice)}</p>'
    if 'Influência dos resultados acadêmicos' not in source:
        preview_insert = preview_anchor + '<section class="notice"><strong>Influência dos resultados acadêmicos</strong>${academicPriorityHtml(s.academic,true)}</section>'
        source = replace_once(source, preview_anchor, preview_insert, 'resumo acadêmico da proposta')

    path.write_text(source, encoding='utf-8')
    html_path = ROOT / 'static' / 'app.html'
    html = html_path.read_text(encoding='utf-8')
    html = html.replace('/static/adaptive.js?v=2.6', '/static/adaptive.js?v=2.9.0')
    html_path.write_text(html, encoding='utf-8')


def main():
    base.patch_planner()
    patch_adaptive_compat()
    patch_frontend_compat()
    print('MEUCRONOGRAMA_ACADEMIC_ENGINE_READY: imported results now provide bounded subject priorities in previewed schedules.')


if __name__ == '__main__':
    main()
