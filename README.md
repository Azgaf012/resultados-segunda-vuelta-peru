# Resultados Segunda Vuelta - Perú

Proyecto en Python que obtiene mediante web scraping los resultados de la segunda
vuelta electoral presidencial de Perú desde la API pública de la ONPE, los guarda
en CSV histórico y muestra siempre el snapshot más reciente en consola.

## Características

- Descarga de resultados desde la API REST de ONPE (todos los niveles geográficos:
  nacional, departamentos, provincias y distritos).
- Almacenamiento en CSV histórico con deduplicación por fecha de actualización: los
  datos se van agregando conforme la ONPE actualiza el conteo.
- Visualización del resultado más actualizado en consola con tablas (`rich`).
- Página web dinámica (Flask) con el resultado general y el detalle por región,
  con gráficos de dona, resumen y auto-refresco.
- Apta para producción: servidor WSGI (gunicorn), cabeceras de seguridad + CSP,
  límite de peticiones por IP y validación de entrada.
- Ejecución en bucle continuo con intervalo configurable.

## Estructura del proyecto

```
resultados-segunda-vuelta-peru/
├── data/
│   ├── resultados_totales.csv         # Histórico de actas/votos por ámbito
│   └── resultados_participantes.csv   # Histórico de votos por candidato/ámbito
├── src/
│   ├── __init__.py
│   ├── models.py              # Modelos de datos y niveles geográficos
│   ├── onpe_client.py         # Cliente HTTP de la API de ONPE
│   ├── scraper.py             # Recorrido de niveles y armado de snapshots
│   ├── storage.py             # Persistencia CSV (append + dedupe)
│   ├── web.py                 # Servidor web Flask (API + página)
│   ├── templates/             # Plantillas HTML de la web
│   ├── static/                # CSS y JS de la web
│   ├── data_loader.py         # Carga desde JSON (legado)
│   └── display.py             # Presentación de resultados en consola
├── tests/
│   └── test_models.py         # Pruebas unitarias
├── main.py                    # Punto de entrada (bucle de recolección)
├── requirements.txt           # Dependencias del proyecto
├── Procfile                   # Comando de inicio en producción (gunicorn)
├── render.yaml                # Infraestructura como código (Render)
├── .env.example               # Plantilla de variables de entorno
├── .gitignore
└── README.md
```

## Requisitos

- Python 3.10 o superior

## Instalación

1. Crear un entorno virtual:

   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   ```

2. Instalar las dependencias:

   ```powershell
   pip install -r requirements.txt
   ```

## Uso

Recolección continua (por defecto baja hasta departamento/región, cada 5 minutos):

```powershell
python main.py
```

Opciones útiles:

```powershell
# Una sola pasada, solo nivel nacional
python main.py --una-vez --nivel-maximo nacional

