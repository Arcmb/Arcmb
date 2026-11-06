"""Preserve explicit legacy priorities while deriving only former default priority 3."""
from pathlib import Path

ROOT=Path(__file__).resolve().parent
MARKER='# === LEARNER PRIORITY LEGACY COMPAT V1 ==='

def main():
    path=ROOT/'planner.py'
    text=path.read_text(encoding='utf-8')
    if MARKER in text:
        return
    old="        if 'priorityManual' not in x:x['priorityManual']=False"
    new="""        if 'priorityManual' not in x:
            try:x['priorityManual']=int(x.get('priority',3) or 3)!=3
            except (TypeError,ValueError):x['priorityManual']=False"""
    if old not in text:
        raise RuntimeError('Learner priority compatibility anchor not found.')
    text=text.replace(old,new,1)
    path.write_text(text.rstrip()+'\n\n'+MARKER+'\n',encoding='utf-8')
    compile(text,'planner.py','exec')
    print('MEUCRONOGRAMA_PRIORITY_COMPAT_READY: explicit priorities preserved; former default 3 remains automatic.',flush=True)

if __name__=='__main__':main()
