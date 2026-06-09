"""Aplicación web (Flask) para visualizar los resultados de ONPE.

Sirve una página dinámica que muestra el resultado general (nacional) y el
detalle por región, consumiendo los CSV históricos generados por el scraper.
"""

from __future__ import annotations

import functools
import hashlib
import os
import re
import threading
import time
from pathlib import Path

from flask import Flask, abort, jsonify, render_template
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
from werkzeug.middleware.proxy_fix import ProxyFix

from .imagenes import ruta_candidato, ruta_partido
from .onpe_client import OnpeClient
from .scraper import Scraper
from .storage import (
    leer_historico_participantes,
    leer_historico_totales,
    leer_ultimos_participantes,
    leer_ultimos_totales,
    listar_ambitos,
)

DIRECTORIO_DATOS = Path(__file__).resolve().parent.parent / "data"

# Formato válido de ubigeo: solo dígitos (2 a 6) para evitar entradas maliciosas.
_UBIGEO_VALIDO = re.compile(r"^\d{2,6}$")


def _bool_env(nombre: str, defecto: bool = False) -> bool:
    """Lee una variable de entorno booleana ("1"/"true"/"yes")."""
    valor = os.environ.get(nombre)
    if valor is None:
        return defecto
    return valor.strip().lower() in {"1", "true", "yes", "on"}


app = Flask(__name__)

# Hash corto basado en el momento de inicio del proceso: invalida el caché del
# navegador para CSS/JS en cada nuevo deploy, sin afectar la URL canónica.
_STATIC_VERSION = hashlib.md5(str(time.time()).encode()).hexdigest()[:8]


@app.context_processor
def _inyectar_version():
    return {"static_v": _STATIC_VERSION}


# Límites de tamaño y caché de archivos estáticos.
# - MAX_CONTENT_LENGTH: rechaza cuerpos de petición grandes (no usamos POST, así
#   que cualquier payload voluminoso es abuso). Protección barata contra floods.
# - SEND_FILE_MAX_AGE_DEFAULT: deja que el navegador/CDN cacheen CSS/JS/imágenes
#   1 día, reduciendo peticiones repetidas al origen.
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024  # 32 KB
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 86400  # 1 día

# Detrás del proxy del PaaS: confiar en X-Forwarded-* para IP y esquema reales
# (necesario para el rate limiting por IP y la detección de HTTPS).
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

# Cabeceras de seguridad + Content Security Policy.
# Nota: la UI genera estilos inline dinámicos (donuts conic-gradient, colores de
# partido), por eso style-src permite 'unsafe-inline'. Los scripts son externos
# (app.js), así que script-src se mantiene estricto.
_CSP = {
    "default-src": "'self'",
    "script-src": "'self'",
    "style-src": "'self' 'unsafe-inline'",
    "img-src": "'self' data:",
    "font-src": "'self'",
    "connect-src": "'self'",
    "base-uri": "'self'",
    "frame-ancestors": "'none'",
    "object-src": "'none'",
}
_FORCE_HTTPS = _bool_env("FORCE_HTTPS", False)
Talisman(
    app,
    content_security_policy=_CSP,
    force_https=_FORCE_HTTPS,
    strict_transport_security=_FORCE_HTTPS,
    frame_options="DENY",
    referrer_policy="strict-origin-when-cross-origin",
)

# Límite de peticiones por IP para mitigar abuso/DoS.
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["120 per minute"],
    storage_uri="memory://",
)


# --- Caché de respuestas en memoria con TTL ---
# Los datos solo cambian cuando el recolector trae filas nuevas (cada minuto o
# más). Cachear las respuestas JSON unos segundos hace que un aluvión de
# peticiones sea barato: en lugar de leer disco y recalcular en cada request, se
# sirve la copia ya construida. Es la defensa más efectiva (junto a un CDN) ante
# un script que intente tumbar la web a base de peticiones.
_CACHE_TTL = float(os.environ.get("CACHE_TTL", "20"))
_CACHE_MAX = 256  # tope de entradas para que la caché no crezca sin límite
_cache_store: dict[str, tuple[float, bytes, str]] = {}
_cache_lock = threading.Lock()


