"""Hotfix v3.7.10: do not block two-tab import on non-A-E exam keys."""
from pathlib import Path

ROOT=Path(__file__).resolve().parent
MARK="# === NON-AE GABARITO AS ERROR V3.7.10 ==="

APPEND=r'''
# === NON-AE GABARITO AS ERROR V3.7.10 ===
_v3710_parse_base = _parse

def _parse(data, require_date=False):
    parsed = _v3710_parse_base(data, require_date)
    for exam in (parsed.get('exams') or {}).values():
        for item in exam.get('items') or []:
            raw = item.get('answer')
            text = '' if raw is None else str(raw).strip().upper()
            if text not in ('A', 'B', 'C', 'D', 'E'):
                # Sentinel is deliberately different from the student's error value (0),
                # so a malformed response can never be counted as a correct answer.
                item['answer'] = '#ERRO#'
            else:
                item['answer'] = text
    return parsed
'''

def _disable_old_gabarito_block(source):
    phrase='gabarito deve ser A–E, ANULADA ou vazio.'
    lines=source.splitlines()
    hits=[i for i,line in enumerate(lines) if phrase in line]
    if not hits:
        raise RuntimeError('Old DADOS DO SIMULADO gabarito validator was not found.')
    for hit in reversed(hits):
        start=hit
        while start>=0 and 'raise ValueError' not in lines[start]:
            start-=1
        if start<0 or hit-start>4:
            raise RuntimeError('Could not locate the old gabarito ValueError statement.')
        indent=lines[start][:len(lines[start])-len(lines[start].lstrip())]
        end=start
        balance=0
        seen_open=False
        while end<len(lines):
            line=lines[end]
            balance += line.count('(')-line.count(')')
            if '(' in line:
                seen_open=True
            if seen_open and balance<=0:
                break
            end+=1
        lines[start:end+1]=[indent+'pass  # v3.7.10: non-A-E gabarito is normalized as error instead of blocking import']
    return '\n'.join(lines)+'\n'

def main():
    model=ROOT/'model_data.py'
    source=model.read_text(encoding='utf-8')
    if MARK not in source:
        source=_disable_old_gabarito_block(source)
        source=source.rstrip()+"\n\n"+APPEND.strip()+"\n"
        model.write_text(source,encoding='utf-8')

    site=ROOT/'site_version_release.py'
    if site.exists():
        text=site.read_text(encoding='utf-8').replace('PUBLIC_VERSION="3.7.9"','PUBLIC_VERSION="3.7.10"')
        site.write_text(text,encoding='utf-8')

    vsite=ROOT/'verify_site_version.py'
    if vsite.exists():
        text=vsite.read_text(encoding='utf-8').replace('v3.7.9','v3.7.10')
        vsite.write_text(text,encoding='utf-8')

    print('MEUCRONOGRAMA_NON_AE_GABARITO_READY: old blocking validator disabled; non-A-E exam keys become forced errors.',flush=True)

if __name__=='__main__':
    main()
