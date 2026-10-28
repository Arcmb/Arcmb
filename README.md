# Horário da May — online 2.0

Planejador de rotina, estudos e revisões sem IA. Interface HTML/CSS/JavaScript e servidor Python/WSGI com PostgreSQL. Esta ramificação é independente do site existente na main.

## Fonte e integridade

O código-fonte completo do aplicativo está comprimido, sem criptografia, em `source/part1.xzpart`, `part2.xzpart`, `part3.xzpart`. Execute `python unpack_source.py` para obter os 11 arquivos originais (`webapp.py`, `planner.py`, interface e dependências). O extrator verifica SHA-256 e uma lista fechada de caminhos antes de escrever. Nenhuma senha real ou dado pessoal de planejamento faz parte do pacote.

SHA-256 do pacote concatenado: `69251ef48eac0f10816e103ef76bb25361448542009c51d27ba0bad1bcfbca16`.

Para manutenção futura, descompacte e edite os arquivos. Pode-se substituir este empacotamento por arquivos-fonte normais e mudar o build para `pip install -r requirements.txt`; não rode o extrator sobre edições que ainda não tenham sido incorporadas ao pacote.

## Render

Nome: `horariodamay`; região: Ohio; runtime: Python; plano inicialmente Free.

Build:
```
python unpack_source.py && pip install -r requirements.txt
```
Start:
```
gunicorn webapp:application --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 60 --access-logfile -
```

Configure exclusivamente no painel Environment:

- `DATABASE_URL`: URL interna do PostgreSQL `ritmo-online-db` existente.
- `SECRET_KEY`: segredo aleatório de pelo menos 32 caracteres.
- `MASTER_USERNAME`: `arcmb`.
- `MASTER_PASSWORD`: senha inicial do proprietário, somente para criar a conta.
- `ALLOWED_HOSTS`: `horariodamay.onrender.com`.
- `DATABASE_EXPIRES_AT`: vencimento ISO opcional, exibido só ao Master.

NUNCA configure `LOCAL_TEST=1` na nuvem. Sem DATABASE_URL, a página responde configuração pendente; não aceita salvar em um disco efêmero. `/healthz` é apenas um indicador de processo/configuração, não uma prova de prontidão do banco. Após configurar o PostgreSQL, valide login, gravação e leitura em outro acesso.

A integração de publicação não fornece a senha do PostgreSQL. Copie Internal Database URL no painel do banco e configure DATABASE_URL no serviço, salvando com novo deploy. Não envie credenciais ao GitHub.

## Contas

`arcmb` é Master permanente, com senha inicial configurada fora do código. Pode selecionar a conta da Mayra, editar sua rotina, cadastrar usuários e redefinir senhas. O proprietário não pode ser desativado ou rebaixado.

A conta `mayra` é criada sem senha utilizável. Depois de entrar, o Master define uma senha provisória em Painel Master > Mayra > Editar acesso. Ela deverá trocar a senha no primeiro login. Não há cadastro público ou recuperação por e-mail.

## Recursos

Diagnóstico, disponibilidade, sono, pausas, reserva, compromissos semanais/quinzenais independentes, deslocamentos, bloqueios pontuais, disciplinas e metas, conteúdos estudados continuamente, revisões configuráveis, quadro semanal em grade/lista, edição/fixação de blocos, verificações e perguntas condicionais, histórico, JSON/CSV/ICS e importação dos backups RITMO locais.

O motor usa heurística de encaixe e resultados declarados. Não garante ótimo global, não interpreta texto livre com IA e não realiza diagnóstico ou previsão de notas. Não realizar uma tarefa é tratado separadamente de dificuldade de conteúdo.

## Segurança e armazenamento

PostgreSQL obrigatório na nuvem; tabelas `hmay_*`. Senhas PBKDF2-SHA256 com sal aleatório, sessões opacas, cookies Secure/HttpOnly/Lax, CSRF, autorização no servidor, bloqueio de tentativas, consultas parametrizadas e proteção contra sobrescrita concorrente com versão por perfil. Confirmação de salvamento só depois do commit.

O Master pode acessar os dados da usuária; a interface informa esse acesso. Backups JSON/CSV não são criptografados e contêm dados pessoais. JSON não inclui credenciais e não substitui backup administrativo completo do banco. Mantenha cópias externas.

O banco gratuito identificado expira em 2026-11-27T01:30:38Z (26/11/2026 às 22h30 em Belém). Migre ou altere o plano antes do vencimento. Nenhum plano pago é contratado pelo aplicativo. Consulte as condições atuais em https://render.com/docs/free.

## iPhone

Acesse pelo Safari. Interface responsiva, lista semanal e formulários adaptados. Exige internet para carregar e salvar; não há edição offline nem notificações com o site fechado.

## Verificação realizada

57 testes locais do motor/servidor aprovados, incluindo 100 cronogramas aleatórios dentro de um teste. 17 fluxos de interface aprovados em Chromium, desktop e viewport móvel. A interface utilizou ponte para WSGI/SQLite porque a navegação HTTP é bloqueada no ambiente de teste. Não equivale a teste em Safari físico ou validação do PostgreSQL de produção.

## Teste local explícito

Depois de extrair, com Python 3.11+: defina LOCAL_TEST=1 e MASTER_PASSWORD apenas no ambiente local e execute `python webapp.py`. Abra http://127.0.0.1:8765. Não exponha esse servidor de teste à internet.
