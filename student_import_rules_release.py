"""Apply final student-import rules after the two-tab importer is generated.

Rules:
- account binding is based on the student's normalized full name;
- login is only a tiebreaker for exact-name homonyms;
- only real student accounts are offered for binding;
- '.', 'x/x' and '*' in answer cells are errors (0);
- replacement options expose contextual help buttons.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY_MARKER = '# === MEU CRONOGRAMA: REGRAS FINAIS DE IMPORTAÇÃO DE ALUNOS ==='
JS_MARKER = '// === MEU CRONOGRAMA: AJUDA E REGRAS DE IMPORTAÇÃO ==='


def replace_once(text, old, new, label):
    if old not in text:
        raise RuntimeError(f'{label}: trecho esperado não encontrado.')
    return text.replace(old, new, 1)


def patch_python():
    path = ROOT / 'model_data.py'
    source = path.read_text(encoding='utf-8')
    if PY_MARKER in source:
        return

    source = replace_once(
        source,
        "    text = str(value).strip().upper()\n    if text in ('0', '0.0'):\n",
        "    text = str(value).strip().upper()\n"
        "    # Marcadores usados nas planilhas para ausência/erro também valem zero.\n"
        "    if text in ('.', 'X/X', '*'):\n"
        "        return 0\n"
        "    if text in ('0', '0.0'):\n",
        'marcadores de erro',
    )
    source = source.replace(
        "resposta deve ser A, B, C, D, E, 1, 0 ou vazio.",
        "resposta deve ser A, B, C, D, E, 1, 0, ponto (.), x/x, asterisco (*) ou vazio.",
        1,
    )

    helper = '''\n\n# === MEU CRONOGRAMA: REGRAS FINAIS DE IMPORTAÇÃO DE ALUNOS ===\ndef _student_account_value(account, key):\n    try:\n        return account[key]\n    except (KeyError, IndexError, TypeError):\n        return ''\n\n\ndef _is_importable_student_account(account):\n    name = F.norm(_student_account_value(account, 'name'))\n    technical_name = F.norm('Verificação técnica temporária')\n    return (\n        _student_account_value(account, 'role') in ('user', 'aluno')\n        and not name.startswith(technical_name)\n    )\n\n\ndef _resolve_student_account(accounts, student):\n    \"\"\"Resolve by full name; login only disambiguates exact-name homonyms.\"\"\"\n    normalized_name = F.norm(student.get('name', ''))\n    same_name = [\n        account for account in accounts\n        if F.norm(_student_account_value(account, 'name')) == normalized_name\n    ]\n    if len(same_name) == 1:\n        return _student_account_value(same_name[0], 'id')\n    if len(same_name) > 1 and student.get('login'):\n        login = F.text(student.get('login'), 100).lower()\n        same_login = [\n            account for account in same_name\n            if F.text(_student_account_value(account, 'username'), 100).lower() == login\n        ]\n        if len(same_login) == 1:\n            return _student_account_value(same_login[0], 'id')\n    return ''\n'''
    source = replace_once(
        source,
        '\ndef prepare(app, c, user, data):\n',
        helper + '\n\ndef prepare(app, c, user, data):\n',
        'funções de vínculo',
    )
    source = replace_once(
        source,
        "    accounts = F.allowed_accounts(app, c, user); byid = {a['id']: a for a in accounts}\n",
        "    allowed_student_accounts = [\n"
        "        account for account in F.allowed_accounts(app, c, user)\n"
        "        if _student_account_value(account, 'role') in ('user', 'aluno')\n"
        "    ]\n"
        "    accounts = [\n"
        "        account for account in allowed_student_accounts\n"
        "        if _is_importable_student_account(account)\n"
        "    ]\n"
        "    byid = {_student_account_value(a, 'id'): a for a in allowed_student_accounts}\n",
        'filtro de contas',
    )
    source = replace_once(
        source,
        "        if selected is None:\n"
        "            candidates = [a for a in accounts if (a['username'] == student['login'] if student['login'] else F.norm(a['name']) == F.norm(student['name']))]\n"
        "            selected = candidates[0]['id'] if len(candidates) == 1 else ''\n",
        "        if selected is None:\n"
        "            selected = _resolve_student_account(accounts, student)\n",
        'resolução por nome',
    )
    path.write_text(source, encoding='utf-8')


def patch_javascript():
    path = ROOT / 'static' / 'model_data.js'
    source = path.read_text(encoding='utf-8')
    if JS_MARKER in source:
        return

    source = replace_once(
        source,
        'Célula em branco será considerada erro quando houver gabarito válido.</p>',
        'Célula em branco, ponto (.), x/x ou asterisco (*) será considerada erro quando houver gabarito válido.</p>'
        '<p class="micro"><strong>Vínculo dos alunos:</strong> o sistema procura primeiro o nome completo. O login serve apenas para desempatar homônimos.</p>',
        'texto de orientação',
    )

    old_options = (
        "${check('Substituir respostas/resultados existentes','workbook-replace',!!workbookDraft?.replace)}"
        "${check('Substituir classificações existentes do mapa','workbook-replace-map',!!workbookDraft?.replaceMap)}"
    )
    new_options = (
        "${resultImportOption(check('Substituir respostas/resultados existentes','workbook-replace',!!workbookDraft?.replace),"
        "'result-import-help-results','Explicar substituição de respostas e resultados')}"
        "${resultImportOption(check('Substituir classificações existentes do mapa','workbook-replace-map',!!workbookDraft?.replaceMap),"
        "'result-import-help-map','Explicar substituição das classificações do mapa')}"
    )
    source = replace_once(source, old_options, new_options, 'botões de ajuda')

    appendix = r'''

// === MEU CRONOGRAMA: AJUDA E REGRAS DE IMPORTAÇÃO ===
function resultImportOption(fieldHtml, action, label){
 return `<div style="display:flex;align-items:center;gap:.55rem;min-width:0">${fieldHtml}<button type="button" class="secondary" data-act="${action}" aria-label="${esc(label)}" title="${esc(label)}" style="width:2rem;height:2rem;min-width:2rem;padding:0;border-radius:999px;font-weight:800">?</button></div>`;
}

acts['result-import-help-results']=()=>modal(
 'Substituir respostas/resultados existentes',
 '<p>Use somente ao reenviar o <strong>mesmo simulado na mesma data</strong> com respostas corrigidas.</p><p>Marcada, a nova importação regrava os resultados já existentes dos alunos vinculados. Desmarcada, resultados anteriores são preservados e divergências não são sobrescritas.</p>',
 null
);
acts['result-import-help-map']=()=>modal(
 'Substituir classificações existentes do mapa',
 '<p>Use quando corrigir o mapa das questões: área, disciplina, tópico, assunto, habilidade, língua estrangeira ou gabarito.</p><p>Ao corrigir o <strong>gabarito</strong>, marque também a substituição de respostas/resultados para recalcular os acertos dos alunos.</p>',
 null
);
'''
    source += appendix
    path.write_text(source, encoding='utf-8')


def main():
    patch_python()
    patch_javascript()
    print('MEUCRONOGRAMA_STUDENT_IMPORT_RULES_READY: name-first binding, error markers and help buttons prepared.', flush=True)


if __name__ == '__main__':
    main()
