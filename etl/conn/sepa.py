"""Lector de los archivos oficiales de **SEPA** (Precios Claros) — versión BULK.

Estructura real:
  outer.zip
    <fecha>/sepa_<n>_comercio-sepa-<m>_<fecha>.zip   (ZIPs anidados)
        comercio.csv      id_comercio|id_bandera|...|comercio_bandera_nombre|...
        sucursales.csv    id_comercio|id_bandera|id_sucursal|sucursales_nombre|
                          sucursales_calle|...|sucursales_localidad|sucursales_provincia
        productos.csv     id_comercio|id_bandera|id_sucursal|id_producto(=EAN)|
                          productos_ean(flag)|productos_descripcion|productos_marca|
                          productos_precio_lista|productos_precio_referencia|
                          productos_leyenda_promo1|...

Delimitador `|`, UTF-8 con BOM.

Carga MASIVA (para los ~12 M de filas/día):
  1. Se leen los CSV y se vuelcan a tablas temporales (`#StgSuc`, `#StgProd`)
     con `fast_executemany`.
  2. Se hacen **MERGE set-based** a Cadena/Sucursal/Producto.
  3. Se borran las ofertas SEPA de la fecha y se hace `INSERT ... SELECT` masivo.

`precio_lista` -> `Precio`; `precio_referencia` -> `PrecioLista` (precio "normal").
"""
from __future__ import annotations

import csv
import io
import re
import zipfile
from datetime import date
from pathlib import Path

from etl.conn.db import get_connection


class SepaError(RuntimeError):
    """Falla al leer/mapear los archivos de SEPA."""


_RE_FECHA = re.compile(r"(\d{4}-\d{2}-\d{2})")

_PROVINCIAS = {
    "AR-C": "Ciudad Autónoma de Buenos Aires", "AR-B": "Buenos Aires",
    "AR-K": "Catamarca", "AR-H": "Chaco", "AR-U": "Chubut", "AR-X": "Córdoba",
    "AR-W": "Corrientes", "AR-E": "Entre Ríos", "AR-P": "Formosa", "AR-Y": "Jujuy",
    "AR-L": "La Pampa", "AR-F": "La Rioja", "AR-M": "Mendoza", "AR-N": "Misiones",
    "AR-Q": "Neuquén", "AR-R": "Río Negro", "AR-A": "Salta", "AR-J": "San Juan",
    "AR-D": "San Luis", "AR-Z": "Santa Cruz", "AR-S": "Santa Fe",
    "AR-G": "Santiago del Estero", "AR-V": "Tierra del Fuego", "AR-T": "Tucumán",
}

_DDL_STG_SUC = """
CREATE TABLE #StgSuc (
    CadenaCodigo varchar(80)  NOT NULL,
    CadenaNombre nvarchar(200) NOT NULL,
    SucCodigo    varchar(80)  NOT NULL,
    SucNombre    nvarchar(150) NULL,
    SucDireccion nvarchar(200) NULL,
    SucLocalidad nvarchar(100) NULL,
    SucProvincia nvarchar(60)  NULL,
    SucCP        varchar(12)   NULL,
    SucLat       decimal(9,6)  NULL,
    SucLng       decimal(9,6)  NULL
);
"""
_DDL_STG_PROD = """
CREATE TABLE #StgProd (
    CadenaCodigo varchar(80)  NOT NULL,
    SucCodigo    varchar(80)  NOT NULL,
    Sku          varchar(40)  NOT NULL,
    Ean          varchar(14)  NULL,
    Nombre       nvarchar(300) NOT NULL,
    Marca        nvarchar(120) NULL,
    Precio       decimal(18,2) NOT NULL,
    PrecioRef    decimal(18,2) NULL,
    EnPromo      bit           NOT NULL,
    LeyendaPromo nvarchar(200) NULL,
    Fecha        date          NOT NULL
);
"""
_INSERT_STG_SUC = (
    "INSERT INTO #StgSuc (CadenaCodigo, CadenaNombre, SucCodigo, SucNombre, "
    "SucDireccion, SucLocalidad, SucProvincia, SucCP, SucLat, SucLng) "
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
)
_INSERT_STG_PROD = (
    "INSERT INTO #StgProd (CadenaCodigo, SucCodigo, Sku, Ean, Nombre, Marca, "
    "Precio, PrecioRef, EnPromo, LeyendaPromo, Fecha) "
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
)

_MERGE_CADENA = """
MERGE dbo.D_PrecioCadena AS t
USING (SELECT DISTINCT CadenaCodigo, CadenaNombre FROM #StgSuc) AS s
   ON t.Codigo = s.CadenaCodigo
WHEN MATCHED THEN UPDATE SET t.Nombre = s.CadenaNombre, t.Plataforma = 'SEPA'
WHEN NOT MATCHED THEN INSERT (Codigo, Nombre, Plataforma)
     VALUES (s.CadenaCodigo, s.CadenaNombre, 'SEPA');
"""

