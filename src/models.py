"""Modelos de datos para los resultados electorales."""

from __future__ import annotations

from dataclasses import dataclass, field

# Niveles geográficos soportados por la API de ONPE.
NIVEL_NACIONAL = "nacional"
NIVEL_DEPARTAMENTO = "departamento"
NIVEL_PROVINCIA = "provincia"
NIVEL_DISTRITO = "distrito"

# Mapeo de nivel interno al valor de `tipoFiltro` que espera la API.
TIPO_FILTRO_POR_NIVEL = {
    NIVEL_NACIONAL: "eleccion",
    NIVEL_DEPARTAMENTO: "ubigeo_nivel_01",
    NIVEL_PROVINCIA: "ubigeo_nivel_02",
    NIVEL_DISTRITO: "ubigeo_nivel_03",
}


@dataclass
class Candidato:
    """Representa a un candidato y sus votos."""

    nombre: str
    partido: str
    votos: int = 0

    def porcentaje(self, total_votos: int) -> float:
        """Devuelve el porcentaje de votos sobre el total de votos válidos."""
        if total_votos <= 0:
            return 0.0
        return round(self.votos / total_votos * 100, 2)


@dataclass
class ResultadosEleccion:
    """Agrupa los resultados de la segunda vuelta."""

    titulo: str
    fecha: str
    candidatos: list[Candidato] = field(default_factory=list)

    @property
    def total_votos(self) -> int:
        """Suma de votos de todos los candidatos."""
        return sum(candidato.votos for candidato in self.candidatos)

    def ordenados_por_votos(self) -> list[Candidato]:
        """Devuelve los candidatos ordenados de mayor a menor cantidad de votos."""
        return sorted(self.candidatos, key=lambda c: c.votos, reverse=True)

    def ganador(self) -> Candidato | None:
        """Devuelve el candidato con más votos, o None si no hay candidatos."""
        ordenados = self.ordenados_por_votos()
        return ordenados[0] if ordenados else None


@dataclass
class RegistroTotales:
    """Totales de actas y votos para un ámbito geográfico (un snapshot)."""

    fecha_captura: str
    fecha_actualizacion: str
    nivel: str
    ubigeo: str
    nombre_ubigeo: str
    actas_contabilizadas: float
    contabilizadas: int
    total_actas: int
    participacion: float
    votos_emitidos: int
    votos_validos: int
    enviadas_jee: int
    pendientes_jee: int

    # Orden de columnas para el CSV de totales.
    CAMPOS = (
        "fecha_captura",
        "fecha_actualizacion",
        "nivel",
        "ubigeo",
        "nombre_ubigeo",
        "actas_contabilizadas",
        "contabilizadas",
        "total_actas",
        "participacion",
        "votos_emitidos",
        "votos_validos",
        "enviadas_jee",
        "pendientes_jee",
    )


@dataclass
class RegistroParticipante:
    """Votos de un candidato/agrupación para un ámbito geográfico (un snapshot)."""

    fecha_captura: str
    fecha_actualizacion: str
    nivel: str
    ubigeo: str
    nombre_ubigeo: str
    agrupacion: str
    codigo_agrupacion: int
    candidato: str
    dni: str
    votos_validos: int
    pct_validos: float
    pct_emitidos: float

    # Orden de columnas para el CSV de participantes.
    CAMPOS = (
        "fecha_captura",
        "fecha_actualizacion",
        "nivel",
        "ubigeo",
        "nombre_ubigeo",
        "agrupacion",
        "codigo_agrupacion",
        "candidato",
        "dni",
        "votos_validos",
        "pct_validos",
        "pct_emitidos",
    )
