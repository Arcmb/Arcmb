"""Verify the built-in Mathematics and Exact Sciences study preset."""
from pathlib import Path
import model_data as M

ROOT=Path(__file__).resolve().parent


def require(value,message):
    if not value:raise RuntimeError(message)


def main():
    preset=next((x for x in M._STUDY_BUILTIN_PRESETS if x.get('id')=='builtin:math'),None)
    require(preset,'Mathematics preset is missing.')
    config=preset.get('config',{})
    require(config.get('defaultReviewPlan')=='both','Mathematics must preserve separate theory and exercise moments.')
    require(config.get('defaultExerciseMin',0)>config.get('defaultTheoryMin',0),'Mathematics must allocate more time to exercises than theory.')
    profile=dict(subjects=[
        dict(id='mat',name='Matemática',priority=3,weeklyMin=60,importance=3),
        dict(id='fis',name='Física',priority=4,weeklyMin=60,importance=3),
        dict(id='his',name='História',priority=3,weeklyMin=120,importance=3),
    ],contents=[
        dict(id='c1',subjectId='mat',title='Funções'),
        dict(id='c2',subjectId='fis',title='Cinemática'),
        dict(id='c3',subjectId='his',title='República'),
    ])
    M._study_apply_math_focus(profile)
    mat=profile['subjects'][0];fis=profile['subjects'][1];his=profile['subjects'][2]
    require(mat['priority']==1 and mat['weeklyMin']>=180,'Mathematics did not receive maximum priority and minimum weekly time.')
    require(mat['reviewPlan']=='both' and mat['theoryReviewMin']==15 and mat['exerciseReviewMin']==35,'Mathematics review split is incorrect.')
    require(fis['priority']<=2 and fis['weeklyMin']>=120,'Physics did not receive high priority.')
    require(his['priority']==3 and his['weeklyMin']==120,'Unrelated disciplines must remain unchanged.')
    require(profile['contents'][0]['reviewMinutes']==50,'Mathematics content review duration is incorrect.')
    source=(ROOT/'model_data.py').read_text(encoding='utf-8')
    require("preset['id']=='builtin:math'" in source,'Preset application hook is missing.')
    print('MEUCRONOGRAMA_MATH_PRESET_CHECK_OK: Mathematics card, priority, weekly time and theory/exercise split passed.',flush=True)


if __name__=='__main__':main()
