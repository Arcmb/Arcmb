"""v3.9.0: perfis de foco do motor (Base Sólida, Prática Ativa, Revisão Intensiva, Precisão)
e aba de configuração para Master e coordenação."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
MARK = '# === MOTOR PROFILES V3.9.0 ==='


def patch(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: esperado 1 trecho, encontrado {count}.')
    return text.replace(old, new, 1)


def patch_planner():
    path = ROOT / 'planner.py'
    text = path.read_text(encoding='utf-8')
    if MARK in text:
        return
    text = patch(text, "plan=c.get('reviewPlan','both');theory=max(5,int(c.get('theoryReviewMin',10)));exercise=max(5,int(c.get('exerciseReviewMin',20)));",
                 "plan,theory,exercise=_qi_profile_review(c,s);", 'review params')
    text = patch(text, "    return int(weekly * _qi_review_share(weekly))",
                 "    profile = s.get('motorProfile') if isinstance(s.get('motorProfile'), dict) else None\n"
                 "    share = float(profile.get('reviewShare')) if profile and profile.get('reviewShare') else _qi_review_share(weekly)\n"
                 "    return int(weekly * share)", 'review share')
    text = patch(text, "c.update(reviewPlan=plan,", "c.update(reviewPrefsCustom=True,reviewPlan=plan,", 'custom prefs flag')
    text = text.rstrip('\n') + '\n\n' + MARK + '\n' + (
        "def _qi_profile_review(c, s):\n"
        "    \"\"\"Forma e minutos da revisão: o perfil de foco vale para conteúdos sem ajuste manual do aluno.\"\"\"\n"
        "    mp = s.get('motorProfile') if isinstance(s.get('motorProfile'), dict) else None\n"
        "    if mp and not c.get('reviewPrefsCustom') and mp.get('reviewPlan') in ('both', 'exercise_only', 'theory_only'):\n"
        "        return mp['reviewPlan'], max(5, int(mp.get('theoryMin', 10))), max(5, int(mp.get('exerciseMin', 20)))\n"
        "    return c.get('reviewPlan', 'both'), max(5, int(c.get('theoryReviewMin', 10))), max(5, int(c.get('exerciseReviewMin', 20)))\n")
    path.write_text(text, encoding='utf-8')


def patch_adaptive():
    path = ROOT / 'adaptive.py'
    text = path.read_text(encoding='utf-8')
    if MARK in text:
        return
    text = patch(text, "import planner as P\n", "import planner as P\nimport motor_profiles as MOTOR  " + MARK + "\n", 'import')
    text = patch(text, "        new=copy.deepcopy(p)\n",
                 "        new=copy.deepcopy(p)\n        motor_profile=MOTOR.apply_to_plan(app,c,target,new)\n", 'apply profile')
    path.write_text(text, encoding='utf-8')


def patch_webapp():
    path = ROOT / 'webapp.py'
    text = path.read_text(encoding='utf-8')
    if MARK in text:
        return
    text = patch(text, "import model_data as MODEL_DATA\n", "import model_data as MODEL_DATA\nimport motor_profiles as MOTOR  " + MARK + "\n", 'import')
    text = patch(text, "            if path.startswith('/api/adaptive'):\n",
                 "            if path.startswith('/api/motor/'):\n"
                 "                return MOTOR.handle(self,c,user,path,method,data,query,start,HTTPError)\n"
                 "            if path.startswith('/api/adaptive'):\n", 'route')
    text = patch(text, "'student_view_v2.js':'application/javascript; charset=utf-8',",
                 "'student_view_v2.js':'application/javascript; charset=utf-8','motor_profiles.js':'application/javascript; charset=utf-8',", 'static allowlist')
    path.write_text(text, encoding='utf-8')


def patch_html():
    shutil.copyfile(ROOT / 'release_assets' / 'motor_profiles.js', ROOT / 'static' / 'motor_profiles.js')
    path = ROOT / 'static' / 'app.html'
    html = path.read_text(encoding='utf-8')
    if '/static/motor_profiles.js' not in html:
        html = patch(html, '<script src="/static/student_view_v2.js?v=3.8.2" defer></script>',
                     '<script src="/static/student_view_v2.js?v=3.8.2" defer></script><script src="/static/motor_profiles.js?v=3.9.0" defer></script>', 'script tag')
        path.write_text(html, encoding='utf-8')


def main():
    patch_planner()
    patch_adaptive()
    patch_webapp()
    patch_html()
    print('MEUCRONOGRAMA_V390_MOTOR_PROFILES_READY: focus profiles, automatic migration and configuration tab.', flush=True)


if __name__ == '__main__':
    main()
