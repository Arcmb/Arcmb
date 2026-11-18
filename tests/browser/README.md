# Testes de navegador

Cada arquivo `0N_*.mjs` abre o site local num Chrome sem janela e confere um fluxo real
(login, menu, visão do aluno, "Voltar ao meu usuário", relatórios, perfis de foco, cadastro de disciplinas).

    bash tests/browser/run.sh

O script cria um banco temporário com dados sintéticos (`seed.py`), sobe o site em http://127.0.0.1:8765,
roda os cenários em ordem e termina com `BROWSER_TESTS_OK` ou `BROWSER_TESTS_FAILED`.
Um cenário falha se alguma conferência falhar ou se aparecer erro de JavaScript na página.
O último cenário altera os dados (aplica o cadastro de disciplinas), por isso roda por último.