_MERGE_SUCURSAL = """
MERGE dbo.D_PrecioSucursal AS t
USING (
    SELECT c.CadenaId, s.SucCodigo, s.SucNombre, s.SucDireccion, s.SucLocalidad,
           s.SucProvincia, s.SucCP, s.SucLat, s.SucLng
    FROM #StgSuc s JOIN dbo.D_PrecioCadena c ON c.Codigo = s.CadenaCodigo
) AS s
   ON t.CadenaId = s.CadenaId AND t.CodigoSucursal = s.SucCodigo
WHEN MATCHED THEN
    UPDATE SET t.Nombre = s.SucNombre, t.Direccion = s.SucDireccion,
               t.Localidad = s.SucLocalidad, t.Provincia = s.SucProvincia,
               t.CodigoPostal = s.SucCP, t.Latitud = s.SucLat,
               t.Longitud = s.SucLng, t.CodigoSepa = s.SucCodigo
WHEN NOT MATCHED THEN
    INSERT (CadenaId, CodigoSucursal, Tipo, Nombre, Direccion, Localidad,
            Provincia, CodigoPostal, Latitud, Longitud, CodigoSepa)
    VALUES (s.CadenaId, s.SucCodigo, 'SUPER', s.SucNombre, s.SucDireccion,
            s.SucLocalidad, s.SucProvincia, s.SucCP, s.SucLat, s.SucLng,
            s.SucCodigo);
"""

_MERGE_PRODUCTO = """
MERGE dbo.D_PrecioProducto AS t
USING (
    SELECT c.CadenaId, s.Sku, s.Ean, s.Nombre, s.Marca
    FROM (SELECT DISTINCT CadenaCodigo, Sku, Ean, Nombre, Marca FROM #StgProd) s
    JOIN dbo.D_PrecioCadena c ON c.Codigo = s.CadenaCodigo
) AS s
   ON t.CadenaId = s.CadenaId AND t.SkuId = s.Sku
WHEN MATCHED THEN
    UPDATE SET t.Ean = s.Ean, t.Nombre = s.Nombre, t.Marca = s.Marca,
               t.UltimaVez = SYSDATETIME()
WHEN NOT MATCHED THEN
    INSERT (CadenaId, SkuId, Ean, Nombre, Marca)
    VALUES (s.CadenaId, s.Sku, s.Ean, s.Nombre, s.Marca);
"""

_DELETE_OFERTAS = "DELETE FROM dbo.D_PrecioOferta WHERE Origen = 'SEPA' AND Fecha = ?"

_INSERT_OFERTAS = """
;WITH o AS (
    SELECT p.ProductoId, su.SucursalId, s.Fecha, s.Precio, s.PrecioRef,
           s.EnPromo, s.LeyendaPromo,
           ROW_NUMBER() OVER (PARTITION BY p.ProductoId, su.SucursalId
                              ORDER BY s.Precio) AS rn
    FROM #StgProd s
    JOIN dbo.D_PrecioCadena c   ON c.Codigo = s.CadenaCodigo
    JOIN dbo.D_PrecioSucursal su ON su.CadenaId = c.CadenaId
                                AND su.CodigoSucursal = s.SucCodigo
    JOIN dbo.D_PrecioProducto p  ON p.CadenaId = c.CadenaId AND p.SkuId = s.Sku
)
INSERT INTO dbo.D_PrecioOferta
    (ProductoId, SucursalId, Fecha, Precio, PrecioLista, EnPromo,
     DescripcionPromo, Moneda, Disponible, Origen)
SELECT ProductoId, SucursalId, Fecha, Precio, PrecioRef, EnPromo,
       LeyendaPromo, 'ARS', 1, 'SEPA'
FROM o WHERE rn = 1;
"""

_BATCH = 5000


def _filas(zf: zipfile.ZipFile, nombre: str):
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


def _es_id(valor) -> bool:
    return str(valor or "").strip().isdigit()


def _zip_inner(entrada: Path):
    if entrada.suffix.lower() != ".zip":
        raise SepaError(f"Esperaba un .zip: {entrada}")
    with zipfile.ZipFile(entrada) as z:
        inner = [n for n in z.namelist() if n.lower().endswith(".zip")]
        if not inner:
            yield entrada.name, entrada.read_bytes()
            return
        for n in inner:
            data = z.read(n)
            if data:
                yield n, data


def _flush(cur, sql, filas) -> None:
    if not filas:
        return
    cur.fast_executemany = True
    cur.executemany(sql, filas)
    cur.fast_executemany = False


