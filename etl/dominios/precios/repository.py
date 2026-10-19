"""Load: upserts idempotentes en SQL Server (MERGE).

Idempotencia:
  * D_PrecioCadena    por Codigo.
  * D_PrecioSucursal  por (CadenaId, CodigoSucursal).
  * D_PrecioProducto  por (CadenaId, SkuId).
  * D_PrecioOferta    por (ProductoId, SucursalId, Fecha) -> re-correr el mismo
    día actualiza, no duplica.

Todas las sentencias van parametrizadas (sin literales inline). El id de
Cadena/Sucursal/Producto se obtiene con `OUTPUT inserted.<Id>`.
"""
from __future__ import annotations

from datetime import date

from .categorias import canonica
from .modelos import Oferta, Producto


def _txt(valor, n: int):
    """Trunca a la longitud de columna (None-safe). Evita 'data truncated'."""
    if valor is None:
        return None
    s = str(valor)
    return s if len(s) <= n else s[:n]

_MERGE_CADENA = """
MERGE dbo.D_PrecioCadena AS t
USING (VALUES (?, ?, ?, ?, ?, ?))
      AS s (Codigo, Nombre, Plataforma, Host, ApiHost, CuentaVtex)
   ON t.Codigo = s.Codigo
WHEN MATCHED THEN
    UPDATE SET t.Nombre = s.Nombre, t.Plataforma = s.Plataforma,
               t.Host = s.Host, t.ApiHost = s.ApiHost,
               t.CuentaVtex = s.CuentaVtex, t.Activa = 1
WHEN NOT MATCHED THEN
    INSERT (Codigo, Nombre, Plataforma, Host, ApiHost, CuentaVtex, Activa)
    VALUES (s.Codigo, s.Nombre, s.Plataforma, s.Host, s.ApiHost, s.CuentaVtex, 1)
OUTPUT inserted.CadenaId;
"""

_MERGE_SUCURSAL = """
MERGE dbo.D_PrecioSucursal AS t
USING (VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?))
      AS s (CadenaId, CodigoSucursal, Tipo, Nombre, Direccion, Localidad,
            Provincia, CodigoPostal, Latitud, Longitud, CodigoSepa)
   ON t.CadenaId = s.CadenaId AND t.CodigoSucursal = s.CodigoSucursal
WHEN MATCHED THEN
    UPDATE SET t.Tipo = s.Tipo, t.Nombre = s.Nombre, t.Direccion = s.Direccion,
               t.Localidad = s.Localidad, t.Provincia = s.Provincia,
               t.CodigoPostal = s.CodigoPostal, t.Latitud = s.Latitud,
               t.Longitud = s.Longitud, t.CodigoSepa = s.CodigoSepa
WHEN NOT MATCHED THEN
    INSERT (CadenaId, CodigoSucursal, Tipo, Nombre, Direccion, Localidad,
            Provincia, CodigoPostal, Latitud, Longitud, CodigoSepa)
    VALUES (s.CadenaId, s.CodigoSucursal, s.Tipo, s.Nombre, s.Direccion,
            s.Localidad, s.Provincia, s.CodigoPostal, s.Latitud, s.Longitud,
            s.CodigoSepa)
OUTPUT inserted.SucursalId;
"""

_MERGE_PRODUCTO = """
MERGE dbo.D_PrecioProducto AS t
USING (VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?))
      AS s (CadenaId, SkuId, ProductoExtId, Ean, Nombre, Marca, Categoria,
            CategoriaId, Subcategoria, CategoriaCanonica, Unidad, Multiplicador,
            ContenidoNeto, Url, Imagen, Descripcion, CodigoRef, FechaPublicacion)
   ON t.CadenaId = s.CadenaId AND t.SkuId = s.SkuId
WHEN MATCHED THEN
    UPDATE SET t.ProductoExtId = s.ProductoExtId, t.Ean = s.Ean,
               t.Nombre = s.Nombre, t.Marca = s.Marca, t.Categoria = s.Categoria,
               t.CategoriaId = s.CategoriaId, t.Subcategoria = s.Subcategoria,
               t.CategoriaCanonica = s.CategoriaCanonica,
               t.Unidad = s.Unidad, t.Multiplicador = s.Multiplicador,
               t.ContenidoNeto = s.ContenidoNeto, t.Url = s.Url,
               t.Imagen = s.Imagen, t.Descripcion = s.Descripcion,
               t.CodigoRef = s.CodigoRef,
               t.FechaPublicacion = s.FechaPublicacion,
               t.UltimaVez = SYSDATETIME()
WHEN NOT MATCHED THEN
    INSERT (CadenaId, SkuId, ProductoExtId, Ean, Nombre, Marca, Categoria,
            CategoriaId, Subcategoria, CategoriaCanonica, Unidad, Multiplicador,
            ContenidoNeto, Url, Imagen, Descripcion, CodigoRef, FechaPublicacion)
    VALUES (s.CadenaId, s.SkuId, s.ProductoExtId, s.Ean, s.Nombre, s.Marca,
            s.Categoria, s.CategoriaId, s.Subcategoria, s.CategoriaCanonica,
            s.Unidad, s.Multiplicador, s.ContenidoNeto, s.Url, s.Imagen,
            s.Descripcion, s.CodigoRef, s.FechaPublicacion)
OUTPUT inserted.ProductoId;
"""