def _podar_cache(ahora: float, ttl: float) -> None:
    """Elimina entradas caducadas y, si aún se excede el tope, las más viejas.

    Evita que pedir muchos ubigeos distintos infle la memoria sin control.
    Debe llamarse con `_cache_lock` tomado.
    """
    if len(_cache_store) < _CACHE_MAX:
        return
    caducadas = [k for k, (t, _, _) in _cache_store.items() if ahora - t >= ttl]
    for k in caducadas:
        _cache_store.pop(k, None)
    if len(_cache_store) >= _CACHE_MAX:
        # Aún lleno: descartar la entrada más antigua.
        mas_vieja = min(_cache_store, key=lambda k: _cache_store[k][0])
        _cache_store.pop(mas_vieja, None)


def cache_respuesta(ttl: float = _CACHE_TTL):
    """Cachea la respuesta JSON de una vista durante `ttl` segundos.

    Añade además la cabecera Cache-Control para que navegadores y CDN puedan
    reutilizar la respuesta sin volver a tocar el servidor.
    """

    def decorador(fn):
        @functools.wraps(fn)
        def envoltorio(*args, **kwargs):
            partes = [str(a) for a in args]
            partes += [f"{k}={v}" for k, v in sorted(kwargs.items())]
            clave = f"{fn.__name__}:" + ":".join(partes)
            ahora = time.monotonic()
            with _cache_lock:
                entrada = _cache_store.get(clave)
                if entrada and (ahora - entrada[0]) < ttl:
                    _, datos, mimetype = entrada
                    resp = app.response_class(datos, mimetype=mimetype)
                    resp.headers["Cache-Control"] = f"public, max-age={int(ttl)}"
                    resp.headers["X-Cache"] = "HIT"
                    return resp

            resultado = fn(*args, **kwargs)
            datos = resultado.get_data()
            with _cache_lock:
                _podar_cache(ahora, ttl)
                _cache_store[clave] = (ahora, datos, resultado.mimetype)
            resultado.headers["Cache-Control"] = f"public, max-age={int(ttl)}"
            resultado.headers["X-Cache"] = "MISS"
            return resultado

        return envoltorio

    return decorador


@app.errorhandler(404)
def _no_encontrado(_error):
    """404 en JSON, sin filtrar detalles internos."""
    return jsonify(error="No encontrado"), 404


@app.errorhandler(429)
def _demasiadas_peticiones(_error):
    """429 cuando se supera el rate limit."""
    return jsonify(error="Demasiadas peticiones. Inténtalo en un momento."), 429


@app.errorhandler(413)
def _payload_grande(_error):
    """413 cuando el cuerpo de la petición excede el límite permitido."""
    return jsonify(error="Petición demasiado grande"), 413



def _num(valor: object, defecto: float = 0.0) -> float:
    """Convierte a float de forma segura."""
    try:
        return float(valor)
    except (TypeError, ValueError):
        return defecto


def _participantes_formateados(nivel: str, ubigeo: str) -> list[dict]:
    """Devuelve los participantes ordenados por votos para un ámbito."""
    filas = leer_ultimos_participantes(DIRECTORIO_DATOS, nivel, ubigeo)
    participantes = [
        {
            "candidato": f["candidato"],
            "agrupacion": f["agrupacion"],
            "codigo": int(_num(f["codigo_agrupacion"])),
            "votos": int(_num(f["votos_validos"])),
            "pct_validos": _num(f["pct_validos"]),
            "pct_emitidos": _num(f["pct_emitidos"]),
            "foto": ruta_candidato(f["dni"]),
            "logo": ruta_partido(int(_num(f["codigo_agrupacion"]))),
        }
        for f in filas
    ]
    participantes.sort(key=lambda p: p["votos"], reverse=True)
    return participantes


