# Meu Cronograma 2.3 — perguntas claras e importação seletiva

## Perguntas do participante

As 20 perguntas mantêm os identificadores das alternativas e as respostas já salvas. “Bloco” foi substituído por “período de estudo” no novo questionário e em suas propostas. Cada pergunta possui uma explicação e, quando útil, um exemplo. A pergunta de foco trata de estudo individual, não de emprego nem de duração de aulas. A pergunta de registro trata de marcar no sistema o que foi realizado, não de escrever resumos. Salvar respostas não altera o cronograma sem aprovação.

## Modelo seletivo e importação de resultados

Em **Desempenho → Escolher campos e gerar modelo**, selecione os dados que serão enviados. NOME, TIPO e data são obrigatórios. LOGIN é opcional e auxilia a vincular a conta. TURMA e COR DA PROVA são campos separados. Há notas gerais, bonificação, acertos por área, disciplinas, habilidades H01–H30 e acerto/erro por questão. É possível acrescentar disciplinas e escolher numeração de questões de 1 a 180. O arquivo é gerado em XLSX ou CSV UTF-8.

Depois de selecionar um arquivo, confira a correspondência entre suas colunas e os campos do sistema. Deixe o destino vazio para ignorar uma coluna. Há sugestão de correspondência, inclusive para alguns cabeçalhos com acentuação corrompida; nomes e respostas dos alunos não são reescritos. A prévia mostra os vínculos e o que será gravado. Apenas confirmar a prévia grava o lote.

- Célula vazia significa não informado; zero é um resultado válido.
- Acerto/erro por questão: 1 ou Acerto/C; 0 ou Erro/E. Não são letras de alternativa escolhida.
- Habilidades precisam de área LC/CH/CN/MT selecionada no importador ou informada por linha. H01 de Natureza não é misturada com H01 de Linguagens.
- Acertos de disciplina, habilidade e questão ficam separados. Não se somam entre si.
- Importações parciais completam dados. Vazios não apagam valores existentes e conflitos só são substituídos por opção explícita.
- A chave dos resultados continua sendo conta + atividade + data. Cor e vínculo com simulado são conferidos para evitar misturar cadernos.
- Notas TRI e bonificação são recebidas, não recalculadas. “Nota com bonificação” é separada do valor informado de bonificação.

Os limites anteriores de tamanho e quantidade permanecem: 3 MB, 5.000 registros, 300 colunas e 300.000 células por arquivo.

## Simulados e questões

O menu **Simulados e questões**, restrito à equipe, permite importar um mapa de questões sem resultados pessoais. Informe nome da avaliação, data, cor da prova e, quando cabível, área. O modelo tem QUESTÃO, ÁREA, DISCIPLINA, TÓPICO, ASSUNTO, HABILIDADE, LÍNGUA ESTRANGEIRA e GABARITO. Questão e disciplina são necessárias; classificações desconhecidas podem ficar em branco.

O modelo enviado com a coluna “Prova Azul” foi lido localmente: 45 questões, numeradas de 91 a 135. Cabeçalhos desse formato são aceitos. O tópico não é inferido a partir do assunto. Nenhuma questão real ou resultado real foi importado no banco durante a preparação desta versão.

Ao importar os resultados individuais por questão, escolha o mapa correto. Nome, data e cor são conferidos. O sistema apresenta acertos/erros por área, disciplina, tópico, assunto e habilidade usando apenas questões com resultado informado. Questões sem resultado não viram erros. A classificação calculada aparece separada dos totais importados, sem sobrescrevê-los. Se houver duas versões de língua estrangeira da mesma questão, a opção do participante é necessária.

O coordenador pode cadastrar e atualizar seus mapas; o Master pode administrar todos. O catálogo não expõe dados pessoais dos alunos. As restrições dos perfis Especial e Aluno continuam aplicadas aos resultados pessoais.

## O que não muda nesta entrega

Contas, senhas, planejamentos, respostas e resultados existentes são preservados. Uma tabela de mapas é acrescentada sem excluir as anteriores. Importar desempenho não redistribui automaticamente o estudo nem calcula novas notas TRI. O planejamento adaptativo já existente continua usando suas próprias regras e confirmações.

## Fonte e integridade

A extensão está comprimida, sem criptografia, em `source/v23-1.xzpart` e `source/v23-2.xzpart`. `python unpack_v23.py` verifica o SHA-256, o limite de descompressão e uma lista fechada de nove caminhos antes de extrair o código legível. Não utiliza rede, comandos externos ou credenciais.

SHA-256 concatenado: `2e04252bfb2150231dad36ff9e73fe248cc658021b6b3726973bf6c492cc4fa1`.

O build executa a extração da extensão e as preparações anteriores antes de `enhance_release.py`. O ZIP de backup contém também a fonte legível e os testes. Edite a fonte e atualize o pacote antes de republicar; não edite apenas a cópia gerada durante um build.

## Validação

191 testes automatizados locais passaram após montagem limpa, incluindo 42 novos testes. A interface foi testada em Chromium com ponte WSGI em processo, incluindo 20 perguntas, XLSX seletivo, coluna ignorada, conferência/confirmação, mapa do simulado, vínculo e largura de 390 px, sem erros JavaScript. Isso não equivale a teste em iPhone físico ou auditoria independente.

`verify_selective.py` executa, na inicialização, um teste adicional no banco configurado: modelo XLSX, importação seletiva, mapa de questões, leitura classificada, isolamento e persistência. Usa contas técnicas temporárias e remove seus registros ao terminar. A mensagem `MEUCRONOGRAMA_V23_CHECK_OK` confirma aprovação no ambiente em que for executado. `/readyz` inclui `version: 2.3` para distinguir a versão publicada.
