"""Pruebas del scraper con un cliente ONPE simulado (sin red)."""

from src.scraper import Scraper
from src.storage import leer_ultimos_participantes, leer_ultimos_totales

TOTALES = {
    "actasContabilizadas": 40.0,
    "contabilizadas": 100,
    "totalActas": 250,
    "participacionCiudadana": 30.0,
    "totalVotosEmitidos": 1000,
    "totalVotosValidos": 950,
    "enviadasJee": 0,
    "pendientesJee": 150,
    "fechaActualizacion": 1780884123061,
}

PARTICIPANTES = [
    {
        "nombreAgrupacionPolitica": "JUNTOS POR EL PERÚ",
        "codigoAgrupacionPolitica": 10,
        "nombreCandidato": "ROBERTO SANCHEZ",
        "dniCandidato": "16002918",
        "totalVotosValidos": 500,
        "porcentajeVotosValidos": 52.6,
        "porcentajeVotosEmitidos": 50.0,
    },
    {
        "nombreAgrupacionPolitica": "FUERZA POPULAR",
        "codigoAgrupacionPolitica": 8,
        "nombreCandidato": "KEIKO FUJIMORI",
        "dniCandidato": "10001088",
        "totalVotosValidos": 450,
        "porcentajeVotosValidos": 47.4,
        "porcentajeVotosEmitidos": 45.0,
    },
]


class ClienteFake:
    """Cliente simulado que devuelve datos fijos sin acceder a la red."""

    def obtener_totales(self, *args, **kwargs):
        return dict(TOTALES)

    def obtener_participantes(self, *args, **kwargs):
        return [dict(p) for p in PARTICIPANTES]

    def obtener_departamentos(self):
        return [{"ubigeo": "010000", "nombre": "AMAZONAS"}]

    def obtener_provincias(self, ubigeo_departamento):
        return [{"ubigeo": "010200", "nombre": "BAGUA"}]

    def obtener_distritos(self, ubigeo_provincia):
        return [{"ubigeo": "010201", "nombre": "LA PECA"}]

    def obtener_departamentos_exterior(self):
        return [{"ubigeo": "910000", "nombre": "EUROPA"}]

    def obtener_provincias_exterior(self, ubigeo_departamento):
        return [{"ubigeo": "910100", "nombre": "ESPAÑA"}]


def test_ejecutar_solo_nacional(tmp_path):
    scraper = Scraper(ClienteFake(), tmp_path, nivel_maximo="nacional")
    escritas = scraper.ejecutar()
    # nacional + extranjero + region_exterior + pais = 4 ámbitos.
    # Por ámbito: 1 totales + 2 participantes = 3 filas. Total: 12.
    assert escritas == 12
    participantes = leer_ultimos_participantes(tmp_path)
    assert len(participantes) == 2
    totales = leer_ultimos_totales(tmp_path)
    assert totales is not None
    assert totales["votos_validos"] == "950"


def test_ejecutar_hasta_distrito_recorre_todos_los_niveles(tmp_path):
    scraper = Scraper(ClienteFake(), tmp_path, nivel_maximo="distrito")
    scraper.ejecutar()
    # Nacional + departamento + provincia + distrito = 4 ámbitos nacionales, 2 candidatos c/u.
    # Exterior: extranjero + region_exterior + pais = 3 ámbitos más.
    nacional = leer_ultimos_participantes(tmp_path, "nacional", "")
    departamento = leer_ultimos_participantes(tmp_path, "departamento", "010000")
    provincia = leer_ultimos_participantes(tmp_path, "provincia", "010200")
    distrito = leer_ultimos_participantes(tmp_path, "distrito", "010201")
    extranjero = leer_ultimos_participantes(tmp_path, "extranjero", "")
    pais = leer_ultimos_participantes(tmp_path, "pais", "910100")
    assert len(nacional) == 2
    assert len(departamento) == 2
    assert len(provincia) == 2
    assert len(distrito) == 2
    assert len(extranjero) == 2
    assert len(pais) == 2


def test_segunda_pasada_misma_fecha_no_duplica(tmp_path):
    scraper = Scraper(ClienteFake(), tmp_path, nivel_maximo="nacional")
    scraper.ejecutar()
    escritas = scraper.ejecutar()
    assert escritas == 0
