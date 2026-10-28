# Meu Cronograma 2.2 — mapeamento objetivo e propostas

## Interface

Abra **Mapeamento objetivo**, responda as 20 perguntas fechadas e salve. As respostas podem ficar parcialmente em branco. Não são diagnóstico psicológico, tipos de personalidade nem estilos de aprendizagem. Textos antigos continuam em Observações pessoais, sem interpretação automática.

Salvar respostas não muda disponibilidade, metas, sono ou horários. Os parâmetros sugeridos aparecem com explicação, para aprovação separada. O questionário orienta duração dos blocos, pausas, reserva e período preferido, além de encaminhamentos de organização. Cadastre disciplinas e janelas disponíveis antes de solicitar horários.

No **Quadro semanal → Gerar / recalcular**, escolha:
- Completar espaços livres: preserva os blocos existentes.
- Reorganizar: pode substituir blocos futuros ainda não fixados; preserva execução e blocos fixados.

A prévia não substitui o cronograma. A confirmação exige a mesma conta, autorização atual, versão do planejamento e prévia não expirada. Outra edição invalida a proposta. Horários desconhecidos não são considerados livres, e novos blocos não ocupam sono, compromissos, pausas ou reserva.

## Histórico e adaptação

Mudanças passam a registrar autor, motivo, blocos adicionados/retirados/alterados, deslocamento de horário e duração. O motivo pode ser selecionado no ajuste manual de um bloco. Não há aprendizado automático de que uma edição foi boa: são usados registros posteriores de execução.

Sugestões de horário usam índices suavizados de execução, e não notas ou domínio. O ajuste é limitado a 3 pontos na pontuação de encaixe e nunca prevalece sobre as restrições. O índice individual considera até 40 registros por período nos últimos 90 dias; só influencia com 6 registros em pelo menos 3 dias. Ausência de resposta não vira falta; exceções identificadas não entram no índice. A heurística não garante ótimo global.

## Contribuição coletiva opcional

Desativada por padrão. Somente o titular de uma conta Aluno pode autorizar ou revogar. Master e coordenação não podem autorizar em seu lugar. São consideradas apenas novas execuções registradas depois da autorização; a importação de um backup não ativa a contribuição.

Grupos são formados pelas respostas sobre duração de foco e estabilidade de rotina. Cada período exige 10 outros participantes autorizados e 30 registros. Cada participante tem peso igual, com até 10 observações por período. Contas especiais, inativas, não autorizadas e a própria conta-alvo são excluídas. A revogação retira as contribuições armazenadas, sem apagar o planejamento individual. As APIs de sugestão não mostram nomes nem cronogramas de outras pessoas.

Trata-se de associação exploratória entre execução declarada e horário, sujeita a vieses e diferenças de tarefas. Os limites de amostra são salvaguardas iniciais, não prova de eficácia ou garantia de anonimato absoluto. Os perfis de acesso anteriores permanecem válidos.

## Entrega e verificação

149 testes automatizados locais passaram: 99 de regressão e 50 novos. Fluxos Chromium/WSGI em memória verificaram questionário, confirmação explícita, prévia sem alteração, gravação, autorização/revogação, permissões, importação anterior e largura de 390 px. Não houve teste em iPhone físico nem auditoria independente.

O início do servidor executa verificações com contas temporárias, sem editar contas reais. `MEUCRONOGRAMA_MAPPING_CHECK_OK` confirma mapeamento, parâmetros, autorização/revogação, prévia/confirmação, histórico, isolamento e persistência no banco configurado. As contas técnicas e seus registros são removidos ao terminar. O código de testes locais acompanha o pacote de backup.

Esta entrega não cria cadastro público, não modifica senhas existentes e não importa resultados reais. A ligação automática entre as notas importadas e a distribuição de estudo por disciplina/assunto/habilidade continua pendente. As notas existentes continuam disponíveis na aba Desempenho.
