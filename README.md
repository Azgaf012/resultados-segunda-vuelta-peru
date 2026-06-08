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
  con barras animadas y auto-refresco.
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

## Datos

Los CSV se guardan en `data/` en formato largo, con una fila por ámbito (y por
candidato en el caso de participantes) y marca de tiempo de captura. Las filas se
agregan solo cuando cambia la `fecha_actualizacion` de la ONPE, conservando el
histórico de la evolución del conteo.

## Pruebas

```powershell
python -m pytest
```

