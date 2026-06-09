"""Recorrido de los niveles geográficos de ONPE y armado de snapshots."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .models import (
    NIVEL_DEPARTAMENTO,
    NIVEL_DISTRITO,
    NIVEL_EXTRANJERO,
    NIVEL_EXTRANJERO_REGION,
    NIVEL_NACIONAL,
    NIVEL_PAIS,
    NIVEL_PROVINCIA,
    RegistroParticipante,
    RegistroTotales,
)
from .imagenes import asegurar_imagenes
from .onpe_client import OnpeClient
from .storage import guardar_participantes, guardar_totales

# Orden de profundidad de los niveles.
ORDEN_NIVELES = [
    NIVEL_NACIONAL,
    NIVEL_DEPARTAMENTO,
    NIVEL_PROVINCIA,
    NIVEL_DISTRITO,
]


def _ahora_iso() -> str:
    """Marca de tiempo de la captura, en ISO 8601 (UTC)."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _fecha_actualizacion(totales: dict) -> str:
    """Convierte el epoch en ms de ONPE a ISO 8601, o cadena vacía."""
    epoch_ms = totales.get("fechaActualizacion")
    if not epoch_ms:
        return ""
    return datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc).isoformat(
        timespec="seconds"
    )


def _registro_totales(
    totales: dict,
    fecha_captura: str,
    nivel: str,
    ubigeo: str,
    nombre_ubigeo: str,
) -> RegistroTotales:
    """Construye un RegistroTotales a partir de la respuesta de la API."""
    return RegistroTotales(
        fecha_captura=fecha_captura,
        fecha_actualizacion=_fecha_actualizacion(totales),
        nivel=nivel,
        ubigeo=ubigeo,
        nombre_ubigeo=nombre_ubigeo,
        actas_contabilizadas=totales.get("actasContabilizadas", 0),
        contabilizadas=totales.get("contabilizadas", 0),
        total_actas=totales.get("totalActas", 0),
        participacion=totales.get("participacionCiudadana", 0),
        votos_emitidos=totales.get("totalVotosEmitidos", 0),
        votos_validos=totales.get("totalVotosValidos", 0),
        enviadas_jee=totales.get("enviadasJee", 0),
        pendientes_jee=totales.get("pendientesJee", 0),
    )


def _registros_participantes(
    participantes: list[dict],
    fecha_captura: str,
    fecha_actualizacion: str,
    nivel: str,
    ubigeo: str,
    nombre_ubigeo: str,
) -> list[RegistroParticipante]:
    """Construye RegistroParticipante por cada candidato de la respuesta."""
    return [
        RegistroParticipante(
            fecha_captura=fecha_captura,
            fecha_actualizacion=fecha_actualizacion,
            nivel=nivel,
            ubigeo=ubigeo,
            nombre_ubigeo=nombre_ubigeo,
            agrupacion=p.get("nombreAgrupacionPolitica", ""),
            codigo_agrupacion=p.get("codigoAgrupacionPolitica", 0),
            candidato=p.get("nombreCandidato", ""),
            dni=str(p.get("dniCandidato", "")),
            votos_validos=p.get("totalVotosValidos", 0),
            pct_validos=p.get("porcentajeVotosValidos", 0),
            pct_emitidos=p.get("porcentajeVotosEmitidos", 0),
        )
        for p in participantes
    ]