def _totales_formateados(nivel: str, ubigeo: str) -> dict | None:
    """Devuelve los totales de actas/participación para un ámbito."""
    totales = leer_ultimos_totales(DIRECTORIO_DATOS, nivel, ubigeo)
    if not totales:
        return None
    return {
        "nombre": totales["nombre_ubigeo"],
        "fecha_actualizacion": totales["fecha_actualizacion"],
        "actas_contabilizadas": _num(totales["actas_contabilizadas"]),
        "participacion": _num(totales["participacion"]),
        "votos_validos": int(_num(totales["votos_validos"])),
        "votos_emitidos": int(_num(totales["votos_emitidos"])),
        "total_actas": int(_num(totales["total_actas"])),
        "contabilizadas": int(_num(totales["contabilizadas"])),
    }


def _resultado(nivel: str, ubigeo: str, nombre_defecto: str) -> dict:
    """Empaqueta totales + participantes de un ámbito."""
    totales = _totales_formateados(nivel, ubigeo)
    participantes = _participantes_formateados(nivel, ubigeo)
    nombre = totales["nombre"] if totales else nombre_defecto
    return {
        "nivel": nivel,
        "ubigeo": ubigeo,
        "nombre": nombre,
        "totales": totales,
        "participantes": participantes,
    }


def _tendencia(nivel: str, ubigeo: str, n: int = 3) -> list[dict]:
    """Calcula cómo evoluciona la diferencia entre los dos primeros candidatos.

    Devuelve hasta `n` snapshots (de más antiguo a más reciente), cada uno con la
    fecha, el avance de actas, el líder y la diferencia en puntos porcentuales.
    También incluye la variación de la diferencia respecto al snapshot anterior.
    """
    historico = leer_historico_participantes(DIRECTORIO_DATOS, nivel, ubigeo, n)
    totales_por_fecha = leer_historico_totales(DIRECTORIO_DATOS, nivel, ubigeo, n)

    puntos: list[dict] = []
    for fecha, filas in historico:
        participantes = sorted(
            (
                {
                    "candidato": f["candidato"],
                    "agrupacion": f["agrupacion"],
                    "codigo": int(_num(f["codigo_agrupacion"])),
                    "votos": int(_num(f["votos_validos"])),
                    "pct_validos": _num(f["pct_validos"]),
                }
                for f in filas
            ),
            key=lambda p: p["votos"],
            reverse=True,
        )
        if len(participantes) < 2:
            continue
        lider, segundo = participantes[0], participantes[1]
        diferencia = round(lider["pct_validos"] - segundo["pct_validos"], 3)
        tot = totales_por_fecha.get(fecha)
        puntos.append(
            {
                "fecha_actualizacion": fecha,
                "actas_contabilizadas": _num(tot["actas_contabilizadas"]) if tot else 0,
                "lider_candidato": lider["candidato"],
                "lider_agrupacion": lider["agrupacion"],
                "lider_codigo": lider["codigo"],
                "lider_pct": lider["pct_validos"],
                "segundo_pct": segundo["pct_validos"],
                "diferencia": diferencia,
                "votos_lider": lider["votos"],
                "votos_segundo": segundo["votos"],
            }
        )

    # Variación de la diferencia respecto al punto anterior.
    for i, punto in enumerate(puntos):
        if i == 0:
            punto["variacion"] = None
        else:
            punto["variacion"] = round(
                punto["diferencia"] - puntos[i - 1]["diferencia"], 3
            )
    return puntos


@app.route("/")
def index():
    """Página principal."""
    return render_template("index.html")


@app.route("/api/general")
@cache_respuesta()
def api_general():
    """Resultado general (nacional) con la tendencia de los últimos snapshots."""
    data = _resultado("nacional", "", "PERÚ")
    data["tendencia"] = _tendencia("nacional", "", 3)
    return jsonify(data)


@app.route("/api/regiones")
@limiter.limit("30 per minute")
@cache_respuesta()
def api_regiones():
    """Resultados de todas las regiones (departamentos) para el grid."""
    regiones = []
    for ambito in listar_ambitos(DIRECTORIO_DATOS, "departamento"):
        regiones.append(
            _resultado("departamento", ambito["ubigeo"], ambito["nombre_ubigeo"])
        )
    # Ordenar por nombre para una lectura predecible.
    regiones.sort(key=lambda r: r["nombre"])
    return jsonify(regiones)


