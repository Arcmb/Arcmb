# Meu Cronograma — exportação coletiva de resultados convertidos

## Conversão das respostas

A importação do `MODELO DADOS.xlsx` compara cada resposta A–E com o gabarito correspondente ao nome do simulado, à data, à cor da prova, ao número da questão e, nas questões 01–05 de Linguagens, à língua estrangeira do aluno.

- resposta igual ao gabarito: 1 acerto;
- resposta diferente do gabarito: 0;
- resposta vazia com gabarito válido: 0;
- questão anulada ou sem gabarito: excluída do cálculo.

Os valores convertidos são gravados por questão no resultado do aluno. As habilidades são vinculadas à área, portanto H01 de Linguagens e H01 de Natureza permanecem métricas distintas.

## Nova página `Exportar resultados`

A página é disponibilizada ao Master e à Coordenação. Ela lista os simulados efetivamente importados e permite selecionar um simulado por nome e data.

O Excel exportado contém:

1. `Resumo dos alunos`;
2. `Por área`;
3. `Por disciplina`;
4. `Por tópico`;
5. `Por assunto`;
6. `Por habilidade`.

Cada linha apresenta o aluno, login, turma, classificação, acertos, erros, questões calculadas, questões válidas, aproveitamento, cobertura e números das questões acertadas, erradas ou sem resultado.

A exportação coletiva contém apenas contas de alunos. Perfis especiais não são incluídos, inclusive quando a exportação é feita pelo Master.
