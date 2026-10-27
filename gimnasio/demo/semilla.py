"""Uso: python -m gimnasio.demo.semilla --reiniciar."""

import argparse

from gimnasio import crear_app
from gimnasio.demo.servicio import reiniciar


def main(argumentos=None):
    analizador = argparse.ArgumentParser(description="Reinicia la demo con datos ficticios de Paraguay.")
    analizador.add_argument(
        "--reiniciar", action="store_true", required=True, help="Vacía los datos y carga la semilla ficticia."
    )
    analizador.parse_args(argumentos)
    with crear_app().app_context():
        reiniciar()
    print("Demo reiniciada con datos ficticios.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
