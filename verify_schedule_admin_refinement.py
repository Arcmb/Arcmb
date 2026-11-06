"""Verify administrative profile assignment and review-schedule UI refinements."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    study = (ROOT / 'static' / 'study_schedule.js').read_text(encoding='utf-8')
    admin = (ROOT / 'static' / 'schedule_admin_refinement.js').read_text(encoding='utf-8')
    html = (ROOT / 'static' / 'app.html').read_text(encoding='utf-8')
    css = (ROOT / 'static' / 'style.css').read_text(encoding='utf-8')
    webapp = (ROOT / 'webapp.py').read_text(encoding='utf-8')

    require("studyPresetPanel()+studyBaseRoutineView()" in study, 'Perfil-base não foi movido para o início de Rotina e horários.')
    require("['routine','accounts','coordinator'].includes(view)" in study, 'Perfis não atualizam no painel administrativo.')
    require("localeCompare(b,'pt-BR'" in study, 'Disciplinas não usam ordenação alfabética pt-BR.')
    require('programmed=groups[name].reduce' in study and 'sem encaixe' in study, 'Resumo de minutos programados não foi corrigido.')
    require('Disciplina: ${esc(sub(s.subjectId)' in study, 'Disciplina não aparece no ajuste do bloco.')
    require('Associar perfil-base a um aluno' in admin, 'Painel explícito de associação não foi criado.')
    require("accountsView=function(){return studyPresetAdminAssociation()" in admin, 'Associação não foi adicionada ao Painel Master.')
    require('removeRankingFromTriSummary' in admin, 'Remoção visual do ranking TRI não foi preparada.')
    require('/static/schedule_admin_refinement.js?v=3.3.0' in html, 'Script de refinamento não está carregado.')
    require('SCHEDULE ADMIN REFINEMENT V1' in css, 'Estilos do refinamento não foram aplicados.')
    require("'schedule_admin_refinement.js':'application/javascript; charset=utf-8'" in webapp, 'MIME do script não foi registrado.')
    print('MEUCRONOGRAMA_SCHEDULE_ADMIN_REFINEMENT_CHECK_OK: assignment, alphabetical order, real minutes, discipline label and ranking cleanup passed.', flush=True)


if __name__ == '__main__':
    main()
