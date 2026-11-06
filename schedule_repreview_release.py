"""Open a fresh schedule preview after the learner changes a review plan."""
from pathlib import Path

ROOT=Path(__file__).resolve().parent
MARKER='// === REVIEW CHANGE REPREVIEW V1 ==='


def main():
    path=ROOT/'static'/'study_schedule.js'
    text=path.read_text(encoding='utf-8')
    if MARKER in text:return
    old="""`,async(f,d)=>save('review_preferences',{id:c.id,nextDue:d.nextDue,preferredReviewDay:+d.preferredReviewDay,reviewPlan:d.reviewPlan,theoryReviewMin:+d.theoryReviewMin,exerciseReviewMin:+d.exerciseReviewMin,paused:f.elements.paused.checked}));
}"""
    new="""`,async(f,d)=>{await save('review_preferences',{id:c.id,nextDue:d.nextDue,preferredReviewDay:+d.preferredReviewDay,reviewPlan:d.reviewPlan,theoryReviewMin:+d.theoryReviewMin,exerciseReviewMin:+d.exerciseReviewMin,paused:f.elements.paused.checked});setTimeout(()=>{view='calendar';render();acts['generate']();},0);});
}"""
    if old not in text:raise RuntimeError('Formulário de preferências de revisão não encontrado.')
    text=text.replace(old,new,1)
    text=text.replace('Ao salvar, blocos futuros não fixados desse conteúdo serão retirados. Gere novamente a semana para aplicar a nova divisão.','Ao salvar, blocos futuros não fixados desse conteúdo serão retirados e uma nova prévia do cronograma será aberta para confirmação.',1)
    path.write_text(text.rstrip()+'\n\n'+MARKER+'\n',encoding='utf-8')
    print('MEUCRONOGRAMA_REVIEW_REPREVIEW_READY: review changes open a fresh schedule preview.',flush=True)


if __name__=='__main__':main()
