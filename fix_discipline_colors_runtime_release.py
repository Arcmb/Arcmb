"""Apply discipline colors after the legacy-priority compatibility patch.

The previous release expected the pre-compatibility priority line. This wrapper
uses the current multi-line priority block, then reuses the reviewed UI/static
asset installer without running the incompatible patch function.
"""
from pathlib import Path
import discipline_colors_review_runtime_release as D

ROOT=Path(__file__).resolve().parent
MARK='# === DISCIPLINE COLORS AND REVIEW RUNTIME V1 ==='


def patch_planner():
    path=ROOT/'planner.py'
    text=path.read_text(encoding='utf-8')
    if MARK in text:return
    anchor="""        if 'priorityManual' not in x:
            try:x['priorityManual']=int(x.get('priority',3) or 3)!=3
            except (TypeError,ValueError):x['priorityManual']=False"""
    replacement="""        x.setdefault('color','')
        _subject_color=str(x.get('color') or '').strip().lower()
        if _subject_color and (len(_subject_color)!=7 or _subject_color[0]!='#' or any(ch not in '0123456789abcdef' for ch in _subject_color[1:])):raise ValueError('Cor da disciplina inválida.')
        x['color']=_subject_color
        if 'priorityManual' not in x:
            try:x['priorityManual']=int(x.get('priority',3) or 3)!=3
            except (TypeError,ValueError):x['priorityManual']=False"""
    if anchor not in text:raise RuntimeError('Current priority compatibility block not found in planner.py.')
    text=text.replace(anchor,replacement,1)
    path.write_text(text.rstrip()+'\n\n'+MARK+'\n',encoding='utf-8')
    compile(text,'planner.py','exec')


def main():
    patch_planner()
    D.install_assets()
    print('MEUCRONOGRAMA_DISCIPLINE_COLORS_REVIEW_RUNTIME_READY: review assets served and learner-editable pastel discipline colors prepared.',flush=True)


if __name__=='__main__':main()