class Scraper:
    """Orquesta la descarga de resultados en todos los niveles solicitados."""

    def __init__(
        self,
        cliente: OnpeClient,
        directorio_datos: str | Path,
        nivel_maximo: str = NIVEL_DISTRITO,
    ) -> None:
        self.cliente = cliente
        self.directorio = Path(directorio_datos)
        if nivel_maximo not in ORDEN_NIVELES:
            raise ValueError(f"Nivel desconocido: {nivel_maximo}")
        self.profundidad = ORDEN_NIVELES.index(nivel_maximo)

    def _alcanza(self, nivel: str) -> bool:
        """Indica si se debe descender hasta el nivel dado."""
        return ORDEN_NIVELES.index(nivel) <= self.profundidad

    def _capturar_ambito(
        self,
        fecha_captura: str,
        nivel: str,
        ubigeo: str,
        nombre_ubigeo: str,
        ubigeo_departamento: str | None = None,
        ubigeo_provincia: str | None = None,
        ubigeo_distrito: str | None = None,
    ) -> int:
        """Descarga y guarda totales + participantes de un ámbito.

        Returns:
            Cantidad de filas nuevas escritas (totales + participantes).
        """
        totales = self.cliente.obtener_totales(
            nivel,
            ubigeo_departamento=ubigeo_departamento,
            ubigeo_provincia=ubigeo_provincia,
            ubigeo_distrito=ubigeo_distrito,
        )
        participantes = self.cliente.obtener_participantes(
            nivel,
            ubigeo_departamento=ubigeo_departamento,
            ubigeo_provincia=ubigeo_provincia,
            ubigeo_distrito=ubigeo_distrito,
        )

        # Descarga (cachea) fotos de candidatos y logos de partidos.
        asegurar_imagenes(participantes)

        reg_totales = _registro_totales(
            totales, fecha_captura, nivel, ubigeo, nombre_ubigeo
        )
        reg_participantes = _registros_participantes(
            participantes,
            fecha_captura,
            reg_totales.fecha_actualizacion,
            nivel,
            ubigeo,
            nombre_ubigeo,
        )

        escritas = guardar_totales([reg_totales], self.directorio)
        escritas += guardar_participantes(reg_participantes, self.directorio)
        return escritas

    def ejecutar(self) -> int:
        """Realiza una pasada completa según la profundidad configurada.

        Returns:
            Total de filas nuevas escritas en esta pasada.
        """
        fecha_captura = _ahora_iso()
        escritas = 0

        # Nivel nacional.
        escritas += self._capturar_ambito(
            fecha_captura, NIVEL_NACIONAL, "", "PERÚ"
        )
        if self._alcanza(NIVEL_DEPARTAMENTO):
            for depto in self.cliente.obtener_departamentos():
                ubigeo_dep = depto["ubigeo"]
                escritas += self._capturar_ambito(
                    fecha_captura,
                    NIVEL_DEPARTAMENTO,
                    ubigeo_dep,
                    depto["nombre"],
                    ubigeo_departamento=ubigeo_dep,
                )
                if not self._alcanza(NIVEL_PROVINCIA):
                    continue

                for prov in self.cliente.obtener_provincias(ubigeo_dep):
                    ubigeo_prov = prov["ubigeo"]
                    escritas += self._capturar_ambito(
                        fecha_captura,
                        NIVEL_PROVINCIA,
                        ubigeo_prov,
                        prov["nombre"],
                        ubigeo_departamento=ubigeo_dep,
                        ubigeo_provincia=ubigeo_prov,
                    )
                    if not self._alcanza(NIVEL_DISTRITO):
                        continue

                    for dist in self.cliente.obtener_distritos(ubigeo_prov):
                        ubigeo_dist = dist["ubigeo"]
                        escritas += self._capturar_ambito(
                            fecha_captura,
                            NIVEL_DISTRITO,
                            ubigeo_dist,
                            dist["nombre"],
                            ubigeo_departamento=ubigeo_dep,
                            ubigeo_provincia=ubigeo_prov,
                            ubigeo_distrito=ubigeo_dist,
                        )

        # Ámbito exterior (siempre se traversa hasta países).
        escritas += self._capturar_ambito(
            fecha_captura, NIVEL_EXTRANJERO, "", "EXTRANJERO"
        )
        for reg in self.cliente.obtener_departamentos_exterior():
            ubigeo_reg = reg["ubigeo"]
            escritas += self._capturar_ambito(
                fecha_captura,
                NIVEL_EXTRANJERO_REGION,
                ubigeo_reg,
                reg["nombre"],
                ubigeo_departamento=ubigeo_reg,
            )
            for pais in self.cliente.obtener_provincias_exterior(ubigeo_reg):
                ubigeo_pais = pais["ubigeo"]
                escritas += self._capturar_ambito(
                    fecha_captura,
                    NIVEL_PAIS,
                    ubigeo_pais,
                    pais["nombre"],
                    ubigeo_departamento=ubigeo_reg,
                    ubigeo_provincia=ubigeo_pais,
                )

        return escritas