_MERGE_OFERTA = """
MERGE dbo.D_PrecioOferta AS t
USING (VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?))
      AS s (ProductoId, SucursalId, Fecha, Precio, PrecioLista, PrecioSinImp,
            PrecioUnitario, EnPromo, DescripcionPromo, PromoDesde, PromoHasta,
            DescuentoPorc, Stock, Moneda, Disponible, Origen)
   ON t.ProductoId = s.ProductoId
      AND t.SucursalId = s.SucursalId
      AND t.Fecha = s.Fecha
WHEN MATCHED THEN
    UPDATE SET t.Precio = s.Precio, t.PrecioLista = s.PrecioLista,
               t.PrecioSinImp = s.PrecioSinImp,
               t.PrecioUnitario = s.PrecioUnitario,
               t.EnPromo = s.EnPromo, t.DescripcionPromo = s.DescripcionPromo,
               t.PromoDesde = s.PromoDesde, t.PromoHasta = s.PromoHasta,
               t.DescuentoPorc = s.DescuentoPorc, t.Stock = s.Stock,
               t.Moneda = s.Moneda, t.Disponible = s.Disponible,
               t.Origen = s.Origen, t.FechaCarga = SYSDATETIME()
WHEN NOT MATCHED THEN
    INSERT (ProductoId, SucursalId, Fecha, Precio, PrecioLista, PrecioSinImp,
            PrecioUnitario, EnPromo, DescripcionPromo, PromoDesde, PromoHasta,
            DescuentoPorc, Stock, Moneda, Disponible, Origen)
    VALUES (s.ProductoId, s.SucursalId, s.Fecha, s.Precio, s.PrecioLista,
            s.PrecioSinImp, s.PrecioUnitario, s.EnPromo, s.DescripcionPromo,
            s.PromoDesde, s.PromoHasta, s.DescuentoPorc, s.Stock, s.Moneda,
            s.Disponible, s.Origen);
"""


def upsert_cadena(
    cur, *, codigo: str, nombre: str, plataforma: str = "VTEX",
    host: str | None = None, api_host: str | None = None,
    cuenta_vtex: str | None = None,
) -> int:
    cur.execute(_MERGE_CADENA, (
        _txt(codigo, 40), _txt(nombre, 100), _txt(plataforma, 30),
        _txt(host, 120), _txt(api_host, 120), _txt(cuenta_vtex, 60),
    ))
    return int(cur.fetchone()[0])


def upsert_sucursal(
    cur, *, cadena_id: int, codigo: str, tipo: str = "SUPER",
    nombre: str | None = None, direccion: str | None = None,
    localidad: str | None = None, provincia: str | None = None,
    codigo_postal: str | None = None, latitud: float | None = None,
    longitud: float | None = None, codigo_sepa: str | None = None,
) -> int:
    cur.execute(
        _MERGE_SUCURSAL,
        (cadena_id, _txt(codigo, 40), _txt(tipo, 20), _txt(nombre, 150),
         _txt(direccion, 200), _txt(localidad, 100), _txt(provincia, 60),
         _txt(codigo_postal, 12), latitud, longitud, _txt(codigo_sepa, 40)),
    )
    return int(cur.fetchone()[0])


def upsert_producto(cur, cadena_id: int, p: Producto) -> int:
    cur.execute(
        _MERGE_PRODUCTO,
        (cadena_id, _txt(p.sku_id, 40), _txt(p.producto_ext_id, 40),
         _txt(p.ean, 14), _txt(p.nombre, 300), _txt(p.marca, 120),
         _txt(p.categoria, 300), _txt(p.categoria_id, 40),
         _txt(p.subcategoria, 150),
         _txt(canonica(p.categoria, p.subcategoria, p.nombre), 40),
         _txt(p.unidad, 10), p.multiplicador,
         p.contenido_neto, _txt(p.url, 500), _txt(p.imagen, 500),
         _txt(p.descripcion, 1000), _txt(p.codigo_ref, 60), p.fecha_publicacion),
    )
    return int(cur.fetchone()[0])


def upsert_oferta(
    cur, *, producto_id: int, sucursal_id: int, oferta: Oferta,
    origen: str = "API",
) -> None:
    fecha = oferta.fecha or date.today()
    cur.execute(
        _MERGE_OFERTA,
        (producto_id, sucursal_id, fecha, oferta.precio, oferta.precio_lista,
         oferta.precio_sin_imp, oferta.precio_unitario, int(oferta.en_promo),
         _txt(oferta.descripcion_promo, 200), oferta.promo_desde,
         oferta.promo_hasta, oferta.descuento_porc, oferta.stock,
         _txt(oferta.moneda, 3), int(oferta.disponible), _txt(origen, 20)),
    )
