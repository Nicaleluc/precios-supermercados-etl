"""Lector de los archivos oficiales de **SEPA** (Precios Claros).

Estructura real (verificada 2026-10-13):
  outer.zip
    <fecha>/sepa_<n>_comercio-sepa-<m>_<fecha>.zip   (ZIPs anidados)
        comercio.csv      id_comercio|id_bandera|...|comercio_bandera_nombre|...
        sucursales.csv    id_comercio|id_bandera|id_sucursal|sucursales_nombre|
                          sucursales_calle|...|sucursales_localidad|sucursales_provincia
        productos.csv     id_comercio|id_bandera|id_sucursal|id_producto(=EAN)|
                          productos_ean(flag)|productos_descripcion|productos_marca|
                          productos_precio_lista|...|productos_leyenda_promo1|...

Delimitador `|`, UTF-8 con BOM.
  * comercio.csv   -> `D_PrecioCadena` (id_comercio+id_bandera -> nombre de bandera)
  * sucursales.csv -> `D_PrecioSucursal` (id_comercio+id_sucursal = local)
  * productos.csv  -> `D_PrecioProducto` + `D_PrecioOferta` (precio POR SUCURSAL)

Las ofertas (el volumen, millones) se cargan en **bulk** con `fast_executemany`;
antes se borran las filas SEPA de esa fecha (idempotente). `limite`/`max_grupos`
sirven para validar sin cargar todo.
"""
from __future__ import annotations

import csv
import io
import re
import zipfile
from datetime import date
from pathlib import Path

from etl.conn.db import get_connection

from etl.dominios.precios.modelos import Producto
from etl.dominios.precios.repository import (
    upsert_cadena,
    upsert_producto,
    upsert_sucursal,
)


class SepaError(RuntimeError):
    """Falla al leer/mapear los archivos de SEPA."""


