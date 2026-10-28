# Meu Cronograma 2.1 — disciplinas dinâmicas e permissões

## Modelo e importação

A aba Desempenho recebe XLSX e CSV com cabeçalhos na primeira linha. As colunas existentes do modelo são preservadas. NOME, TIPO (ou Atividade) e data identificam cada registro; TURMA e LOGIN são opcionais. A identificação final é confirmada vinculando o aluno a uma conta existente. Não são criadas contas automaticamente.

Acrescente quantas disciplinas forem necessárias, dentro do limite de 300 colunas por lote, usando `Acertos - Nome da disciplina`. Exemplos: `Acertos - Inglês`, `Acertos - Espanhol`, `Acertos - Robótica`. O sistema reconhece os nomes sem programação adicional. Para informar o denominador, acrescente opcionalmente `Questões - Nome da disciplina`.

Campos vazios significam não informado, não zero. Colunas vazias são reconhecidas. Em reimportações, vazios nunca apagam valores existentes. Zero é um número válido. Nomes são normalizados para acentos, espaços e maiúsculas; nomes diferentes não são mesclados por suposição. Cabeçalhos repetidos são rejeitados.

A prévia mostra disciplinas, vínculos e contagens de registros novos, atualizados, repetidos e sem vínculo. Nenhum resultado é gravado antes da confirmação. Registros sem vínculo só são ignorados com confirmação explícita. Atividade + data + conta identificam duplicidades. Por padrão, valores existentes são mantidos; a opção de substituir exige nova conferência. A confirmação assinada expira em 30 minutos e verifica alterações concorrentes. Falha no lote reverte a transação.

Limites por arquivo: 3 MB, 5.000 registros, 300 colunas e 300.000 células. XLSX descompactado limitado a 25 MB; leitura com defusedxml, sem macros ou vínculos externos. Fórmulas sem resultado salvo devem ser recalculadas no Excel ou coladas como valores. Há leitura de uma aba por importação.

O histórico exibe as 500 atividades mais recentes de cada conta. Os percentuais só são calculados se houver total de questões maior que zero. As notas gerais do modelo permanecem como dados da atividade. Não há inferência de desempenho por disciplina a partir das notas por área.

Importar não altera automaticamente a rotina ou a dificuldade. A integração automática de resultados ao motor, o detalhamento estruturado por assunto/habilidade e a revisão do questionário continuam sendo etapas separadas, não concluídas por esta versão.

## Perfis

- arcmb permanece Master proprietário. Não pode ser rebaixado ou desativado pela interface.
- O Master define o perfil em Painel Master > Editar acesso > Perfil de acesso.
- Coordenador consulta e edita as rotinas de todas as contas Aluno, e importa seus resultados. Não administra usuários nem acessa contas especiais ou de outros gestores.
- Especial acessa a própria conta. Somente o titular e os Masters podem consultar ou editar suas informações.
- Aluno acessa apenas a própria conta e seu histórico. O papel legado `user` tem os mesmos limites de Aluno.
- Mudanças de perfil encerram as sessões da conta alterada. Autorização é verificada no servidor, não apenas ocultada na tela.

Nenhuma senha ou classificação de conta existente é modificada por esta atualização, salvo a garantia já existente do Master proprietário. Nenhum resultado real da planilha foi enviado ao banco na preparação do código.

## Verificação local

57 testes anteriores e 42 novos testes de importação e permissões: 99 aprovados. Também foi executado um fluxo de interface Chromium/WSGI em memória, com conferência/confirmacão, disciplinas dinâmicas, seletor de perfil, isolamento do coordenador e largura móvel de 390 px, sem erros JavaScript. A navegação de rede do navegador de teste é bloqueada neste ambiente; a interface usou uma ponte local para WSGI. Isso não equivale a um teste no iPhone físico nem a uma auditoria completa.

A leitura local do modelo preservou 201 registros, 30 colunas e 12 disciplinas vazias. As tabelas anteriores e os arquivos originais são preservados; o build aplica uma extensão versionada e cria a tabela adicional hmay_performance sem apagar informações existentes.
