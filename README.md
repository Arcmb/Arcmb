# Meu Cronograma Qi

Planejamento de estudos e revisões para os alunos do Qi Vestibulares, com relatórios para a coordenação.
Publicado em https://meucronograma.onrender.com (Render + banco Postgres no Neon).

## Como o código está organizado

O código deste repositório **é** o site: não há etapa de montagem. A publicação instala as dependências
e roda as verificações (`build.sh`); depois só inicia o servidor (`start.sh`). Assim, se o servidor
reiniciar (por exemplo, por falta de memória), ele volta em segundos.

| Pasta / arquivo | O que tem |
|---|---|
| `webapp.py` | Servidor WSGI: rotas, login, permissões, sessões, banco de dados. |
| `planner.py`, `adaptive.py` | Motor de estudos: semana, sessões, revisões e prioridades. |
| `motor_profiles.py` | Perfis de foco (Base Sólida, Prática Ativa, Revisão Intensiva, Precisão). |
| `model_data.py`, `unified.py`, `area_workbook.py`, `performance.py`, `selective.py`, `exams.py`, `exam_metadata.py`, `templates_v23.py` | Importação de resultados e mapas de simulado, TRI, desempenho e planilhas modelo. |
| `school_reports.py` | Relatórios da escola (atenção, questões, assuntos, disciplinas, redação, perfis). |
| `disciplines_catalog.py` | Cadastro de disciplinas oficiais e conversão de nomes na importação. |
| `provisional_access.py` | Senhas provisórias com validade. |
| `routine_entries.py`, `questions_v23.py` | Rotina e questionário de mapeamento. |
| `site_version.py` | Versão exibida no rodapé (mude com `python tools/set_version.py X.Y.Z`). |
| `static/` | Telas (HTML, JavaScript e CSS). A política de segurança só aceita CSS em arquivo: não injete `<style>` por script. |
| `checks/` | Verificações que rodam a cada publicação, **sempre num banco SQLite temporário**. `python checks/run_all.py` |
| `tests/` | Testes automáticos. `python -m unittest discover -s tests` |
| `tests/browser/` | Testes em navegador (Chrome sem janela). Veja `tests/browser/README.md`. |
| `tools/` | Utilitários de manutenção. |
| `docs/historico/` | Notas das versões antigas. |

Todas as tabelas do banco começam com `hmay_`, o que permite integrar este sistema a um site maior
sem conflito de nomes.

## Rodar no computador

```bash
pip install -r requirements.txt
LOCAL_TEST=1 LOCAL_DB=local.sqlite3 SECRET_KEY=$(python -c "print('x'*64)") MASTER_PASSWORD=sua_senha_local python webapp.py
```

O site abre em http://localhost:8765 (login `arcmb` com a senha local escolhida).

## Antes de publicar

1. `python checks/run_all.py`
2. `python -m unittest discover -s tests`
3. Testes de navegador (`tests/browser/run.sh`).
4. Ao alterar um arquivo de `static/`, troque o `?v=` dele em `static/app.html`.
5. `python tools/set_version.py X.Y.Z` para a nova versão pública.

Cada `git push` na branch `meucronograma` publica automaticamente no Render.
