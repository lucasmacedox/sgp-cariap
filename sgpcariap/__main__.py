from __future__ import annotations

import argparse
import logging
import sys
import threading
import webbrowser

from .ambiente import VARIAVEL_DADOS, Ambiente
from .web import ApiAssistente, ServidorAssistente


def _argumentos(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="sgp-cariap",
        description="Assistente de configuração do SGP para o Cariap.",
        epilog=f"Registros das execuções: ~/SGP-Cariap/execucoes (ou a pasta em {VARIAVEL_DADOS}).",
    )
    parser.add_argument("--porta", type=int, default=8765, help="primeira porta a tentar (padrão: 8765)")
    parser.add_argument("--sem-navegador", action="store_true", help="não abrir o navegador")
    parser.add_argument("--detalhado", action="store_true", help="mostrar cada requisição no terminal")
    return parser.parse_args(argv)


def _console_tolerante() -> None:
    # console do Windows sem UTF-8
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(errors="replace")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass


def main(argv: list[str] | None = None) -> int:
    _console_tolerante()
    args = _argumentos(argv)
    logging.basicConfig(level=logging.DEBUG if args.detalhado else logging.WARNING,
                        format="%(asctime)s %(levelname)s %(message)s")

    ambiente = Ambiente.detectar()
    servidor = ServidorAssistente(ApiAssistente(ambiente), ambiente.recursos, args.porta)

    print(f"Assistente SGP x Cariap {ambiente.versao}", flush=True)
    print(f"Aberto em {servidor.url}  (feche esta janela ou use Ctrl+C para encerrar)", flush=True)
    print(f"Registros das execuções: {ambiente.execucoes}", flush=True)
    if not args.sem_navegador:
        threading.Timer(0.8, webbrowser.open, args=(servidor.url,)).start()
    try:
        servidor.servir()
    except KeyboardInterrupt:
        print("encerrado")
    return 0


if __name__ == "__main__":
    sys.exit(main())