@app.route("/api/region/<ubigeo>")
@cache_respuesta()
def api_region(ubigeo: str):
    """Detalle de una región (departamento)."""
    if not _UBIGEO_VALIDO.match(ubigeo):
        abort(404)
    return jsonify(_resultado("departamento", ubigeo, ubigeo))


@app.route("/api/exterior")
@cache_respuesta()
def api_exterior():
    """Resultado total del voto exterior con tendencia."""
    data = _resultado("extranjero", "", "EXTRANJERO")
    data["tendencia"] = _tendencia("extranjero", "", 3)
    return jsonify(data)


@app.route("/api/exterior/regiones")
@limiter.limit("30 per minute")
@cache_respuesta()
def api_exterior_regiones():
    """Lista de regiones del exterior (Europa, Américas, etc.) para el grid."""
    regiones = []
    for ambito in listar_ambitos(DIRECTORIO_DATOS, "region_exterior"):
        regiones.append(
            _resultado("region_exterior", ambito["ubigeo"], ambito["nombre_ubigeo"])
        )
    regiones.sort(key=lambda r: r["nombre"])
    return jsonify(regiones)


@app.route("/api/exterior/region/<ubigeo>")
@cache_respuesta()
def api_exterior_region(ubigeo: str):
    """Detalle de una región exterior (con sus países)."""
    if not _UBIGEO_VALIDO.match(ubigeo):
        abort(404)
    return jsonify(_resultado("region_exterior", ubigeo, ubigeo))


@app.route("/api/exterior/paises")
@limiter.limit("30 per minute")
@cache_respuesta()
def api_exterior_paises():
    """Lista de todos los países del exterior para el grid."""
    paises = []
    for ambito in listar_ambitos(DIRECTORIO_DATOS, "pais"):
        paises.append(
            _resultado("pais", ambito["ubigeo"], ambito["nombre_ubigeo"])
        )
    paises.sort(key=lambda r: r["nombre"])
    return jsonify(paises)


