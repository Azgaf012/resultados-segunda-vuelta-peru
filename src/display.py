"""Presentación de los resultados electorales en consola."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.table import Table

from .models import ResultadosEleccion
from .storage import leer_ultimos_participantes, leer_ultimos_totales

console = Console()


def mostrar_resultados(resultados: ResultadosEleccion) -> None:
    """Imprime los resultados en una tabla con formato en la consola."""
    console.print(f"\n[bold cyan]{resultados.titulo}[/bold cyan]")
    if resultados.fecha:
        console.print(f"[dim]Fecha: {resultados.fecha}[/dim]\n")

    tabla = Table(show_header=True, header_style="bold magenta")
    tabla.add_column("#", justify="right")
    tabla.add_column("Candidato")
    tabla.add_column("Partido")
    tabla.add_column("Votos", justify="right")
    tabla.add_column("%", justify="right")

    total = resultados.total_votos
    for posicion, candidato in enumerate(resultados.ordenados_por_votos(), start=1):
        tabla.add_row(
            str(posicion),
            candidato.nombre,
            candidato.partido,
            f"{candidato.votos:,}",
            f"{candidato.porcentaje(total):.2f}%",
        )

    console.print(tabla)

    ganador = resultados.ganador()
    if ganador:
        console.print(
            f"\n[bold green]Ganador: {ganador.nombre} "
            f"({ganador.porcentaje(total):.2f}%)[/bold green]\n"
        )


def mostrar_ultimo_snapshot(
    directorio: str | Path,
    nivel: str = "nacional",
    ubigeo: str = "",
    nombre_ambito: str = "PERÚ",
) -> None:
    """Muestra el snapshot más reciente de un ámbito leído desde el CSV."""
    participantes = leer_ultimos_participantes(directorio, nivel, ubigeo)
    totales = leer_ultimos_totales(directorio, nivel, ubigeo)

    console.print(
        f"\n[bold cyan]Resultados Segunda Vuelta - Perú "
        f"({nombre_ambito})[/bold cyan]"
    )

    if not participantes:
        console.print("[yellow]Aún no hay datos capturados.[/yellow]\n")
        return

    if totales:
        console.print(
            f"[dim]Actualizado: {totales['fecha_actualizacion']} · "
            f"Actas contabilizadas: {totales['actas_contabilizadas']}% · "
            f"Participación: {totales['participacion']}%[/dim]\n"
        )

    tabla = Table(show_header=True, header_style="bold magenta")
    tabla.add_column("#", justify="right")
    tabla.add_column("Candidato")
    tabla.add_column("Agrupación")
    tabla.add_column("Votos", justify="right")
    tabla.add_column("% válidos", justify="right")

    ordenados = sorted(
        participantes,
        key=lambda p: float(p["votos_validos"]),
        reverse=True,
    )
    for posicion, p in enumerate(ordenados, start=1):
        tabla.add_row(
            str(posicion),
            p["candidato"],
            p["agrupacion"],
            f"{int(p['votos_validos']):,}",
            f"{float(p['pct_validos']):.3f}%",
        )

    console.print(tabla)

    lider = ordenados[0]
    console.print(
        f"\n[bold green]En cabeza: {lider['candidato']} "
        f"({float(lider['pct_validos']):.3f}%)[/bold green]\n"
    )
