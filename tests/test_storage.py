"""Pruebas para la persistencia en CSV (storage)."""

from src.models import RegistroParticipante, RegistroTotales
from src.storage import (
    guardar_participantes,
    guardar_totales,
    leer_historico_participantes,
    leer_historico_totales,
    leer_ultimos_participantes,
    leer_ultimos_totales,
)


def _totales(fecha_actualizacion: str, votos: int) -> RegistroTotales:
    return RegistroTotales(
        fecha_captura="2026-06-07T10:00:00+00:00",
        fecha_actualizacion=fecha_actualizacion,
        nivel="nacional",
        ubigeo="",
        nombre_ubigeo="PERÚ",
        actas_contabilizadas=40.0,
        contabilizadas=100,
        total_actas=250,
        participacion=30.0,
        votos_emitidos=votos,
        votos_validos=votos,
        enviadas_jee=0,
        pendientes_jee=150,
    )


def _participante(
    fecha_actualizacion: str, dni: str, votos: int
) -> RegistroParticipante:
    return RegistroParticipante(
        fecha_captura="2026-06-07T10:00:00+00:00",
        fecha_actualizacion=fecha_actualizacion,
        nivel="nacional",
        ubigeo="",
        nombre_ubigeo="PERÚ",
        agrupacion="PARTIDO",
        codigo_agrupacion=1,
        candidato="CANDIDATO",
        dni=dni,
        votos_validos=votos,
        pct_validos=50.0,
        pct_emitidos=45.0,
    )


def test_guardar_totales_anexa_filas(tmp_path):
    escritas = guardar_totales([_totales("2026-06-07T09:00:00+00:00", 10)], tmp_path)
    assert escritas == 1
    assert (tmp_path / "resultados_totales.csv").exists()


def test_guardar_totales_dedupe_misma_fecha(tmp_path):
    registro = _totales("2026-06-07T09:00:00+00:00", 10)
    assert guardar_totales([registro], tmp_path) == 1
    # La misma fecha de actualización no debe duplicarse.
    assert guardar_totales([registro], tmp_path) == 0


def test_guardar_totales_nueva_fecha_se_agrega(tmp_path):
    guardar_totales([_totales("2026-06-07T09:00:00+00:00", 10)], tmp_path)
    escritas = guardar_totales([_totales("2026-06-07T10:00:00+00:00", 20)], tmp_path)
    assert escritas == 1


def test_leer_ultimos_totales_toma_la_fecha_mayor(tmp_path):
    guardar_totales([_totales("2026-06-07T09:00:00+00:00", 10)], tmp_path)
    guardar_totales([_totales("2026-06-07T10:00:00+00:00", 20)], tmp_path)
    ultimo = leer_ultimos_totales(tmp_path)
    assert ultimo is not None
    assert ultimo["votos_validos"] == "20"


def test_participantes_dedupe_y_ultimo(tmp_path):
    guardar_participantes(
        [
            _participante("2026-06-07T09:00:00+00:00", "111", 100),
            _participante("2026-06-07T09:00:00+00:00", "222", 80),
        ],
        tmp_path,
    )
    # Repetir misma fecha: no agrega.
    assert (
        guardar_participantes(
            [_participante("2026-06-07T09:00:00+00:00", "111", 100)], tmp_path
        )
        == 0
    )
    # Nueva fecha: agrega.
    guardar_participantes(
        [
            _participante("2026-06-07T10:00:00+00:00", "111", 150),
            _participante("2026-06-07T10:00:00+00:00", "222", 120),
        ],
        tmp_path,
    )
    ultimos = leer_ultimos_participantes(tmp_path)
    assert len(ultimos) == 2
    assert all(f["fecha_actualizacion"] == "2026-06-07T10:00:00+00:00" for f in ultimos)


def test_leer_sin_datos_devuelve_vacio(tmp_path):
    assert leer_ultimos_participantes(tmp_path) == []
    assert leer_ultimos_totales(tmp_path) is None


def test_historico_participantes_toma_ultimos_n(tmp_path):
    for hora in ("09", "10", "11", "12"):
        fecha = f"2026-06-07T{hora}:00:00+00:00"
        guardar_participantes(
            [
                _participante(fecha, "111", 100),
                _participante(fecha, "222", 80),
            ],
            tmp_path,
        )
    historico = leer_historico_participantes(tmp_path, n=3)
    # Solo los 3 más recientes, de más antiguo a más reciente.
    assert [fecha for fecha, _ in historico] == [
        "2026-06-07T10:00:00+00:00",
        "2026-06-07T11:00:00+00:00",
        "2026-06-07T12:00:00+00:00",
    ]
    # Cada snapshot conserva sus dos participantes.
    assert all(len(filas) == 2 for _, filas in historico)


def test_historico_totales_indexado_por_fecha(tmp_path):
    guardar_totales([_totales("2026-06-07T09:00:00+00:00", 10)], tmp_path)
    guardar_totales([_totales("2026-06-07T10:00:00+00:00", 20)], tmp_path)
    historico = leer_historico_totales(tmp_path, n=3)
    assert set(historico.keys()) == {
        "2026-06-07T09:00:00+00:00",
        "2026-06-07T10:00:00+00:00",
    }
    assert historico["2026-06-07T10:00:00+00:00"]["votos_validos"] == "20"


def test_historico_sin_datos_devuelve_vacio(tmp_path):
    assert leer_historico_participantes(tmp_path) == []
    assert leer_historico_totales(tmp_path) == {}
