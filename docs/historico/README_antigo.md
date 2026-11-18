# Meu Cronograma — versão online

Planejamento semanal, conteúdos estudados e revisões adaptativas sem IA.
Interface responsiva HTML/CSS/JavaScript, servidor Python/WSGI e PostgreSQL no Neon.

## Publicação

Repositório `Arcmb/Arcmb`, ramificação `meucronograma`.
A ramificação `main` e os outros sites não são alterados.
Endereço pretendido: `https://meucronograma.onrender.com` (confirme o endereço atribuído pelo Render).
Build: `bash build.sh`. Inicialização: `bash start.sh`. Região: Ohio. Plano: Free.

Configure no ambiente do Render, nunca no código:
- `DATABASE_URL`: conexão PostgreSQL do projeto Neon existente `horariodamay`.
- `SECRET_KEY`: segredo aleatório de pelo menos 32 caracteres.
- `MASTER_USERNAME`: `arcmb`.
- `MASTER_PASSWORD`: senha inicial do proprietário. Não redefine senha existente.
- `ALLOWED_HOSTS`: `meucronograma.onrender.com`.
- `PYTHONUNBUFFERED`: `1`.

Não configure `LOCAL_TEST=1` na nuvem. Sem banco e chave, o aplicativo recusa gravar.
Não é usado o antigo banco `ritmo-online-db` do Render. Nenhum banco é criado pelo Blueprint.
O projeto, banco, tabelas e cookies internos preservam os identificadores antigos para compatibilidade.

## Contas

`arcmb` é o Master proprietário permanente. Pode cadastrar contas, abrir e editar planejamentos,
redefinir senhas dos usuários e consultar auditoria. Não pode ser rebaixado ou desativado pela interface.
A conta `mayra` é criada sem senha utilizável. O Master define uma senha provisória em
**Painel Master → Mayra → Editar acesso**. No primeiro acesso, ela precisa trocar essa senha.
Não há cadastro público nem recuperação por e-mail. O usuário comum só acessa sua própria conta.

## Fonte verificável

`source/part1.xzpart`, `part2.xzpart` e `part3.xzpart` contêm o código original sem criptografia.
`unpack_source.py` valida SHA-256 e uma lista fechada de caminhos antes de extrair.
`prepare_release.py` aplica os nomes Meu Cronograma, preserva o esquema do banco e adiciona `/readyz`.
Não edite os arquivos extraídos sem também atualizar o pacote ou o processo de build.
Hash do pacote original: `69251ef48eac0f10816e103ef76bb25361448542009c51d27ba0bad1bcfbca16`.

## Verificações

57 testes locais de motor e servidor aprovados após a mudança de nome.
O verificador `verify_release.py` passou localmente com SQLite.
No servidor, antes de iniciar o Gunicorn, ele verifica o banco configurado com uma conta técnica temporária:
login, gravação, leitura em nova sessão, restrição de acesso, CSRF e conflito de versões.
A conta e os registros técnicos são removidos ao concluir. Contas e planejamentos reais não são editados.
O log `MEUCRONOGRAMA_RELEASE_CHECK_OK` confirma a aprovação; não são impressas credenciais.
`/readyz` testa a conexão com o banco. `/healthz` informa se há configuração mínima.
Isso não substitui o teste manual no iPhone nem uma auditoria completa de segurança.

## Recursos

Diagnóstico da rotina, disponibilidade por dia, compromissos semanais/quinzenais independentes,
sono, pausas, reserva, deslocamentos, disciplinas e metas, cadastro contínuo de conteúdos,
revisões periódicas configuráveis, verificações, perguntas de retomada, histórico, grade/lista semanal,
edição/fixação de blocos, exportação JSON/CSV/ICS e importação de backups RITMO.
O motor é uma heurística explicável; não garante ótimo global nem interpreta texto livre por IA.
Ausência de execução não é classificada automaticamente como falta de conhecimento.

## Segurança e operação

Senhas PBKDF2-SHA256 com sal aleatório, sessões opacas, cookies Secure/HttpOnly/Lax,
autorização no servidor, CSRF, limitação de tentativas, SQL parametrizado e controle de versão.
A gravação só é confirmada depois do commit. Os dados da usuária podem ser vistos pelo Master.
Backups JSON/CSV contêm dados pessoais e não são criptografados; mantenha cópias externas privadas.
O plano gratuito do Render pode suspender o serviço por inatividade; não oferece disponibilidade contínua.
No iPhone, acesse pelo Safari. É necessária internet para carregar e salvar.
Não há edição offline nem notificações com o site fechado.
