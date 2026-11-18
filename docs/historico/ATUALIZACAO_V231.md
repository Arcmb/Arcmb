# Meu Cronograma 2.3.1 — marcar campos antes de gerar o modelo

## Caminho principal

No menu Modelo de resultados, Master e coordenador veem uma lista de informações com caixas de marcação antes de enviar qualquer arquivo. Marcam os campos, conferem a lista de colunas ao lado e escolhem Gerar modelo com os campos marcados. O XLSX ou CSV contém somente essas colunas, na ordem exibida. NOME, TIPO de prova e data de aplicação são obrigatórios; os demais campos começam desmarcados. A planilha é preenchida no Excel e enviada em Desempenho → Importar planilha preenchida.

A lista inclui identificação, notas e totais, disciplinas, habilidades H01–H30 e questões 01–180. Pode-se marcar por grupo, por intervalo de questões ou acrescentar outra disciplina. Turma e cor da prova continuam separados. O catálogo padrão tem 244 campos; os limites e regras do importador anterior permanecem.

Na aba Desempenho, o passo para gerar o modelo aparece antes do campo para envio. Os cabeçalhos do modelo gerado são reconhecidos. A correspondência manual de colunas permanece como opção secundária para outros arquivos; não é uma etapa de criação do modelo nem precisa ser refeita para os campos padronizados. Vincular alunos, selecionar a área das habilidades quando necessária e confirmar a gravação continuam exigidos.

## Separação dos arquivos

Mapa de questões é o novo nome de Simulados e questões e continua servindo apenas à classificação de questões (número, disciplina, tópico, assunto e habilidade). Um arquivo com nome de aluno sem coluna de número da questão recebe um aviso na interface e atalhos para Modelo de resultados e Desempenho, em vez de pedir a ligação de Nome com Questão.

Nenhuma senha, conta, resposta, classificação ou resultado existente é alterado por esta atualização. Não há migração de banco nem importação de dados reais. Gerar um modelo não grava desempenho nem altera o cronograma. Campos vazios continuam não apagando resultados anteriores.

## Verificação

191 testes automatizados anteriores passaram na montagem local. Foram executadas 21 verificações adicionais com Chromium e o backend WSGI real em SQLite temporário: seleção sem upload, lista, obrigatórios, XLSX/CSV exatos, disciplina nova, marcação por intervalo, importação preenchida sem remapeamento, aviso de arquivo na tela errada, permissões e layout de 390 px. Sem erros JavaScript. Não equivale a teste em Safari/iPhone físico. A validação no Render deve confirmar o deploy e /readyz com version 2.3.1.

A extensão desta entrega está em arquivos legíveis static/import_wizard.js e simplify_import_release.py, executada depois da preparação 2.3. Os fontes legados e demais serviços são preservados.
