# Meu Cronograma 2.5 — resultados separados por área

## Estrutura do arquivo Excel

O modelo personalizado passa a gerar uma aba para cada área selecionada, sempre nesta ordem:

1. Linguagens
2. Humanas
3. Natureza
4. Matemática
5. Redação

Além dessas abas, o arquivo contém `Geral`, com a identificação da avaliação e dos participantes, e `Como preencher`, com as regras do modelo. Áreas não selecionadas não geram abas.

## Disciplinas por área

- Linguagens: Língua estrangeira, Português, Literatura, Artes, Educação Física, Linguagem Corporal e TICs.
- Humanas: História, Geografia, Filosofia e Sociologia.
- Natureza: Biologia, Física e Química.
- Matemática: Matemática.
- Redação: tema, C1, C2, C3, C4, C5 e nota total.

Outras disciplinas continuam podendo ser acrescentadas, mas precisam ser vinculadas a uma área.

## Questões e habilidades

O usuário informa a quantidade de questões de Linguagens, Humanas, Natureza e Matemática. A numeração é contínua e segue a ordem das áreas. Exemplo: 45 questões de Linguagens, 45 de Humanas, 45 de Natureza e 45 de Matemática geram as faixas 01–45, 46–90, 91–135 e 136–180.

Redação não recebe questões. Cada aba de área contém o mapa de suas questões — disciplina, tópico, assunto, habilidade, língua estrangeira e gabarito — e os resultados dos participantes daquela área.

As habilidades H01–H30 são armazenadas com a área. Portanto, H01 de Linguagens, H01 de Humanas, H01 de Natureza e H01 de Matemática permanecem métricas distintas.

## Regras de preenchimento e análise

- 1 = acerto.
- 0 = erro.
- Célula vazia = resultado não informado.
- Acertos, erros, cobertura e aproveitamento são calculados por área, disciplina, tópico, assunto e habilidade.
- A nota da redação corresponde à soma de C1 a C5. O sistema calcula a soma quando o total estiver vazio e acusa divergência quando o total informado não corresponder aos critérios.
- Resultados importados anteriormente permanecem compatíveis. O formato único da versão 2.4 continua aceito.

## Verificação

Foram aprovados 293 testes automatizados locais: 284 testes de regressão e 9 testes específicos da versão 2.5. O teste de inicialização da versão confirma abas, ordem, numeração contínua, habilidades separadas por área, padrão 1/0, redação, persistência e limpeza de contas técnicas.

Nenhum resultado real, conta ou planejamento é alterado pela instalação desta versão.