def cargar_zip(cur, conn, entrada: Path, *, limite: int | None = None,
               max_grupos: int | None = None, fecha: date | None = None,
               banderas=None) -> dict:
    stats = {"grupos": 0, "cadenas": 0, "sucursales": 0, "productos": 0, "precios": 0}
    cur.execute(_DDL_STG_SUC)
    cur.execute(_DDL_STG_PROD)
    limpiadas: set[date] = set()
    cadenas_vistas: set[str] = set()
    restante = limite

    for nombre, data in _zip_inner(entrada):
        if max_grupos and stats["grupos"] >= max_grupos:
            break
        if not data:
            continue
        stats["grupos"] += 1

        m = _RE_FECHA.search(nombre)
        fecha_grupo = fecha or (date.fromisoformat(m.group(1)) if m else date.today())
        if fecha_grupo not in limpiadas:
            cur.execute(_DELETE_OFERTAS, (fecha_grupo,))
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

            def _cadena(com: str, b: str) -> tuple[str, str]:
                cod = f"sepa_{com}_{b}"
                cadenas_vistas.add(cod)
                if banderas and b in banderas:
                    return cod, banderas[b]
                return cod, nombres_bandera.get((com, b)) or f"SEPA {com}-{b}"

            # 1) sucursales -> #StgSuc
            cur.execute("TRUNCATE TABLE #StgSuc")
            lote = []
            for row in _filas(z, n_suc):
                com = str(row.get("id_comercio") or "").strip()
                b = str(row.get("id_bandera") or "").strip()
                suc = str(row.get("id_sucursal") or "").strip()
                if not (_es_id(com) and _es_id(suc)):
                    continue
                cod, nom = _cadena(com, b)
                direccion = " ".join(filter(None, [
                    (row.get("sucursales_calle") or "").strip(),
                    (row.get("sucursales_numero") or "").strip()]))
                prov = (row.get("sucursales_provincia") or "").strip()
                lote.append((
                    cod, nom, f"SEPA-{com}-{suc}",
                    row.get("sucursales_nombre") or None, direccion or None,
                    row.get("sucursales_localidad") or None,
                    _PROVINCIAS.get(prov, prov) or None,
                    row.get("sucursales_codigo_postal") or None,
                    _num(row.get("sucursales_latitud")),
                    _num(row.get("sucursales_longitud")),
                ))
                stats["sucursales"] += 1
                if len(lote) >= _BATCH:
                    _flush(cur, _INSERT_STG_SUC, lote)
                    lote = []
            _flush(cur, _INSERT_STG_SUC, lote)

            # 2) productos/precios -> #StgProd
            cur.execute("TRUNCATE TABLE #StgProd")
            lote = []
            for row in _filas(z, n_prod):
                if restante is not None and restante <= 0:
                    break
                com = str(row.get("id_comercio") or "").strip()
                b = str(row.get("id_bandera") or "").strip()
                suc = str(row.get("id_sucursal") or "").strip()
                if not (_es_id(com) and _es_id(suc)):
                    continue
                sku = str(row.get("id_producto") or "").strip()
                if not sku:
                    continue
                precio = _num(row.get("productos_precio_lista"))
                ref = _num(row.get("productos_precio_referencia"))
                if precio is None:
                    precio = ref
                if precio is None:
                    continue
                ean = sku if sku.isdigit() and 8 <= len(sku) <= 14 else None
                leyenda = (row.get("productos_leyenda_promo1") or "").strip()
                cod, _ = _cadena(com, b)
                lote.append((
                    cod, f"SEPA-{com}-{suc}", sku, ean,
                    row.get("productos_descripcion") or sku,
                    row.get("productos_marca") or None,
                    precio, ref, int(bool(leyenda)), leyenda or None, fecha_grupo,
                ))
                stats["productos"] += 1
                stats["precios"] += 1
                if len(lote) >= _BATCH:
                    _flush(cur, _INSERT_STG_PROD, lote)
                    lote = []
                if restante is not None:
                    restante -= 1
            _flush(cur, _INSERT_STG_PROD, lote)

            # 3) MERGE set-based + ofertas masivas
            cur.execute(_MERGE_CADENA)
            cur.execute(_MERGE_SUCURSAL)
            cur.execute(_MERGE_PRODUCTO)
            cur.execute(_INSERT_OFERTAS)
            conn.commit()

    stats["cadenas"] = len(cadenas_vistas)
    return stats


def cargar(entrada, *, limite=None, max_grupos=None, fecha=None, banderas=None, conn=None) -> dict:
    entrada = Path(entrada)
    if not entrada.is_file():
        raise SepaError(f"No existe: {entrada}")
    propias = conn is None
    conn = conn or get_connection()
    cur = conn.cursor()
    try:
        stats = cargar_zip(cur, conn, entrada, limite=limite,
                           max_grupos=max_grupos, fecha=fecha, banderas=banderas)
        conn.commit()
        return stats
    finally:
        if propias:
            conn.close()
