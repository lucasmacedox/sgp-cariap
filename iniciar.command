#!/bin/bash
# macOS: dê dois cliques neste arquivo para abrir o assistente.
cd "$(dirname "$0")" || exit 1
if command -v python3 >/dev/null 2>&1; then
  exec python3 app.py "$@"
fi
echo "Python 3 não encontrado."
echo "Instale em https://www.python.org/downloads/ ou use o executável pronto (SGP-Cariap-macos)."
read -r -p "Pressione Enter para fechar..."
