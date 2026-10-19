"""Gera o executável do sistema atual em dist/ (pip install -r requirements-build.txt)."""

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
        "--console",
        "--name", nome,
        "--add-data", os.pathsep.join(["sgpcariap/static", "sgpcariap/static"]),
        "--hidden-import", "certifi",
        "--clean", "--noconfirm",
    ])
    print(f"\npronto: dist/{nome}{'.exe' if sys.platform == 'win32' else ''}")


if __name__ == "__main__":
    main()
