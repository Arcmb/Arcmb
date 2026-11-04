# Meu Cronograma 2.8 — modelo definitivo de duas abas

O gerador de resultados deixa de exibir a seleção extensa por áreas, disciplinas, habilidades e abas. O arquivo padrão passa a conter somente:

1. `DADOS DOS ALUNOS`: uma linha por participante e uma coluna por questão;
2. `DADOS DO SIMULADO`: uma linha por questão, cor e versão de língua estrangeira.

## Linguagens

O aluno possui 45 respostas de Linguagens. No mapa, as questões 01–05 possuem duas linhas — Inglês e Espanhol — e as questões 06–45 possuem uma linha. Portanto, são 50 registros de Linguagens por cor, sem duplicar as respostas do aluno.

O cruzamento usa simulado, data, cor, número da questão e língua estrangeira. Habilidade, disciplina, tópico, assunto e gabarito podem ser distintos entre Inglês e Espanhol. A língua do participante é obrigatória quando o mapa contém as duas versões.

## Modelo gerado

Por padrão, são criadas 180 colunas de respostas e quatro cores: Azul, Amarelo, Branco e Verde. Cada cor recebe 185 linhas no mapa: 180 números, com cinco linhas adicionais para a segunda versão das questões 01–05. Nome do simulado, data, quantidade e cores podem ser pré-preenchidos na tela.

Não há aba de instruções, bonificação ou abas separadas por áreas. As orientações aparecem no próprio site.

## Correção

- resposta igual ao gabarito: 1;
- resposta diferente: 0;
- resposta vazia com gabarito válido: 0;
- questão anulada ou sem gabarito: excluída do cálculo.
