# Ativação — Meu Cronograma

Use somente a ramificação `meucronograma` de `Arcmb/Arcmb`.
Crie um **Web Service** Python, nome `meucronograma`, região Ohio, plano Free.
Build: `bash build.sh`. Start: `bash start.sh`. Health check: `/readyz`.

No Environment:
- `DATABASE_URL`: obtenha no projeto Neon `horariodamay` usando Connect. Mantenha os parâmetros TLS.
- `SECRET_KEY`: valor aleatório de pelo menos 32 caracteres.
- `MASTER_USERNAME`: `arcmb`.
- `MASTER_PASSWORD`: a senha inicial escolhida pelo proprietário. Não salve neste arquivo.
- `ALLOWED_HOSTS`: `meucronograma.onrender.com` ou o domínio efetivamente atribuído.
- `PYTHONUNBUFFERED`: `1`.

Não configure LOCAL_TEST nem use o banco antigo ritmo-online-db. Não envie segredos ao GitHub.
Após a publicação, confira `/readyz`, a tela `/login` e o log MEUCRONOGRAMA_RELEASE_CHECK_OK.
Entre como Master e defina a senha da Mayra em Painel Master → Editar acesso.
A existência deste arquivo não significa que o serviço já foi publicado; confira o status live no Render.
