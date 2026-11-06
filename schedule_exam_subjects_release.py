"""Create schedule subjects automatically for disciplines found in imported exam errors."""
from pathlib import Path

ROOT=Path(__file__).resolve().parent
MARKER='# === MEU CRONOGRAMA: DISCIPLINAS AUTOMATICAS DOS SIMULADOS V1 ==='


def main():
    path=ROOT/'model_data.py'
    text=path.read_text(encoding='utf-8')
    if MARKER in text:
        return
    old="""    existing={x.get('sourceKey'):x for x in contents if isinstance(x,dict) and x.get('sourceType')=='exam_error' and x.get('sourceKey')}
    groups=_er_exam_errors(app,c,target['id'])
    created=updated=0
"""
    new="""    existing={x.get('sourceKey'):x for x in contents if isinstance(x,dict) and x.get('sourceType')=='exam_error' and x.get('sourceKey')}
    groups=_er_exam_errors(app,c,target['id'])
    auto_subjects=0
    for bucket in groups.values():
        discipline=str(bucket.get('discipline') or '').strip()
        discipline_key=_er_norm(discipline)
        if not discipline_key or discipline_key in subject_map:continue
        subject_id='sub_exam_'+_er_hash.sha1(discipline_key.encode('utf-8')).hexdigest()[:16]
        subjects.append(dict(id=subject_id,name=discipline,kind='study',action='Estudar e praticar',weeklyMin=90,difficulty=3,importance=3,priority=2,examDate='',active=True,reviewPlan='both',theoryReviewMin=10,exerciseReviewMin=20,preferredReviewDay=-1))
        subject_map[discipline_key]=subject_id;auto_subjects+=1
    profile['subjects']=subjects
    created=updated=0
"""
    if old not in text:raise RuntimeError('Trecho de sincronização dos erros não encontrado.')
    text=text.replace(old,new,1)
    text=text.replace("    changed=bool(created or updated)\n", "    changed=bool(created or updated or auto_subjects)\n",1)
    text=text.replace("                errors=sum(len(x['errors']) for x in groups.values()),targetId=target['id'])\n", "                errors=sum(len(x['errors']) for x in groups.values()),subjectsCreated=auto_subjects,targetId=target['id'])\n",1)
    path.write_text(text.rstrip()+'\n\n'+MARKER+'\n',encoding='utf-8')
    print('MEUCRONOGRAMA_EXAM_SUBJECTS_READY: missing disciplines from imported errors become schedulable subjects.',flush=True)


if __name__=='__main__':main()
