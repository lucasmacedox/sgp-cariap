#!/usr/bin/env sh
# Linux: abre o assistente (precisa de Python 3.10+, que já vem na maioria das distros).
cd "$(dirname "$0")" || exit 1
for py in python3 python; do
  if command -v "$py" >/dev/null 2>&1; then exec "$py" app.py "$@"; fi
done
echo "Python 3 não encontrado. Instale com: sudo apt install python3  (ou use o executável pronto)."
exit 1
