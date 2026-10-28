# Meu Cronograma 2.4.1 — cadastro pela coordenação e rotina por horários

## Cadastro de alunos pelo coordenador
Em **Meus alunos → Cadastrar aluno**, o coordenador informa nome, login e senha provisória. A nova conta tem exclusivamente o perfil **Aluno**, ativo, com troca obrigatória da senha no primeiro acesso. O cadastro é registrado na auditoria com o autor. Logins repetidos são rejeitados sem sobrescrever a conta existente.

O coordenador não ganha permissão para criar Master, Especial ou outros Coordenadores, redefinir senhas existentes, alterar perfis, desativar contas ou ver contas especiais. A administração de acessos continua exclusiva do Master. As restrições são verificadas no servidor; o novo cadastro possui uma rota própria, limitada à criação. O Master arcmb permanece protegido.

## Horário de início | Horário de término | Atividade
Em **Rotina e horários**, preencha uma linha para cada atividade já realizada no dia (trabalho, aula, almoço, cuidados com a família etc.). Marque os dias da semana e a repetição; há opção semanal, quinzenal independente ou data única. Pode acrescentar até 50 novas atividades por envio. Os exemplos não são preenchidos nem salvos automaticamente.

Os três campos ficam explícitos: **Horário de início | Horário de término | Atividade**. Na mesma página, a disponibilidade para novas sugestões também é preenchida com início e término separados, com várias faixas por dia. Horário não informado não é considerado livre. Atividades ocupadas são descontadas das faixas disponíveis, assim como sono e demais limites do motor.

O botão **Salvar rotina, horários e atividades** grava as novas atividades, disponibilidade e limites de uma só vez. Se uma linha estiver inválida, nenhuma parte dessa operação é confirmada. A gravação respeita a versão da conta para evitar sobrescrita concorrente. Atividades já existentes permanecem visíveis em tabela com Editar/Excluir. A edição detalhada anterior continua disponível para deslocamentos, fim de recorrência e atividades que atravessam a meia-noite.

O cadastro preserva o cronograma de estudo existente: não move nem exclui sessões automaticamente. Depois de alterar a rotina, confira a prévia no Quadro semanal. As permissões anteriores de edição individual, coordenação dos alunos e Master são mantidas. Contas especiais continuam restritas ao titular e aos Masters.

## Verificação e escopo
Foram executados 284 testes automatizados locais após reconstrução limpa (262 anteriores/coordenação + 22 da rotina). Os fluxos da interface Chromium com backend WSGI real em SQLite temporário tiveram 27 verificações: 12 de cadastro/permissões e 15 da rotina, salvamento, recuperação e largura móvel de 390 px. Não são testes em Safari ou iPhone físico, de carga ou auditoria independente.

`verify_coordinator.py` roda na inicialização com contas técnicas descartáveis e confirma criação restrita, troca de senha, impedimento de duplicação, auditoria, cadastro de rotina, persistência, concorrência e restrição das contas especiais. Os registros técnicos são removidos ao terminar. A mensagem `MEUCRONOGRAMA_V241_CHECK_OK` confirma a aprovação no banco configurado.

Nenhum cadastro real é criado nem nenhum planejamento existente é substituído ao instalar esta versão. Não há migração de esquema. Os dados da rotina reutilizam compromissos já suportados pelo motor. A navegação lateral ganhou rolagem para manter Meus alunos acessível em telas menores.

## Fonte
A extensão está em `source/v241-{1,2,3}.xzpart`, comprimida sem criptografia. `unpack_v241.py` verifica SHA-256 e a lista fechada de dez arquivos antes da extração. O ZIP de backup inclui código legível, testes e fontes comprimidos; não inclui credenciais, bancos de testes nem dados pessoais.
