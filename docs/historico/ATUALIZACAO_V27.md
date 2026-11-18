# Meu Cronograma 2.7 — importação direta do MODELO DADOS

## Fluxo principal

O gerador padrão deixa de separar os resultados em abas por área. O arquivo simples contém:

- **DADOS DOS ALUNOS**: uma linha por participante e uma coluna por questão;
- **DADOS DO SIMULADO**: uma linha por questão, cor e versão de língua estrangeira.

O campo **Bonificação** não aparece no novo gerador. Quando houver nota com bônus, o valor final deve ser informado diretamente no fluxo que utiliza notas.

## Conversão automática das respostas

O participante pode permanecer com respostas **A, B, C, D ou E**. O sistema compara a alternativa com o gabarito e grava internamente:

- 1 = acerto;
- 0 = erro;
- resposta correta = 1 (acerto);
- resposta diferente do gabarito = 0 (erro);
- resposta em branco = 0 (erro), quando a questão possui gabarito válido;
- questão anulada = identificada como anulada, sem gerar acerto nem erro e fora do denominador.

Também são aceitos arquivos antigos que já tragam 1/0. As questões de língua estrangeira utilizam a opção Inglês/Espanhol do participante. AMARELO/AMARELA e BRANCO/BRANCA são normalizados.

## Informações calculadas

Após o vínculo com as contas, o sistema calcula para cada aluno:

- acertos e erros por área;
- acertos e erros por disciplina;
- acertos e erros por tópico;
- acertos e erros por assunto;
- acertos e erros por habilidade, preservando a área;
- relação das questões acertadas, erradas e sem resultado;
- aproveitamento e cobertura do mapa.

O histórico do aluno recebe a opção **Baixar detalhamento em Excel**, com abas de resumo, áreas, disciplinas, tópicos, assuntos, habilidades e questões.

## Conferência

A coluna `% ACERTOS` existente no mapa não é tratada como resultado definitivo. Ela é recalculada a partir das respostas efetivamente importadas. Questões sem gabarito permanecem como não calculadas e são destacadas na prévia. Questões anuladas também ficam fora do cálculo, sem gerar acerto automático.

O arquivo enviado pelo usuário foi validado localmente: 731 participantes, quatro cores, respostas 01–180 e 736 linhas de mapa. A questão 45 está sem gabarito/mapa nas quatro cores e é sinalizada sem ser transformada em erro.


## Regra definitiva de correção

| Situação | Resultado interno |
|---|---:|
| Alternativa igual ao gabarito | 1 — acerto |
| Alternativa diferente do gabarito | 0 — erro |
| Resposta em branco, com gabarito válido | 0 — erro |
| Questão anulada | sem acerto e sem erro; excluída do denominador |
| Questão sem gabarito ou sem mapa aplicável | não calculada e sinalizada na conferência |
