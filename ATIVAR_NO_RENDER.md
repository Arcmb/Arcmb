# Ativar Horário da May

**Status:** código desenvolvido e publicado nesta branch. A criação automática do serviço Render foi bloqueada pela integração. O endereço ainda não foi publicado nem reservado.

## Caminho recomendado

[Revisar e ativar no Render](https://render.com/deploy?repo=https%3A%2F%2Fgithub.com%2FArcmb%2FArcmb%2Ftree%2Fhorariodamay)

1. Entre na conta Render e selecione **My Workspace**, onde já existe o banco **ritmo-online-db**.
2. Confira serviço **horariodamay**, branch **horariodamay**, região **Ohio** e plano **Free**.
3. Preencha **MASTER_PASSWORD** com sua senha inicial diretamente no campo secreto do Render. O login será **arcmb**.
4. Revise e confirme Deploy/Apply. O Blueprint referencia o banco existente por `fromDatabase` e gera `SECRET_KEY` automaticamente, sem criar outro banco ou alterar seu plano.
5. Quando o serviço indicar **Live**, abra o endereço real mostrado no painel. O nome solicitado é `horariodamay`; a disponibilidade de `horariodamay.onrender.com` só será confirmada na criação.
6. Entre como **arcmb** e abra **Painel Master > Mayra > Editar acesso** para definir uma senha provisória para **mayra**. Ela deverá trocá-la no primeiro acesso.
7. Faça um registro no iPhone, saia, entre novamente e confira também em outro dispositivo. Exporte um JSON como backup.

Este caminho substitui a necessidade de copiar `DATABASE_URL` descrita na configuração manual do README. Se a referência ao banco falhar, confira o workspace e o nome do banco. A configuração manual continua disponível como alternativa.

## Limites e validação

A branch main e os sites existentes não foram alterados. Nenhuma senha real está no código. Nenhum plano pago foi contratado.

O banco gratuito existente informa vencimento em **26/11/2026 às 22h30 em Belém** (27/11/2026 01h30 UTC). Migre ou altere o plano antes dessa data.

57 testes locais de motor/servidor e 17 fluxos de interface passaram. Testes em Chromium desktop/viewport móvel com WSGI/SQLite não equivalem a validação em Safari físico ou PostgreSQL de produção. YAML conferido localmente e contra documentação; não houve validação pela CLI/API do Render.

## Manutenção do código

`python unpack_source.py` extrai os 11 arquivos originais verificados por SHA-256. Para editar e manter fontes normais, faça a extração, remova o empacotamento e altere o build para `pip install -r requirements.txt`. Não execute o extrator sobre alterações ainda não incorporadas ao pacote.
