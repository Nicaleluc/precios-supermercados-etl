"""Configuración de precios-supermercados-etl (repo fuera del ecosistema DELI).

Destino: SQL Server (base `precios-supermercados-etl`), tablas
`D_Precio*`. Credenciales y rutas en `.env` (raíz de este repo); acá solo se
leen y tipan. Parser propio, mismo estilo que los hermanos ETL.
"""
import os
from pathlib import Path

_BASE_DIR = Path(__file__).resolve().parent.parent
_ENV_FILE = _BASE_DIR / ".env"


def _cargar_env() -> None:
    if not _ENV_FILE.exists():
        return
    for linea in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, _, valor = linea.partition("=")
        clave = clave.strip()
        valor = valor.strip()
        if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "\"'":
            valor = valor[1:-1]
        os.environ.setdefault(clave, valor)


_cargar_env()


def _get(clave: str, default: str = "") -> str:
    return os.getenv(clave, default)


# DIRECTORIO RAÍZ DEL REPO
BASE_DIR = _BASE_DIR

# SQL SERVER (tablas D_PrecioCadena / D_PrecioSucursal / D_PrecioProducto /
# D_PrecioOferta; ver etl/conn/db.py). Sin SQL_USERNAME -> Windows Auth.
SQL_SERVER = _get("SQL_SERVER", r"localhost\SQLEXPRESS")
SQL_DATABASE = _get("SQL_DATABASE", "precios-supermercados-etl")
SQL_USERNAME = _get("SQL_USERNAME")
SQL_PASSWORD = _get("SQL_PASSWORD")

# HTTP (scrapers de catálogos VTEX)
USER_AGENT = _get(
    "USER_AGENT",
    "precios-supermercados-etl/0.1 "
    "(+https://github.com/Nicaleluc/precios-supermercados-etl)",
)
HTTP_TIMEOUT = int(_get("HTTP_TIMEOUT", "20"))
HTTP_REINTENTOS = int(_get("HTTP_REINTENTOS", "3"))
HTTP_PAUSA = float(_get("HTTP_PAUSA", "0.5"))

# CADENAS habilitadas por defecto (ids de etl/dominios/precios/constants.py)
CADENAS = tuple(
    c.strip() for c in _get(
        "CADENAS",
        "vea,jumbo,disco,carrefour,changomas,cordiez,dia,cooperativa_obrera,la_banderita",
    ).split(",")
    if c.strip()
)

# EXTRACT de búsqueda
POR_PAGINA = int(_get("POR_PAGINA", "50"))
MAX_PAGINAS = int(_get("MAX_PAGINAS", "5"))
