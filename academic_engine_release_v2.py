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


def main():
    base.patch_planner()
    patch_adaptive_compat()
    base.patch_frontend()
    print('MEUCRONOGRAMA_ACADEMIC_ENGINE_READY: imported results now provide bounded subject priorities in previewed schedules.')


if __name__ == '__main__':
    main()
