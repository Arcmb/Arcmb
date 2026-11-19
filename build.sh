#!/usr/bin/env bash
# O código deste repositório já é o site completo: a publicação instala as dependências
# e roda as verificações. Se alguma falhar, o build falha e a versão anterior continua no ar.
set -euo pipefail
python -m pip install -r requirements.txt
# As verificações rodam num banco SQLite temporário, nunca no banco de produção.
python checks/run_all.py