_RE_FECHA = re.compile(r"(\d{4}-\d{2}-\d{2})")
_INSERT_OFERTA = """
INSERT INTO dbo.D_PrecioOferta
    (ProductoId, SucursalId, Fecha, Precio, PrecioLista, PrecioSinImp,
     PrecioUnitario, EnPromo, DescripcionPromo, PromoDesde, PromoHasta,
     DescuentoPorc, Stock, Moneda, Disponible, Origen)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

_PROVINCIAS = {
    "AR-C": "Ciudad Autónoma de Buenos Aires",
    "AR-B": "Buenos Aires",
    "AR-K": "Catamarca", "AR-H": "Chaco", "AR-U": "Chubut", "AR-X": "Córdoba",
    "AR-W": "Corrientes", "AR-E": "Entre Ríos", "AR-P": "Formosa", "AR-Y": "Jujuy",
    "AR-L": "La Pampa", "AR-F": "La Rioja", "AR-M": "Mendoza", "AR-N": "Misiones",
    "AR-Q": "Neuquén", "AR-R": "Río Negro", "AR-A": "Salta", "AR-J": "San Juan",
    "AR-D": "San Luis", "AR-Z": "Santa Cruz", "AR-S": "Santa Fe",
    "AR-G": "Santiago del Estero", "AR-V": "Tierra del Fuego", "AR-T": "Tucumán",
}


def _filas(zf: zipfile.ZipFile, nombre: str):
    """Genera dicts de un CSV `|`-delimitado, UTF-8 con BOM."""
    try:
        fh = zf.open(nombre)
    except KeyError:
        return
    with io.TextIOWrapper(fh, encoding="utf-8-sig", errors="replace", newline="") as f:
        yield from csv.DictReader(f, delimiter="|")


def _num(valor) -> float | None:
    if valor is None or valor == "":
        return None
    try:
        return float(str(valor).replace(",", "."))
    except ValueError:
        return None


def _zip_inner(entrada: Path):
    """Genera (nombre, bytes) de cada inner ZIP; o el propio archivo si es un inner."""
    if entrada.suffix.lower() != ".zip":
        raise SepaError(f"Esperaba un .zip: {entrada}")
    with zipfile.ZipFile(entrada) as z:
        inner = [n for n in z.namelist() if n.lower().endswith(".zip")]
        if not inner:  # ya es un inner zip (tiene los CSV)
            yield entrada.name, entrada.read_bytes()
            return
        for n in inner:
            data = z.read(n)
            if data:
                yield n, data


def _flush_ofertas(cur, filas) -> None:
    if not filas:
        return
    cur.fast_executemany = True
    cur.executemany(_INSERT_OFERTA, filas)
    cur.fast_executemany = False


def cargar_zip(cur, conn, entrada: Path, *, limite: int | None = None,
               max_grupos: int | None = None, banderas=None,
               fecha: date | None = None) -> dict:
    stats = {"grupos": 0, "cadenas": 0, "sucursales": 0, "productos": 0, "precios": 0}
    cache_cad: dict[tuple, int] = {}
    cache_suc: dict[tuple, int] = {}
    cache_prod: dict[tuple, int] = {}
    limpiadas: set[date] = set()
    buffer: list[tuple] = []
    restante = limite

    def _es_id(valor) -> bool:
        return str(valor or "").strip().isdigit()

    try:
        for nombre, data in _zip_inner(entrada):
            if max_grupos and stats["grupos"] >= max_grupos:
                break
            if not data:
                continue
            stats["grupos"] += 1

            m = _RE_FECHA.search(nombre)
            fecha_grupo = fecha or (date.fromisoformat(m.group(1)) if m else date.today())
            if fecha_grupo not in limpiadas:
                cur.execute(
                    "DELETE FROM dbo.D_PrecioOferta WHERE Origen = ? AND Fecha = ?",
                    ("SEPA", fecha_grupo),
                )
                limpiadas.add(fecha_grupo)

            with zipfile.ZipFile(io.BytesIO(data)) as z:
                nombres = {n.lower(): n for n in z.namelist()}
                n_com = nombres.get("comercio.csv")
                n_suc = nombres.get("sucursales.csv")
                n_prod = nombres.get("productos.csv")

                nombres_bandera: dict[tuple, str] = {}
                if n_com:
                    for row in _filas(z, n_com):
                        com = str(row.get("id_comercio") or "").strip()
                        b = str(row.get("id_bandera") or "").strip()
                        nom = (row.get("comercio_bandera_nombre") or "").strip()
                        if _es_id(com) and _es_id(b) and nom:
                            nombres_bandera.setdefault((com, b), nom)

                def cadena_id(comercio: str, bandera: str) -> int:
                    clave = (comercio, bandera)
                    if clave in cache_cad:
                        return cache_cad[clave]
                    if banderas and bandera in banderas:
                        nom = banderas[bandera]
                    else:
                        nom = nombres_bandera.get(clave) or f"SEPA {comercio}-{bandera}"
                    cache_cad[clave] = upsert_cadena(
                        cur, codigo=f"sepa_{comercio}_{bandera}", nombre=nom,
                        plataforma="SEPA")
                    stats["cadenas"] += 1
                    return cache_cad[clave]

                if n_suc:
                    for row in _filas(z, n_suc):
                        com = str(row.get("id_comercio") or "").strip()
                        b = str(row.get("id_bandera") or "").strip()
                        suc = str(row.get("id_sucursal") or "").strip()
                        if not (_es_id(com) and _es_id(suc)):
                            continue
                        cid = cadena_id(com, b)
                        direccion = " ".join(filter(None, [
                            (row.get("sucursales_calle") or "").strip(),
                            (row.get("sucursales_numero") or "").strip()]))
                        prov = (row.get("sucursales_provincia") or "").strip()
                        sid = upsert_sucursal(
                            cur, cadena_id=cid, codigo=f"SEPA-{com}-{suc}", tipo="SUPER",
                            nombre=(row.get("sucursales_nombre") or None),
                            direccion=(direccion or None),
                            localidad=(row.get("sucursales_localidad") or None),
                            provincia=(_PROVINCIAS.get(prov, prov) or None),
                            codigo_postal=(row.get("sucursales_codigo_postal") or None),
                            latitud=_num(row.get("sucursales_latitud")),
                            longitud=_num(row.get("sucursales_longitud")),
                            codigo_sepa=f"{com}-{suc}",
                        )
                        cache_suc[(com, suc)] = sid
                        stats["sucursales"] += 1

                if n_prod:
                    for row in _filas(z, n_prod):
                        if restante is not None and restante <= 0:
                            break
                        com = str(row.get("id_comercio") or "").strip()
                        suc = str(row.get("id_sucursal") or "").strip()
                        b = str(row.get("id_bandera") or "").strip()
                        if not (_es_id(com) and _es_id(suc)):
                            continue
                        id_prod = str(row.get("id_producto") or "").strip()
                        if not id_prod:
                            continue
                        ean = id_prod if id_prod.isdigit() and 8 <= len(id_prod) <= 14 else None
                        precio = _num(row.get("productos_precio_lista"))
                        if precio is None:
                            precio = _num(row.get("productos_precio_referencia"))
                        if precio is None:
                            continue
                        par = cache_suc.get((com, suc))
                        if par is None:
                            continue
                        cid = cadena_id(com, b)
                        pkey = (cid, id_prod)
                        if pkey not in cache_prod:
                            prod = Producto(
                                cadena=f"sepa_{com}_{b}", sku_id=id_prod,
                                nombre=(row.get("productos_descripcion") or id_prod),
                                ean=ean, marca=(row.get("productos_marca") or None),
                            )
                            cache_prod[pkey] = upsert_producto(cur, cid, prod)
                            stats["productos"] += 1
                        leyenda = (row.get("productos_leyenda_promo1") or "").strip()
                        buffer.append((
                            cache_prod[pkey], par, fecha_grupo, precio, None, None,
                            None, int(bool(leyenda)), (leyenda or None), None, None,
                            None, None, "ARS", 1, "SEPA",
                        ))
                        stats["precios"] += 1
                        if len(buffer) >= 5000:
                            _flush_ofertas(cur, buffer)
                            buffer = []
                        if restante is not None:
                            restante -= 1
            _flush_ofertas(cur, buffer)
            buffer = []
            conn.commit()
    finally:
        _flush_ofertas(cur, buffer)
        conn.commit()
    return stats


def cargar(entrada, *, limite=None, max_grupos=None, banderas=None,
           fecha=None, conn=None) -> dict:
    entrada = Path(entrada)
    if not entrada.is_file():
        raise SepaError(f"No existe: {entrada}")
    propias = conn is None
    conn = conn or get_connection()
    cur = conn.cursor()
    try:
        stats = cargar_zip(cur, conn, entrada, limite=limite, max_grupos=max_grupos,
                           banderas=banderas, fecha=fecha)
        conn.commit()
        return stats
    finally:
        if propias:
            conn.close()
