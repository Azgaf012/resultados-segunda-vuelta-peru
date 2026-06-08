"""Persistencia de snapshots de resultados en CSV histórico.

Cada captura se agrega (append) a un CSV. Se evita duplicar filas cuando la
ONPE no ha publicado una nueva `fechaActualizacion` para un mismo ámbito.
"""

from __future__ import annotations

import csv
from dataclasses import asdict
from pathlib import Path

from .models import RegistroParticipante, RegistroTotales

ARCHIVO_TOTALES = "resultados_totales.csv"
ARCHIVO_PARTICIPANTES = "resultados_participantes.csv"


def _claves_existentes(ruta: Path, campos_clave: tuple[str, ...]) -> set[tuple]:
    """Lee un CSV y devuelve el conjunto de claves ya presentes."""
    if not ruta.exists():
        return set()
    claves: set[tuple] = set()
    with ruta.open(newline="", encoding="utf-8") as archivo:
        lector = csv.DictReader(archivo)
        for fila in lector:
            claves.add(tuple(fila[campo] for campo in campos_clave))
    return claves


def _anexar(
    ruta: Path,
    columnas: tuple[str, ...],
    filas: list[dict],
    campos_clave: tuple[str, ...],
) -> int:
    """Anexa filas nuevas a un CSV, omitiendo las ya existentes.

    Returns:
        Cantidad de filas efectivamente escritas.
    """
    ruta.parent.mkdir(parents=True, exist_ok=True)
    existentes = _claves_existentes(ruta, campos_clave)
    archivo_nuevo = not ruta.exists()

    escritas = 0
    with ruta.open("a", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=columnas)
        if archivo_nuevo:
            escritor.writeheader()
        for fila in filas:
            clave = tuple(str(fila[campo]) for campo in campos_clave)
            if clave in existentes:
                continue
            escritor.writerow({col: fila[col] for col in columnas})
            existentes.add(clave)
            escritas += 1
    return escritas


# Clave de deduplicación: un ámbito (nivel + ubigeo) por fecha de actualización.
_CLAVE_TOTALES = ("nivel", "ubigeo", "fecha_actualizacion")
_CLAVE_PARTICIPANTES = ("nivel", "ubigeo", "dni", "fecha_actualizacion")


def guardar_totales(
    registros: list[RegistroTotales], directorio: str | Path
) -> int:
    """Anexa registros de totales al CSV histórico (con dedupe)."""
    ruta = Path(directorio) / ARCHIVO_TOTALES
    filas = [asdict(r) for r in registros]
    return _anexar(ruta, RegistroTotales.CAMPOS, filas, _CLAVE_TOTALES)


def guardar_participantes(
    registros: list[RegistroParticipante], directorio: str | Path
) -> int:
    """Anexa registros de participantes al CSV histórico (con dedupe)."""
    ruta = Path(directorio) / ARCHIVO_PARTICIPANTES
    filas = [asdict(r) for r in registros]
    return _anexar(
        ruta, RegistroParticipante.CAMPOS, filas, _CLAVE_PARTICIPANTES
    )


def _leer_filas(ruta: Path) -> list[dict]:
    """Lee todas las filas de un CSV como diccionarios."""
    if not ruta.exists():
        return []
    with ruta.open(newline="", encoding="utf-8") as archivo:
        return list(csv.DictReader(archivo))


def leer_ultimos_participantes(
    directorio: str | Path,
    nivel: str = "nacional",
    ubigeo: str = "",
) -> list[dict]:
    """Devuelve los participantes del snapshot más reciente para un ámbito.

    Filtra por nivel y ubigeo y se queda con las filas de la `fecha_actualizacion`
    máxima encontrada.
    """
    ruta = Path(directorio) / ARCHIVO_PARTICIPANTES
    filas = [
        f
        for f in _leer_filas(ruta)
        if f["nivel"] == nivel and f["ubigeo"] == ubigeo
    ]
    if not filas:
        return []
    ultima_fecha = max(f["fecha_actualizacion"] for f in filas)
    return [f for f in filas if f["fecha_actualizacion"] == ultima_fecha]


def leer_ultimos_totales(
    directorio: str | Path,
    nivel: str = "nacional",
    ubigeo: str = "",
) -> dict | None:
    """Devuelve los totales del snapshot más reciente para un ámbito."""
    ruta = Path(directorio) / ARCHIVO_TOTALES
    filas = [
        f
        for f in _leer_filas(ruta)
        if f["nivel"] == nivel and f["ubigeo"] == ubigeo
    ]
    if not filas:
        return None
    return max(filas, key=lambda f: f["fecha_actualizacion"])


def leer_historico_participantes(
    directorio: str | Path,
    nivel: str = "nacional",
    ubigeo: str = "",
    n: int = 3,
) -> list[tuple[str, list[dict]]]:
    """Devuelve los últimos `n` snapshots de participantes de un ámbito.

    Returns:
        Lista de tuplas `(fecha_actualizacion, filas)` ordenadas de la más
        antigua a la más reciente (máximo `n` elementos).
    """
    ruta = Path(directorio) / ARCHIVO_PARTICIPANTES
    filas = [
        f
        for f in _leer_filas(ruta)
        if f["nivel"] == nivel and f["ubigeo"] == ubigeo
    ]
    if not filas:
        return []
    por_fecha: dict[str, list[dict]] = {}
    for f in filas:
        por_fecha.setdefault(f["fecha_actualizacion"], []).append(f)
    fechas = sorted(por_fecha.keys())[-n:]
    return [(fecha, por_fecha[fecha]) for fecha in fechas]


def leer_historico_totales(
    directorio: str | Path,
    nivel: str = "nacional",
    ubigeo: str = "",
    n: int = 3,
) -> dict[str, dict]:
    """Devuelve los totales de los últimos `n` snapshots, indexados por fecha."""
    ruta = Path(directorio) / ARCHIVO_TOTALES
    filas = [
        f
        for f in _leer_filas(ruta)
        if f["nivel"] == nivel and f["ubigeo"] == ubigeo
    ]
    if not filas:
        return {}
    por_fecha = {f["fecha_actualizacion"]: f for f in filas}
    fechas = sorted(por_fecha.keys())[-n:]
    return {fecha: por_fecha[fecha] for fecha in fechas}


def listar_ambitos(
    directorio: str | Path, nivel: str = "departamento"
) -> list[dict]:
    """Lista los ámbitos disponibles en el CSV de totales para un nivel.

    Returns:
        Lista de dicts con `ubigeo` y `nombre_ubigeo`, ordenada por nombre.
    """
    ruta = Path(directorio) / ARCHIVO_TOTALES
    vistos: dict[str, str] = {}
    for fila in _leer_filas(ruta):
        if fila["nivel"] == nivel:
            vistos[fila["ubigeo"]] = fila["nombre_ubigeo"]
    return [
        {"ubigeo": ubigeo, "nombre_ubigeo": nombre}
        for ubigeo, nombre in sorted(vistos.items(), key=lambda kv: kv[1])
    ]

