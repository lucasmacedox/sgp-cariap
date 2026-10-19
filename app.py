"""Atalho para iniciar o assistente: ``python app.py`` (equivale a ``python -m sgpcariap``).

Usado pelos lançadores ``iniciar.*`` e como ponto de entrada do PyInstaller.
"""

import sys

from sgpcariap.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