# Bucle cada 60 s, hasta departamento, con 0.1 s entre peticiones
python main.py --intervalo 60 --nivel-maximo departamento --delay 0.1
```

| Argumento        | Descripción                                          | Por defecto  |
| ---------------- | ---------------------------------------------------- | ------------ |
| `--intervalo`    | Segundos entre cada pasada                            | 300          |
| `--nivel-maximo` | `nacional`, `departamento`, `provincia` o `distrito` | departamento |
| `--delay`        | Segundos entre peticiones HTTP                        | 0.2          |
| `--una-vez`      | Ejecuta una sola pasada y termina                    | (bucle)      |

> Nota: recorrer hasta distrito implica miles de peticiones por pasada. Ajusta
> `--delay` e `--intervalo` para no saturar el servidor de ONPE.

## Página web

La web lee los CSV generados por el scraper y muestra el resultado general y el
detalle por región de forma dinámica (barras animadas, resumen por regiones y
grilla de regiones). Toda la interfaz se ajusta al 100 % del ancho y alto de la
pantalla (cada zona desplaza su propio contenido) y se auto-refresca cada 60 s.

Además, el servidor web trae datos de la ONPE automáticamente en segundo plano
cada cierto intervalo, por lo que basta con iniciarlo:

```powershell
python -m src.web
```

Abre http://127.0.0.1:5000 en el navegador.

Configuración del recolector automático mediante variables de entorno:

| Variable             | Por defecto    | Descripción                                              |
| -------------------- | -------------- | -------------------------------------------------------- |
| `ONPE_INTERVALO`     | `60`           | Segundos entre cada recolección automática de la ONPE.   |
| `ONPE_NIVEL_MAXIMO`  | `departamento` | Nivel máximo a recorrer (`nacional`/`departamento`/...). |

Ejemplo (PowerShell) para refrescar cada 2 minutos:

```powershell
$env:ONPE_INTERVALO = "120"; python -m src.web
```

## Despliegue en producción

La aplicación es de **solo lectura** (sin login ni base de datos), por lo que el
endurecimiento se centra en evitar abuso/DoS y en no exponer configuración
insegura. Se incluyen varias capas de defensa, activas automáticamente:

- **Servidor WSGI (gunicorn):** nunca se usa el servidor de desarrollo de Flask.
- **Cabeceras de seguridad + CSP (Flask-Talisman):** `Content-Security-Policy`,
  `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy`
  y, con `FORCE_HTTPS=1`, redirección a HTTPS + HSTS.
- **Límite de peticiones por IP (Flask-Limiter):** 120/min global y 30/min en los
  endpoints que agregan datos (`/api/regiones`, `/api/resumen`). Excederlo
  devuelve `HTTP 429`.
- **Caché de respuestas en memoria (TTL):** las respuestas JSON se cachean unos
  segundos (`CACHE_TTL`, 20 s por defecto) y se envían con `Cache-Control`. Así
  un aluvión de peticiones no recalcula ni lee disco en cada request: se sirve la
  copia ya construida. La caché tiene un tope de entradas con poda para que pedir
  muchos ubigeos distintos no infle la memoria.
- **Límite de tamaño de petición:** `MAX_CONTENT_LENGTH` rechaza cuerpos grandes
  (`HTTP 413`); los estáticos (CSS/JS/imágenes) se cachean 1 día en el navegador.
- **Errores en JSON:** 404/413/429 devuelven mensajes genéricos sin filtrar
  detalles internos.

Además, la entrada de usuario (`/api/region/<ubigeo>`) se valida (solo dígitos) y
`FLASK_DEBUG` está desactivado por defecto (con `debug=True` el depurador de
Werkzeug permite ejecución remota de código).

> **Importante — protección ante DDoS volumétrico:** el rate limiting por IP frena
> a un script desde una sola IP, pero **no** detiene un ataque distribuido (botnet
> con miles de IPs); ninguna defensa a nivel de aplicación lo hace. Para eso, pon
> un **CDN/WAF delante del dominio**. Lo más sencillo y gratuito es
> [Cloudflare](https://www.cloudflare.com/): añade tu dominio, apunta el DNS a
> Cloudflare (proxy activado, nube naranja), y absorberá los ataques volumétricos
> antes de que lleguen al servidor. Con su caché y el modo *"Under Attack"* la web
> aguanta picos enormes sin tocar el origen.

### Variables de entorno de producción

| Variable             | Valor recomendado | Descripción                                              |
| -------------------- | ----------------- | -------------------------------------------------------- |
| `FLASK_DEBUG`        | `0`               | Modo depuración. **Siempre 0 en producción.**            |
| `FORCE_HTTPS`        | `1`               | Redirige a HTTPS y activa HSTS (detrás de un proxy TLS). |
| `ONPE_RECOLECTOR`    | `1`               | Arranca el recolector dentro del proceso web (gunicorn). |
| `ONPE_INTERVALO`     | `180`             | Segundos entre cada recolección automática de la ONPE.   |
| `ONPE_NIVEL_MAXIMO`  | `departamento`    | Nivel máximo a recorrer.                                 |
| `CACHE_TTL`          | `20`              | Segundos que se cachea cada respuesta JSON en memoria.   |

Hay un archivo [.env.example](.env.example) con todas las variables.

### Probar el servidor de producción en local

> gunicorn no funciona en Windows. En Windows usa WSL o prueba con el servidor de
> desarrollo (`python -m src.web`). En Linux/macOS:

```bash
ONPE_RECOLECTOR=1 gunicorn --workers 1 --threads 4 --bind 0.0.0.0:8000 src.web:app
```

### Desplegar en Render

1. Sube el repositorio a GitHub (ya incluye [Procfile](Procfile) y
   [render.yaml](render.yaml)).
2. En [Render](https://render.com): **New → Blueprint** y selecciona el repo; se
   leerá `render.yaml` con el comando de inicio y las variables de entorno.
   (Alternativa: **New → Web Service**, _Build_ `pip install -r requirements.txt`,
   _Start_ el comando del `Procfile`).
3. Render asigna un subdominio `*.onrender.com` con **HTTPS automático**.

> **Notas del plan gratuito:**
>
> - El sistema de archivos es **efímero**: el histórico en `data/*.csv` se borra
>   en cada redeploy, pero el snapshot más reciente se reconstruye solo en el
>   primer ciclo del recolector. Para conservar el histórico, añade un disco
>   persistente.
> - El servicio "duerme" tras inactividad; el recolector se reanuda con la
>   siguiente visita.

### Usa un único worker

El recolector vive en un hilo dentro del proceso web. Mantén **`--workers 1`**
(como en el `Procfile`/`render.yaml`) para no ejecutar varios recolectores en
paralelo. Para escalar horizontalmente, separa el recolector en un servicio
aparte.

## Datos

Los CSV se guardan en `data/` en formato largo, con una fila por ámbito (y por
candidato en el caso de participantes) y marca de tiempo de captura. Las filas se
agregan solo cuando cambia la `fecha_actualizacion` de la ONPE, conservando el
histórico de la evolución del conteo.

## Pruebas

```powershell
python -m pytest
```