@app.route("/api/resumen")
@limiter.limit("30 per minute")
@cache_respuesta()
def api_resumen():
    """Resumen agregado por regiones: en cuántas gana cada candidato y más."""
    regiones = [
        _resultado("departamento", a["ubigeo"], a["nombre_ubigeo"])
        for a in listar_ambitos(DIRECTORIO_DATOS, "departamento")
    ]

    # Acumuladores por candidato (clave = dni o nombre).
    candidatos: dict[str, dict] = {}
    regiones_contadas = 0

    for region in regiones:
        participantes = region["participantes"]
        if not participantes:
            continue
        # Ignorar regiones sin actas contabilizadas
        totales_r = region.get("totales") or {}
        if not totales_r.get("contabilizadas", 0):
            continue
        regiones_contadas += 1
        lider = participantes[0]

        for p in participantes:
            clave = p["candidato"]
            acc = candidatos.setdefault(
                clave,
                {
                    "candidato": p["candidato"],
                    "agrupacion": p["agrupacion"],
                    "codigo": p["codigo"],
                    "foto": p["foto"],
                    "logo": p["logo"],
                    "regiones_ganadas": 0,
                    "votos": 0,
                    "bastion": None,
                },
            )
            acc["votos"] += p["votos"]
            # Bastión: región donde el candidato saca su mayor porcentaje.
            if acc["bastion"] is None or p["pct_validos"] > acc["bastion"]["pct"]:
                acc["bastion"] = {
                    "nombre": region["nombre"],
                    "pct": p["pct_validos"],
                }
            if p is lider:
                acc["regiones_ganadas"] += 1

    # Margen del líder por región.
    margenes = []
    for region in regiones:
        p = region["participantes"]
        if len(p) >= 2:
            margenes.append(
                {
                    "nombre": region["nombre"],
                    "ganador": p[0]["candidato"],
                    "agrupacion": p[0]["agrupacion"],
                    "codigo": p[0]["codigo"],
                    "diferencia": round(p[0]["pct_validos"] - p[1]["pct_validos"], 2),
                }
            )

    mas_ajustada = min(margenes, key=lambda m: m["diferencia"], default=None)
    mas_holgada = max(margenes, key=lambda m: m["diferencia"], default=None)
    ventaja_promedio = (
        round(sum(m["diferencia"] for m in margenes) / len(margenes), 2)
        if margenes
        else 0
    )

    # Mayor participación entre regiones.
    participaciones = [
        {
            "nombre": r["nombre"],
            "participacion": r["totales"]["participacion"],
        }
        for r in regiones
        if r["totales"]
    ]
    mayor_participacion = max(
        participaciones, key=lambda x: x["participacion"], default=None
    )

    resumen_candidatos = sorted(
        candidatos.values(),
        key=lambda c: c["regiones_ganadas"],
        reverse=True,
    )

    # Votos totales agregados (todas las regiones) para repartir el dominio.
    votos_totales = sum(c["votos"] for c in resumen_candidatos)
    for c in resumen_candidatos:
        c["pct_votos"] = (
            round(c["votos"] / votos_totales * 100, 2) if votos_totales else 0
        )

    # Actas faltantes por región (departamentos nacionales).
    actas_faltantes_regiones = []
    for r in regiones:
        t = r["totales"]
        if not t:
            continue
        pendientes = t["total_actas"] - t["contabilizadas"]
        actas_faltantes_regiones.append({
            "nombre": r["nombre"],
            "contabilizadas": t["contabilizadas"],
            "total_actas": t["total_actas"],
            "pendientes": pendientes,
            "pct_contabilizadas": t["actas_contabilizadas"],
        })
    actas_faltantes_regiones.sort(key=lambda x: x["pendientes"], reverse=True)

    # Actas faltantes por país (exterior).
    actas_faltantes_paises = []
    for ambito in listar_ambitos(DIRECTORIO_DATOS, "pais"):
        t = _totales_formateados("pais", ambito["ubigeo"])
        if not t:
            continue
        pendientes = t["total_actas"] - t["contabilizadas"]
        actas_faltantes_paises.append({
            "nombre": t["nombre"],
            "ubigeo": ambito["ubigeo"],
            "contabilizadas": t["contabilizadas"],
            "total_actas": t["total_actas"],
            "pendientes": pendientes,
            "pct_contabilizadas": t["actas_contabilizadas"],
        })
    actas_faltantes_paises.sort(key=lambda x: x["pendientes"], reverse=True)

    # Resumen por países (exterior): cuántos países gana cada candidato.
    paises_data = [
        _resultado("pais", a["ubigeo"], a["nombre_ubigeo"])
        for a in listar_ambitos(DIRECTORIO_DATOS, "pais")
    ]
    paises_candidatos: dict[str, dict] = {}
    paises_contados = 0
    for pais in paises_data:
        participantes = pais["participantes"]
        if not participantes:
            continue
        # Ignorar países sin actas contabilizadas
        totales_p = pais.get("totales") or {}
        if not totales_p.get("contabilizadas", 0):
            continue
        paises_contados += 1
        lider = participantes[0]
        for p in participantes:
            clave = p["candidato"]
            acc = paises_candidatos.setdefault(
                clave,
                {
                    "candidato": p["candidato"],
                    "agrupacion": p["agrupacion"],
                    "codigo": p["codigo"],
                    "foto": p["foto"],
                    "logo": p["logo"],
                    "paises_ganados": 0,
                    "votos": 0,
                    "bastion": None,
                },
            )
            acc["votos"] += p["votos"]
            if acc["bastion"] is None or p["pct_validos"] > acc["bastion"]["pct"]:
                acc["bastion"] = {"nombre": pais["nombre"], "pct": p["pct_validos"]}
            if p is lider:
                acc["paises_ganados"] += 1

    resumen_candidatos_paises = sorted(
        paises_candidatos.values(),
        key=lambda c: c["paises_ganados"],
        reverse=True,
    )
    votos_totales_paises = sum(c["votos"] for c in resumen_candidatos_paises)
    for c in resumen_candidatos_paises:
        c["pct_votos"] = (
            round(c["votos"] / votos_totales_paises * 100, 2) if votos_totales_paises else 0
        )

    return jsonify(
        {
            "total_regiones": regiones_contadas,
            "candidatos": resumen_candidatos,
            "mas_ajustada": mas_ajustada,
            "mas_holgada": mas_holgada,
            "ventaja_promedio": ventaja_promedio,
            "mayor_participacion": mayor_participacion,
            "actas_faltantes_regiones": actas_faltantes_regiones,
            "actas_faltantes_paises": actas_faltantes_paises,
            "total_paises": paises_contados,
            "candidatos_paises": resumen_candidatos_paises,
        }
    )


