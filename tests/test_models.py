"""Pruebas unitarias para los modelos de datos."""

from src.models import Candidato, ResultadosEleccion


def test_porcentaje_calcula_correctamente():
    candidato = Candidato(nombre="Test", partido="P", votos=50)
    assert candidato.porcentaje(100) == 50.0


def test_porcentaje_con_total_cero():
    candidato = Candidato(nombre="Test", partido="P", votos=10)
    assert candidato.porcentaje(0) == 0.0


def test_total_votos():
    resultados = ResultadosEleccion(
        titulo="Test",
        fecha="2026-06-07",
        candidatos=[
            Candidato("A", "PA", 60),
            Candidato("B", "PB", 40),
        ],
    )
    assert resultados.total_votos == 100


def test_ganador_es_el_de_mas_votos():
    resultados = ResultadosEleccion(
        titulo="Test",
        fecha="2026-06-07",
        candidatos=[
            Candidato("A", "PA", 40),
            Candidato("B", "PB", 60),
        ],
    )
    ganador = resultados.ganador()
    assert ganador is not None
    assert ganador.nombre == "B"


def test_ganador_sin_candidatos():
    resultados = ResultadosEleccion(titulo="Test", fecha="2026-06-07")
    assert resultados.ganador() is None
