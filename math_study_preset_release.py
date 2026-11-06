"""Add a Mathematics and Exact Sciences operational preset.

The preset is visible with the other built-ins. When applied to existing data it
also configures Mathematics as maximum priority and gives Physics/Chemistry high
priority, while keeping theory and exercises as distinct moments.
"""
from pathlib import Path

ROOT=Path(__file__).resolve().parent
MARKER='# === MATHEMATICS STUDY PRESET V1 ==='

APPEND=r'''

# === MATHEMATICS STUDY PRESET V1 ===
import unicodedata as _math_ud


def _math_norm(value):
    raw=str(value or '').strip().lower()
    return ''.join(ch for ch in _math_ud.normalize('NFD',raw) if _math_ud.category(ch)!='Mn')


def _study_apply_math_focus(profile):
    subjects=profile.get('subjects',[]) if isinstance(profile,dict) else []
    subject_kind={}
    for subject in subjects:
        if not isinstance(subject,dict):continue
        name=_math_norm(subject.get('name'))
        kind=''
        if 'matematica' in name:
            kind='math'
            subject['priority']=1
            subject['weeklyMin']=max(180,int(subject.get('weeklyMin') or 0))
            subject['reviewPlan']='both'
            subject['theoryReviewMin']=15
            subject['exerciseReviewMin']=35
            subject['importance']=max(4,int(subject.get('importance') or 3))
        elif 'fisica' in name or 'quimica' in name:
            kind='exact'
            subject['priority']=min(2,int(subject.get('priority') or 3))
            subject['weeklyMin']=max(120,int(subject.get('weeklyMin') or 0))
            subject['reviewPlan']='both'
            subject['theoryReviewMin']=15
            subject['exerciseReviewMin']=30
        if kind and subject.get('id'):subject_kind[subject['id']]=kind
    for content in profile.get('contents',[]):
        if not isinstance(content,dict):continue
        kind=subject_kind.get(content.get('subjectId'))
        if not kind:continue
        content['reviewPlan']='both'
        content['theoryReviewMin']=15
        content['exerciseReviewMin']=35 if kind=='math' else 30
        content['reviewMinutes']=content['theoryReviewMin']+content['exerciseReviewMin']
    return profile

if not any(x.get('id')=='builtin:math' for x in _STUDY_BUILTIN_PRESETS):
    _STUDY_BUILTIN_PRESETS.append(dict(
        id='builtin:math',
        name='Matemática e Exatas',
        description='Prioriza Matemática, resolução progressiva de problemas, correção de erros e prática frequente. Física e Química recebem prioridade alta quando cadastradas.',
        config=dict(sessionMin=25,sessionMax=50,breakMin=10,dailyMax=180,weeklyGoal=660,reservePct=20,intervals=[1,3,7,14,30,60],reviewMin=50,defaultReviewPlan='both',defaultTheoryMin=15,defaultExerciseMin=35)
    ))
'''


def main():
    path=ROOT/'model_data.py'
    text=path.read_text(encoding='utf-8')
    if MARKER in text:return
    anchor="""            if bool(data.get('applyExisting',True)):
                for subject in profile.get('subjects',[]):
                    subject['reviewPlan']=config['defaultReviewPlan'];subject['theoryReviewMin']=config['defaultTheoryMin'];subject['exerciseReviewMin']=config['defaultExerciseMin'];subject.setdefault('priority',3);subject.setdefault('preferredReviewDay',-1)
                for content in profile.get('contents',[]):
                    content['reviewPlan']=config['defaultReviewPlan'];content['theoryReviewMin']=config['defaultTheoryMin'];content['exerciseReviewMin']=config['defaultExerciseMin'];content['reviewMinutes']=config['defaultTheoryMin']+config['defaultExerciseMin'];content.setdefault('preferredReviewDay',-1)
            if profile.get('planMeta'):profile['planMeta']['dirty']=True
"""
    replacement="""            if bool(data.get('applyExisting',True)):
                for subject in profile.get('subjects',[]):
                    subject['reviewPlan']=config['defaultReviewPlan'];subject['theoryReviewMin']=config['defaultTheoryMin'];subject['exerciseReviewMin']=config['defaultExerciseMin'];subject.setdefault('priority',3);subject.setdefault('preferredReviewDay',-1)
                for content in profile.get('contents',[]):
                    content['reviewPlan']=config['defaultReviewPlan'];content['theoryReviewMin']=config['defaultTheoryMin'];content['exerciseReviewMin']=config['defaultExerciseMin'];content['reviewMinutes']=config['defaultTheoryMin']+config['defaultExerciseMin'];content.setdefault('preferredReviewDay',-1)
                if preset['id']=='builtin:math':_study_apply_math_focus(profile)
            if profile.get('planMeta'):profile['planMeta']['dirty']=True
"""
    if anchor not in text:raise RuntimeError('Study preset apply anchor was not found.')
    text=text.replace(anchor,replacement,1)
    text=text.rstrip()+APPEND+'\n'
    path.write_text(text,encoding='utf-8')
    print('MEUCRONOGRAMA_MATH_PRESET_READY: Mathematics and Exact Sciences preset added with subject-specific priorities.',flush=True)


if __name__=='__main__':main()
