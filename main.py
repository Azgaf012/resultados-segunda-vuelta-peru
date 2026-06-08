"""Punto de entrada: recolecta resultados de ONPE en bucle y los muestra."""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from src.display import console, mostrar_ultimo_snapshot
from src.models import NIVEL_DEPARTAMENTO
from src.onpe_client import OnpeClient
from src.scraper import Scraper

DIRECTORIO_DATOS = Path(__file__).parent / "data"


def parsear_argumentos() -> argparse.Namespace:
    """Define y parsea los argumentos de línea de comandos."""
    parser = argparse.ArgumentParser(
        description="Recolector de resultados de la segunda vuelta (ONPE)."
    )
    parser.add_argument(
        "--intervalo",
        type=float,
        default=300.0,
        help="Segundos entre cada pasada de recolección (por defecto 300).",
    )
    parser.add_argument(
        "--nivel-maximo",
        choices=["nacional", "departamento", "provincia", "distrito"],
        default=NIVEL_DEPARTAMENTO,
        help="Nivel geográfico máximo a descargar (por defecto departamento).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.2,
        help="Segundos de espera entre peticiones HTTP (por defecto 0.2).",
    )
    parser.add_argument(
        "--una-vez",
        action="store_true",
        help="Ejecuta una sola pasada y termina (sin bucle).",
    )
    return parser.parse_args()


def main() -> None:
    """Ejecuta la recolección en bucle continuo hasta Ctrl+C."""
    args = parsear_argumentos()
    cliente = OnpeClient(delay=args.delay)
    scraper = Scraper(cliente, DIRECTORIO_DATOS, nivel_maximo=args.nivel_maximo)

    try:
        while True:
            console.print("[dim]Descargando resultados de ONPE...[/dim]")
            try:
                nuevas = scraper.ejecutar()
                console.print(
                    f"[green]Pasada completa: {nuevas} filas nuevas "
                    f"guardadas.[/green]"
                )
            except Exception as error:  # noqa: BLE001
                console.print(f"[red]Error en la pasada: {error}[/red]")

            mostrar_ultimo_snapshot(DIRECTORIO_DATOS)

            if args.una_vez:
                break

            console.print(
                f"[dim]Próxima actualización en {args.intervalo:.0f}s "
                f"(Ctrl+C para salir).[/dim]"
            )
            time.sleep(args.intervalo)
    except KeyboardInterrupt:
        console.print("\n[yellow]Detenido por el usuario.[/yellow]")
    finally:
        cliente.cerrar()


if __name__ == "__main__":
    main()