# Estado del recolector en segundo plano (para mostrarlo en la web).
_estado = {"ultima_recoleccion": None, "ultimo_error": None, "filas_nuevas": 0}


@app.route("/health")
def health():
    """Endpoint mínimo para monitores de uptime (UptimeRobot, etc.).

    No lee disco ni hace cálculos: responde 200 inmediatamente para mantener
    el servicio despierto en Render free tier. Configura el monitor externo
    para hacer ping a /health cada 5 minutos.
    """
    return "", 200


@app.route("/api/estado")
def api_estado():
    """Estado del recolector automático en segundo plano."""
    return jsonify(_estado)


def _bucle_recoleccion(intervalo: float, nivel_maximo: str) -> None:
    """Hilo de fondo que trae datos de ONPE cada `intervalo` segundos."""
    cliente = OnpeClient()
    scraper = Scraper(cliente, DIRECTORIO_DATOS, nivel_maximo=nivel_maximo)
    while True:
        try:
            nuevas = scraper.ejecutar()
            _estado["filas_nuevas"] = nuevas
            _estado["ultima_recoleccion"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            _estado["ultimo_error"] = None
            print(
                f"[recolector] {_estado['ultima_recoleccion']} "
                f"+{nuevas} filas nuevas",
                flush=True,
            )
        except Exception as error:  # noqa: BLE001
            _estado["ultimo_error"] = str(error)
            print(f"[recolector] error: {error}", flush=True)
        time.sleep(intervalo)


def iniciar_recolector(intervalo: float, nivel_maximo: str) -> None:
    """Lanza el recolector en un hilo daemon (una sola vez)."""
    hilo = threading.Thread(
        target=_bucle_recoleccion,
        args=(intervalo, nivel_maximo),
        daemon=True,
    )
    hilo.start()


# Arranque del recolector a nivel de módulo para entornos WSGI (gunicorn), que
# importan `src.web:app` y nunca ejecutan main(). Se activa solo si
# ONPE_RECOLECTOR=1. Con gunicorn --workers 1 no se duplica el hilo.
if _bool_env("ONPE_RECOLECTOR", False):
    iniciar_recolector(
        float(os.environ.get("ONPE_INTERVALO", "180")),
        os.environ.get("ONPE_NIVEL_MAXIMO", "departamento"),
    )


def main() -> None:
    """Inicia el servidor web y el recolector automático (modo desarrollo local).

    En producción se usa un servidor WSGI (gunicorn) que importa `app`; el
    recolector se arranca con la variable de entorno ONPE_RECOLECTOR=1.
    """
    debug = _bool_env("FLASK_DEBUG", False)
    intervalo = float(os.environ.get("ONPE_INTERVALO", "60"))
    nivel_maximo = os.environ.get("ONPE_NIVEL_MAXIMO", "departamento")

    # Evitar doble arranque: si ya se inició a nivel de módulo, no repetir.
    ya_iniciado = _bool_env("ONPE_RECOLECTOR", False)
    # Con el reloader de Flask activo, solo el proceso hijo debe recolectar.
    if not ya_iniciado and (not debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true"):
        iniciar_recolector(intervalo, nivel_maximo)

    app.run(host="127.0.0.1", port=5000, debug=debug)


if __name__ == "__main__":
    main()
