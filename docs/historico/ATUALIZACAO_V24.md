# Meu Cronograma 2.4 — arquivo único e padrão numérico 1/0

## Selecionar antes de importar
Modelo de resultados mostra duas colunas de caixas de marcação: identificação/notas/totais e disciplinas. Campos opcionais começam desmarcados; Nome, tipo de prova e data permanecem obrigatórios. Novas disciplinas podem ser acrescentadas. Ao habilitar questões, escolha inicial/final entre 01 e 180. Habilidades têm intervalo 01 a 30. Nenhum arquivo precisa ser enviado para fazer a seleção.

Gerar arquivo Excel com os campos marcados cria um XLSX com quatro abas:
- Resultados: apenas as colunas escolhidas, uma linha por aluno.
- Questoes: número, área, disciplina, tópico, assunto, habilidade, língua estrangeira e gabarito. Números acompanham a faixa de questões escolhida. Campos classificatórios não são inventados.
- Simulado: avaliação, data, cor e área de totais por habilidade quando usados.
- Como preencher: instruções, padrão binário e regras de importação parcial.

Um arquivo único corresponde a uma avaliação, data e cor. A classificação das questões não é repetida para cada aluno. A leitura conjunta está em Desempenho > Importar arquivo único. Arquivos antigos e CSV continuam disponíveis na importação anterior. Antes de salvar, há conferência do mapa e vínculo explícito das contas; não são criadas contas automaticamente.

## Padrão de resultados por questão
Somente 1 = acerto e 0 = erro. Célula vazia = resultado não informado, nunca erro. O servidor rejeita letras, palavras Acerto/Erro, C/E e números fora do padrão, informando linha e questão. Representações numéricas do Excel equivalentes a 1.0/0.0 são aceitas como 1/0. Os modelos adicionam validação de número inteiro 0–1 com aviso de bloqueio nas colunas de questões; a validação no servidor continua obrigatória mesmo após colar dados no Excel. Contagens por disciplina/habilidade e notas não são limitadas a 0–1.

## Detalhamento calculado
A análise lista questões acertadas, erradas e sem resultado por área, disciplina, tópico, assunto e habilidade. Habilidades são separadas pela área. Língua estrangeira identifica a versão aplicável da questão.
Aproveitamento = acertos / questões com resultado. Cobertura = questões com resultado / questões classificadas no mapa. Percentual final do mapa somente com todos os resultados, língua definida quando necessária e nenhum resultado fora do mapa. Os totais importados ficam separados dos calculados e não são somados. Um mapa incompleto não prova a cobertura da prova inteira. Não se calcula TRI nem se redistribui o cronograma na importação.

A importação conjunta grava mapa e resultados na mesma transação. Vazios não apagam valores, 0 permanece válido, reimportações complementam e substituições exigem opção explícita. Prévia expira e detecta mudanças concorrentes. Permissões Master, Coordenador, Especial e Aluno são preservadas. Coordenador não acessa contas especiais e só altera mapas próprios; pode usar mapas existentes autorizados.

## Validação desta entrega
191 testes de regressão e 49 testes de arquivo único/padrão binário aprovados localmente, total 240. Fluxo Chromium com backend WSGI em memória validou seleção, XLSX com quatro abas, intervalos, disciplina nova, conferência, confirmação, gravação, listas por questão, percentuais parciais e largura móvel de 390 px. Não equivale a Safari/iPhone físico, teste de carga ou auditoria independente.
verify_workbook.py roda na inicialização com duas contas técnicas temporárias, sem alterar contas reais. A mensagem MEUCRONOGRAMA_V24_CHECK_OK confirma padrão 1/0, persistência, permissões, importação conjunta e limpeza no banco configurado. /readyz identifica version 2.4.

## Fonte
A extensão de quatro arquivos UTF-8 é comprimida sem criptografia em source/v24-{1,2,3}.xzpart. unpack_v24.py confere SHA-256, limite de descompressão e caminhos permitidos. SHA-256: 844e39d2f11ce424a0c05c91b81dbf7b5fb532d1532c4b75bf7c06bf020627d4. O ZIP de backup inclui também os fontes legíveis e testes. Não há credenciais nem dados pessoais no pacote.
