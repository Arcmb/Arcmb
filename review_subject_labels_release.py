"""Show the discipline explicitly in every generated review block."""
from pathlib import Path

ROOT=Path(__file__).resolve().parent
MARKER='# === REVIEW SUBJECT LABELS V1 ==='


def replace_once(text,old,new,label):
    if old not in text:raise RuntimeError(label+' anchor not found.')
    return text.replace(old,new,1)


def main():
    path=ROOT/'planner.py'
    text=path.read_text(encoding='utf-8')
    if MARKER in text:return

    text=replace_once(
        text,
        "    subject_priority={x['id']:int(x.get('priority',3)) for x in subjects}\n",
        "    subject_priority={x['id']:int(x.get('priority',3)) for x in subjects}\n    subject_names={x['id']:x.get('name','Disciplina') for x in subjects}\n",
        'subject-name map',
    )
    text=replace_once(
        text,
        "        plan=c.get('reviewPlan','both');theory=max(5,int(c.get('theoryReviewMin',10)));exercise=max(5,int(c.get('exerciseReviewMin',20)));cycle=uid()\n        if plan=='exercise_only':parts=[('exercise',theory+exercise,'Exercícios: '+c['title'],True)]\n        elif plan=='theory_only':parts=[('theory',theory+exercise,'Revisão de teoria: '+c['title'],True)]\n        else:parts=[('theory',theory,'Revisão de teoria: '+c['title'],False),('exercise',exercise,'Exercícios: '+c['title'],True)]\n",
        "        plan=c.get('reviewPlan','both');theory=max(5,int(c.get('theoryReviewMin',10)));exercise=max(5,int(c.get('exerciseReviewMin',20)));cycle=uid();discipline=subject_names.get(c['subjectId'],'Disciplina')\n        if plan=='exercise_only':parts=[('exercise',theory+exercise,discipline+' · Exercícios: '+c['title'],True)]\n        elif plan=='theory_only':parts=[('theory',theory+exercise,discipline+' · Revisão de teoria: '+c['title'],True)]\n        else:parts=[('theory',theory,discipline+' · Revisão de teoria: '+c['title'],False),('exercise',exercise,discipline+' · Exercícios: '+c['title'],True)]\n",
        'review titles',
    )
    text=replace_once(
        text,
        "            task=dict(kind='review',subjectId=c['subjectId'],contentId=c['id'] if closes_cycle else '',reviewContentId=c['id'],reviewPart=part,reviewCycleId=cycle,title=title,earliest=c['nextDue'],due=c['nextDue'],studiedOn=c['studiedOn'],studiedTime=c['studiedTime'],studyMinutes=c['studyMinutes'],preferredDay=int(c.get('preferredReviewDay',-1)),priority=subject_priority.get(c['subjectId'],3),reason=('Prática de recuperação por exercícios. ' if part=='exercise' else 'Retomada orientada da teoria. ')+'Data-alvo: '+c['nextDue']+'.')\n",
        "            task=dict(kind='review',subjectId=c['subjectId'],subjectName=discipline,contentId=c['id'] if closes_cycle else '',reviewContentId=c['id'],reviewPart=part,reviewCycleId=cycle,title=title,earliest=c['nextDue'],due=c['nextDue'],studiedOn=c['studiedOn'],studiedTime=c['studiedTime'],studyMinutes=c['studyMinutes'],preferredDay=int(c.get('preferredReviewDay',-1)),priority=subject_priority.get(c['subjectId'],3),reason=('Prática de recuperação por exercícios. ' if part=='exercise' else 'Retomada orientada da teoria. ')+' Disciplina: '+discipline+'. Data-alvo: '+c['nextDue']+'.')\n",
        'review task metadata',
    )
    text=replace_once(
        text,
        "        created.append(dict(id=uid(),date=d,start=t,end=t+duration,kind=task['kind'],subjectId=task['subjectId'],contentId=task.get('contentId',''),reviewContentId=task.get('reviewContentId',''),reviewPart=task.get('reviewPart',''),reviewCycleId=task.get('reviewCycleId',''),title=task['title'],status='planned',locked=False,reason=task['reason'],createdAt=now().isoformat()))\n",
        "        created.append(dict(id=uid(),date=d,start=t,end=t+duration,kind=task['kind'],subjectId=task['subjectId'],subjectName=task.get('subjectName',''),contentId=task.get('contentId',''),reviewContentId=task.get('reviewContentId',''),reviewPart=task.get('reviewPart',''),reviewCycleId=task.get('reviewCycleId',''),title=task['title'],status='planned',locked=False,reason=task['reason'],createdAt=now().isoformat()))\n",
        'session subject metadata',
    )
    path.write_text(text.rstrip()+'\n\n'+MARKER+'\n',encoding='utf-8')
    print('MEUCRONOGRAMA_REVIEW_SUBJECT_LABELS_READY: discipline is explicit in review titles, reasons and session metadata.',flush=True)


if __name__=='__main__':main()
