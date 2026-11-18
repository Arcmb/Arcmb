#!/usr/bin/env bash
# Testes de navegador: sobe o site local com dados sintéticos e roda cada cenário no Chrome sem janela.
# Requer: google-chrome, Node 22+ e Python 3. Uso: bash tests/browser/run.sh
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TMP="$(mktemp -d)"
export ENEM_XLSX="$TMP/itens_enem.xlsx" LOCAL_TEST=1 LOCAL_DB="$TMP/browser.sqlite3" SECRET_KEY="$(python3 -c "print('k'*64)")" MASTER_PASSWORD=TEST_master_13579 ALLOWED_HOSTS=localhost,127.0.0.1 PORT=8765
python3 "$ROOT/tests/browser/seed.py" "$ROOT" "$LOCAL_DB" >/dev/null || exit 1
(cd "$ROOT" && python3 webapp.py >"$TMP/server.log" 2>&1) & SERVER=$!
google-chrome --headless=new --no-sandbox --remote-debugging-port=9222 --window-size=1400,1000 --user-data-dir="$TMP/chrome" about:blank >"$TMP/chrome.log" 2>&1 & CHROME=$!
trap 'kill $SERVER $CHROME 2>/dev/null; rm -rf "$TMP"' EXIT
sleep 5
FAILED=0
for t in "$ROOT"/tests/browser/0*${1:-}*.mjs; do
  echo "== $(basename "$t")"
  timeout 180 node "$t" >"$TMP/out.txt" 2>&1; code=$?
  grep -E "^(FALHA|Falhas)" "$TMP/out.txt" || tail -5 "$TMP/out.txt"
  [ $code = 0 ] || FAILED=1
done
[ $FAILED = 0 ] && echo "BROWSER_TESTS_OK" || { echo "BROWSER_TESTS_FAILED"; exit 1; }
