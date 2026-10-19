"""Comparador cruzado sobre las tablas `D_Precio*` (no consulta los sitios).

Responde, leyendo el store en SQL Server: dada una lista de lo que hay que
comprar, en qué cadena conviene cada ítem; y dado un producto, sus
**equivalentes** en las demás cadenas (fuzzy + EAN).

Matching:
  * por **nombre** (contiene, normalizado) para resolver un término;
  * por **EAN** exacto (`por_ean`);
  * por **similitud** (rapidfuzz + tamaño) para equivalentes (`equivalentes`).
"""
from __future__ import annotations

from dataclasses import dataclass

from .canasta import recomendar
from .matching import normalizar, precio_unidad, similitud

_ULTIMAS = """
WITH ult AS (
    SELECT o.ProductoId, o.Precio, o.SucursalId, o.Disponible,
           ROW_NUMBER() OVER (PARTITION BY o.ProductoId ORDER BY o.Fecha DESC) AS rn
    FROM dbo.D_PrecioOferta o
)
SELECT ch.Codigo AS cadena, p.Nombre, p.SkuId, p.Ean, p.Marca, p.Url,
       ult.Precio, s.CodigoSucursal, p.CategoriaCanonica
FROM ult
JOIN dbo.D_PrecioProducto p ON p.ProductoId = ult.ProductoId
JOIN dbo.D_PrecioCadena   ch ON ch.CadenaId = p.CadenaId
JOIN dbo.D_PrecioSucursal s  ON s.SucursalId = ult.SucursalId
WHERE ult.rn = 1 AND ult.Disponible = 1 AND p.Nombre LIKE ?
"""


@dataclass
class Opcion:
    cadena: str
    nombre: str
    sku: str
    ean: str | None
    marca: str | None
    precio: float
    url: str | None
    sucursal: str
    categoria: str | None = None
    precio_unidad: float | None = None


@dataclass
class ItemComparado:
    termino: str
    por_cadena: dict[str, Opcion]

    @property
    def mejor(self) -> tuple[str, Opcion] | None:
        disp = {c: o for c, o in self.por_cadena.items() if o is not None}
        if not disp:
            return None
        cadena = min(disp, key=lambda c: disp[c].precio)
        return cadena, disp[cadena]


def _filtro_cadenas(cadenas) -> tuple[str, tuple]:
    if not cadenas:
        return "", ()
    marcas = ",".join("?" * len(cadenas))
    return f" AND ch.Codigo IN ({marcas})", tuple(cadenas)


def _opciones(cur, sql, params) -> list[Opcion]:
    cur.execute(sql, params)
    out = []
    for cadena, nombre, sku, ean, marca, url, precio, sucursal, cat in cur.fetchall():
        precio = float(precio)
        out.append(Opcion(cadena, nombre, sku, ean, marca, precio, url, sucursal,
                          cat, precio_unidad(precio, nombre)))
    return out


def _mejores_por_cadena(opciones, por_unidad: bool = False) -> dict[str, Opcion]:
    def clave(o: Opcion) -> float:
        if por_unidad and o.precio_unidad:
            return o.precio_unidad
        return o.precio

    mejores: dict[str, Opcion] = {}
    for o in opciones:
        actual = mejores.get(o.cadena)
        if actual is None or clave(o) < clave(actual):
            mejores[o.cadena] = o
    return mejores


def comparar_termino(cur, termino: str, cadenas=None, *, por_unidad: bool = False) -> ItemComparado:
    filtro, params = _filtro_cadenas(cadenas)
    opciones = _opciones(cur, _ULTIMAS + filtro, (f"%{termino}%", *params))
    return ItemComparado(termino=termino,
                         por_cadena=_mejores_por_cadena(opciones, por_unidad))


def por_ean(cur, ean: str, cadenas=None) -> list[Opcion]:
    """Todas las ofertas (una por cadena) de un EAN concreto — cruce exacto."""
    filtro, params = _filtro_cadenas(cadenas)
    sql = _ULTIMAS.replace("p.Nombre LIKE ?", "p.Ean = ?") + filtro
    return list(_mejores_por_cadena(_opciones(cur, sql, (ean, *params))).values())


def equivalentes(cur, nombre: str, marca=None, cadenas=None, *, umbral: float = 0.6):
    """Producto más parecido (>= umbral) en cada cadena, por similitud de nombre.

    Devuelve `{cadena: (score, Opcion)}`.
    """
    token = (normalizar(nombre).split() or [""])[0]
    filtro, params = _filtro_cadenas(cadenas)
    opciones = _opciones(cur, _ULTIMAS + filtro, (f"%{token}%", *params))
    mejor: dict[str, tuple[float, Opcion]] = {}
    for o in opciones:
        s = similitud(o.nombre, nombre)
        if marca and o.marca and normalizar(marca) in normalizar(o.marca):
            s = min(1.0, s + 0.15)
        if s < umbral:
            continue
        if o.cadena not in mejor or s > mejor[o.cadena][0]:
            mejor[o.cadena] = (s, o)
    return mejor


def comparar(cur, terminos, cadenas=None, *, por_unidad: bool = False) -> list[ItemComparado]:
    return [comparar_termino(cur, t, cadenas, por_unidad=por_unidad) for t in terminos]


__all__ = ["Opcion", "ItemComparado", "comparar_termino", "comparar",
           "por_ean", "equivalentes", "recomendar"]
