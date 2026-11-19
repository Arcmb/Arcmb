#!/usr/bin/env bash
set -euo pipefail
# As verificações rodam no build.sh, antes da publicação. Aqui o servidor sobe direto,
# para que um reinício (por exemplo, depois de falta de memória) leve segundos e não minutos.
exec gunicorn webapp:application --bind "0.0.0.0:${PORT:-10000}" --workers 1 --threads 4 --timeout 60 --access-logfile -
