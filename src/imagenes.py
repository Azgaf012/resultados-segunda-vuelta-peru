"""Descarga y cacheo de imágenes (fotos de candidatos y logos de partidos).

Las imágenes provienen del sitio público de ONPE y se guardan localmente en
la carpeta de estáticos de la web para servirlas sin depender de la red.
"""

from __future__ import annotations

from pathlib import Path

import requests

BASE_IMG = "https://resultadosegundavuelta.onpe.gob.pe/assets/img"
URL_CANDIDATO = BASE_IMG + "/candidatos/{dni}.png"
URL_PARTIDO = BASE_IMG + "/partidos/{codigo:08d}.png"

# Carpeta de estáticos de la web (src/static).
DIR_STATIC = Path(__file__).resolve().parent / "static"
DIR_CANDIDATOS = DIR_STATIC / "img" / "candidatos"
DIR_PARTIDOS = DIR_STATIC / "img" / "partidos"

HEADERS = {
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
    ),
    "referer": "https://resultadosegundavuelta.onpe.gob.pe/main/resumen",
}


def _descargar(url: str, destino: Path) -> bool:
    """Descarga una imagen si aún no existe localmente.

    Returns:
        True si la imagen está disponible (descargada o ya existente).
    """
    if destino.exists() and destino.stat().st_size > 0:
        return True
    destino.parent.mkdir(parents=True, exist_ok=True)
    try:
        respuesta = requests.get(url, headers=HEADERS, timeout=15)
        respuesta.raise_for_status()
        if "image" not in respuesta.headers.get("content-type", ""):
            return False
        destino.write_bytes(respuesta.content)
        return True
    except requests.RequestException:
        return False


def ruta_candidato(dni: str) -> str:
    """Ruta web (relativa a /static) de la foto de un candidato."""
    return f"img/candidatos/{dni}.png"


def ruta_partido(codigo: int) -> str:
    """Ruta web (relativa a /static) del logo de un partido."""
    return f"img/partidos/{int(codigo):08d}.png"


def asegurar_imagenes(participantes: list[dict]) -> None:
    """Descarga las fotos y logos de una lista de participantes.

    Cada participante debe tener `dni` y `codigo_agrupacion` (o las claves de
    la API `dniCandidato` / `codigoAgrupacionPolitica`).
    """
    for p in participantes:
        dni = str(p.get("dni") or p.get("dniCandidato") or "").strip()
        codigo = p.get("codigo_agrupacion")
        if codigo is None:
            codigo = p.get("codigoAgrupacionPolitica")

        if dni:
            _descargar(
                URL_CANDIDATO.format(dni=dni),
                DIR_CANDIDATOS / f"{dni}.png",
            )
        if codigo is not None:
            _descargar(
                URL_PARTIDO.format(codigo=int(codigo)),
                DIR_PARTIDOS / f"{int(codigo):08d}.png",
            )
