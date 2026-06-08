"""Carga de datos de resultados desde un archivo JSON."""

from __future__ import annotations

import json
from pathlib import Path

from .models import Candidato, ResultadosEleccion


def cargar_resultados(ruta: str | Path) -> ResultadosEleccion:
    """Carga los resultados electorales desde un archivo JSON.

    Args:
        ruta: Ruta al archivo JSON con los datos.

    Returns:
        Una instancia de ResultadosEleccion con los datos cargados.
    """
    ruta = Path(ruta)
    with ruta.open(encoding="utf-8") as archivo:
        datos = json.load(archivo)

    candidatos = [
        Candidato(
            nombre=item["nombre"],
            partido=item["partido"],
            votos=int(item.get("votos", 0)),
        )
        for item in datos.get("candidatos", [])
    ]

    return ResultadosEleccion(
        titulo=datos.get("titulo", "Segunda Vuelta - Perú"),
        fecha=datos.get("fecha", ""),
        candidatos=candidatos,
    )
