"""Cliente HTTP para la API pública de resultados de ONPE."""

from __future__ import annotations

import time

import requests

from .models import NIVELES_EXTERIOR, TIPO_FILTRO_POR_NIVEL

BASE_URL = "https://resultadosegundavuelta.onpe.gob.pe/presentacion-backend"

# Cabeceras mínimas necesarias (las cookies _ga del navegador no se requieren).
# El WAF de ONPE devuelve el HTML del SPA si faltan las cabeceras sec-fetch-*.
HEADERS = {
    "accept": "*/*",
    "accept-language": "es-US,es-419;q=0.9,es;q=0.8",
    "referer": "https://resultadosegundavuelta.onpe.gob.pe/main/resumen",
    "sec-ch-ua": (
        '"Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"'
    ),
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
    ),
}


class OnpeClient:
    """Cliente para consultar los endpoints de resultados de ONPE.

    Maneja una sesión HTTP reutilizable, reintentos básicos, timeout y un
    pequeño retardo entre peticiones para no saturar el servidor.
    """

    def __init__(
        self,
        id_eleccion: int = 10,
        id_ambito_geografico: int = 1,
        timeout: float = 15.0,
        delay: float = 0.2,
        max_reintentos: int = 3,
        base_url: str = BASE_URL,
    ) -> None:
        self.id_eleccion = id_eleccion
        self.id_ambito_geografico = id_ambito_geografico
        self.timeout = timeout
        self.delay = delay
        self.max_reintentos = max_reintentos
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    # ------------------------------------------------------------------
    # Petición genérica
    # ------------------------------------------------------------------
    def _get(self, ruta: str, params: dict) -> object:
        """Realiza una petición GET con reintentos y devuelve el campo `data`."""
        url = f"{self.base_url}/{ruta.lstrip('/')}"
        ultimo_error: Exception | None = None

        for intento in range(1, self.max_reintentos + 1):
            try:
                respuesta = self.session.get(
                    url, params=params, timeout=self.timeout
                )
                respuesta.raise_for_status()
                cuerpo = respuesta.json()
                if self.delay:
                    time.sleep(self.delay)
                if not cuerpo.get("success", False):
                    mensaje = cuerpo.get("message", "respuesta sin éxito")
                    raise ValueError(f"ONPE respondió sin éxito: {mensaje}")
                return cuerpo.get("data")
            except (requests.RequestException, ValueError) as error:
                ultimo_error = error
                if intento < self.max_reintentos:
                    time.sleep(self.delay * intento + 0.5)

        raise RuntimeError(
            f"No se pudo obtener {url} tras {self.max_reintentos} intentos: "
            f"{ultimo_error}"
        )

    # ------------------------------------------------------------------
    # Parámetros de ubigeo según el nivel
    # ------------------------------------------------------------------
    def _params_filtro(
        self,
        nivel: str,
        ubigeo_departamento: str | None = None,
        ubigeo_provincia: str | None = None,
        ubigeo_distrito: str | None = None,
    ) -> dict:
        """Construye los parámetros de filtro para totales/participantes."""
        params: dict[str, object] = {
            "idEleccion": self.id_eleccion,
            "tipoFiltro": TIPO_FILTRO_POR_NIVEL[nivel],
        }
        if nivel in NIVELES_EXTERIOR:
            # El ámbito exterior siempre usa idAmbitoGeografico=2.
            params["idAmbitoGeografico"] = 2
        elif nivel != "nacional":
            params["idAmbitoGeografico"] = self.id_ambito_geografico
        if ubigeo_departamento:
            params["idUbigeoDepartamento"] = ubigeo_departamento
        if ubigeo_provincia:
            params["idUbigeoProvincia"] = ubigeo_provincia
        if ubigeo_distrito:
            params["idUbigeoDistrito"] = ubigeo_distrito
        return params

    # ------------------------------------------------------------------
    # Endpoints de resultados
    # ------------------------------------------------------------------
    def obtener_totales(
        self,
        nivel: str = "nacional",
        ubigeo_departamento: str | None = None,
        ubigeo_provincia: str | None = None,
        ubigeo_distrito: str | None = None,
    ) -> dict:
        """Devuelve los totales de actas/votos para el ámbito indicado."""
        params = self._params_filtro(
            nivel, ubigeo_departamento, ubigeo_provincia, ubigeo_distrito
        )
        return self._get("resumen-general/totales", params)

    def obtener_participantes(
        self,
        nivel: str = "nacional",
        ubigeo_departamento: str | None = None,
        ubigeo_provincia: str | None = None,
        ubigeo_distrito: str | None = None,
    ) -> list[dict]:
        """Devuelve la lista de candidatos/agrupaciones para el ámbito indicado."""
        params = self._params_filtro(
            nivel, ubigeo_departamento, ubigeo_provincia, ubigeo_distrito
        )
        return self._get("resumen-general/participantes", params)

    # ------------------------------------------------------------------
    # Endpoints de ubigeos (catálogos)
    # ------------------------------------------------------------------
    def obtener_departamentos(self) -> list[dict]:
        """Lista los departamentos disponibles."""
        return self._get(
            "ubigeos/departamentos",
            {
                "idEleccion": self.id_eleccion,
                "idAmbitoGeografico": self.id_ambito_geografico,
            },
        )

    def obtener_provincias(self, ubigeo_departamento: str) -> list[dict]:
        """Lista las provincias de un departamento."""
        return self._get(
            "ubigeos/provincias",
            {
                "idEleccion": self.id_eleccion,
                "idAmbitoGeografico": self.id_ambito_geografico,
                "idUbigeoDepartamento": ubigeo_departamento,
            },
        )

    def obtener_distritos(self, ubigeo_provincia: str) -> list[dict]:
        """Lista los distritos de una provincia."""
        return self._get(
            "ubigeos/distritos",
            {
                "idEleccion": self.id_eleccion,
                "idAmbitoGeografico": self.id_ambito_geografico,
                "idUbigeoProvincia": ubigeo_provincia,
            },
        )

    def obtener_departamentos_exterior(self) -> list[dict]:
        """Lista las regiones del exterior (idAmbitoGeografico=2)."""
        return self._get(
            "ubigeos/departamentos",
            {
                "idEleccion": self.id_eleccion,
                "idAmbitoGeografico": 2,
            },
        )

    def obtener_provincias_exterior(self, ubigeo_departamento: str) -> list[dict]:
        """Lista los países de una región exterior."""
        return self._get(
            "ubigeos/provincias",
            {
                "idEleccion": self.id_eleccion,
                "idAmbitoGeografico": 2,
                "idUbigeoDepartamento": ubigeo_departamento,
            },
        )

    def cerrar(self) -> None:
        """Cierra la sesión HTTP."""
        self.session.close()
