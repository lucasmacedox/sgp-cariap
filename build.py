"""Gera o executável de arquivo único para o sistema atual.

    pip install ".[executavel]"     # ou: pip install -r requirements-build.txt
    python build.py

Saída em dist/: SGP-Cariap-windows.exe, SGP-Cariap-macos-arm64, SGP-Cariap-linux-x86_64...
Para os três sistemas de uma vez, use o workflow .github/workflows/build.yml.
"""

import os
import platform
import sys

import PyInstaller.__main__


def nome_do_executavel() -> str:
    sistema = {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux")
    if sistema == "windows":
        return "SGP-Cariap-windows"
    arquitetura = platform.machine().lower().replace("amd64", "x86_64").replace("aarch64", "arm64")
    return f"SGP-Cariap-{sistema}-{arquitetura}"


def main() -> None:
    nome = nome_do_executavel()
    PyInstaller.__main__.run([
        "app.py",
        "--onefile",
        "--console",  # a janela mostra o endereço; fechá-la encerra o assistente
        "--name", nome,
        "--add-data", os.pathsep.join(["sgpcariap/static", "sgpcariap/static"]),
        "--hidden-import", "certifi",
        "--clean", "--noconfirm",
    ])
    print(f"\npronto: dist/{nome}{'.exe' if sys.platform == 'win32' else ''}")


if __name__ == "__main__":
    main()
