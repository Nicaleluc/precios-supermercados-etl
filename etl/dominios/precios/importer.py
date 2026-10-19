"""Orquesta el extract -> SQL Server (MERGE), por plataforma.

Flujo: por cada cadena asegura `D_PrecioCadena` y su sucursal `ONLINE`
(el online es un precio de toda la cadena); luego delega el extract según
`cadena.tipo` (VTEX / Coope), normaliza y hace MERGE de productos/ofertas.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from etl.conn.coope import CoopeClient, CoopeError
from etl.conn.db import get_connection
from etl.conn.la_banderita import LaBanderitaClient, LaBanderitaError
from etl.conn.vtex import VtexClient, VtexError

from .constants import CADENAS, TERMINOS_DEFAULT
from .normalizar import normalizar
from .normalizar_coope import normalizar as normalizar_coope
from .normalizar_la_banderita import normalizar as normalizar_la_banderita
from .repository import (
    upsert_cadena,
    upsert_oferta,
    upsert_producto,
    upsert_sucursal,
)
from .schema import ensure_tablas

_SUCURSAL_ONLINE = "ONLINE"


@dataclass
class ImportStats:
    cadenas: int = 0
    terminos: int = 0
    ofertas: int = 0
    errores: int = 0
    salteadas: list[str] = field(default_factory=list)


def _cuenta_vtex(api_host: str) -> str | None:
    if api_host and "vtexcommercestable" in api_host:
        return api_host.split(".")[0]
    return None


def _guardar(cur, cadena_id, sucursal_id, cache, oferta, stats) -> None:
    sku = oferta.producto.sku_id
    producto_id = cache.get(sku)
    if producto_id is None:
        producto_id = upsert_producto(cur, cadena_id, oferta.producto)
        cache[sku] = producto_id
    upsert_oferta(
        cur, producto_id=producto_id, sucursal_id=sucursal_id,
        oferta=oferta, origen="API",
    )
    stats.ofertas += 1


def _cargar_vtex(cur, conn, cadena, cadena_id, sucursal_id, terminos,
                 por_pagina, max_paginas, stats) -> None:
    cliente = VtexClient(cadena.host_api)
    cache: dict[str, int] = {}
    try:
        for termino in terminos:
            stats.terminos += 1
            for pagina in range(1, max_paginas + 1):
                try:
                    crudos = cliente.buscar_termino(
                        termino, pagina=pagina, por_pagina=por_pagina
                    )
                except VtexError as exc:
                    stats.errores += 1
                    print(f"[!] {cadena.nombre} '{termino}' p{pagina}: {exc}")
                    break
                if not crudos:
                    break
                for raw in crudos:
                    for oferta in normalizar(cadena.id, raw, cadena.host_api):
                        _guardar(cur, cadena_id, sucursal_id, cache, oferta, stats)
                if len(crudos) < por_pagina:
                    break
            conn.commit()
    finally:
        cliente.cerrar()


def _cargar_coope(cur, conn, cadena, cadena_id, sucursal_id, terminos, max_paginas, stats) -> None:
    """La Coope: búsqueda paginada por término (8 por página)."""
    cliente = CoopeClient(cadena.host_api)
    cache: dict[str, int] = {}
    try:
        for termino in terminos:
            stats.terminos += 1
            try:
                articulos = cliente.buscar_paginado(termino, max_paginas=max_paginas)
            except CoopeError as exc:
                stats.errores += 1
                print(f"[!] {cadena.nombre} '{termino}': {exc}")
                continue
            for art in articulos:
                oferta = normalizar_coope(cadena.id, art)
                if oferta is not None:
                    _guardar(cur, cadena_id, sucursal_id, cache, oferta, stats)
            conn.commit()
    finally:
        cliente.cerrar()


def _cargar_coope_catalogo(cur, conn, cadena, cadena_id, sucursal_id, stats,
                           cat_max_paginas, cat_terminos=None) -> None:
    """La Coope: recorre el catálogo usando los nombres de categoría como término."""
    cliente = CoopeClient(cadena.host_api)
    cache: dict[str, int] = {}
    try:
        try:
            nombres = cliente.categorias_nombres()
        except CoopeError as exc:
            stats.errores += 1
            print(f"[!] {cadena.nombre} categorias: {exc}")
            nombres = []
        if cat_terminos:
            nombres = nombres[:cat_terminos]
        vistos: set[str] = set()
        for nombre in nombres:
            n = (nombre or "").strip()
            if len(n) < 2 or n.lower() in vistos:
                continue
            vistos.add(n.lower())
            stats.terminos += 1
            try:
                articulos = cliente.buscar_paginado(n, max_paginas=cat_max_paginas)
            except CoopeError as exc:
                stats.errores += 1
                print(f"[!] {cadena.nombre} '{n}': {exc}")
                continue
            for art in articulos:
                oferta = normalizar_coope(cadena.id, art)
                if oferta is not None:
                    _guardar(cur, cadena_id, sucursal_id, cache, oferta, stats)
            conn.commit()
    finally:
        cliente.cerrar()


def _cargar_la_banderita(cur, conn, cadena, cadena_id, sucursal_id, terminos,
                         max_paginas, stats, ean_ficha=False) -> None:
    """La Banderita: scraper HTML (`/shop?s=<term>`); REST deshabilitada."""
    cliente = LaBanderitaClient(cadena.host)
    cache: dict[str, int] = {}
    try:
        for termino in terminos:
            stats.terminos += 1
            try:
                crudos = cliente.buscar(termino, max_paginas=max_paginas, con_ean=ean_ficha)
            except LaBanderitaError as exc:
                stats.errores += 1
                print(f"[!] {cadena.nombre} '{termino}': {exc}")
                continue
            for raw in crudos:
                oferta = normalizar_la_banderita(cadena.id, raw)
                if oferta is not None:
                    _guardar(cur, cadena_id, sucursal_id, cache, oferta, stats)
            conn.commit()
    finally:
        cliente.cerrar()


def _aplanar_categorias(arbol) -> list:
    ids: list = []
    for cat in arbol or []:
        cid = cat.get("id")
        if cid:
            ids.append(cid)
        ids.extend(_aplanar_categorias(cat.get("children")))
    return ids


def _cargar_vtex_catalogo(cur, conn, cadena, cadena_id, sucursal_id, stats,
                          cat_max_paginas) -> None:
    """Recorre el árbol de categorías y carga todo el catálogo de la cadena."""
    cliente = VtexClient(cadena.host_api)
    cache: dict[str, int] = {}
    try:
        try:
            categorias = _aplanar_categorias(cliente.categorias_arbol())
        except VtexError as exc:
            stats.errores += 1
            print(f"[!] {cadena.nombre} categorias: {exc}")
            categorias = []
        stats.terminos += len(categorias)
        for cat in categorias:
            for pagina in range(cat_max_paginas):
                desde = pagina * 50
                try:
                    crudos = cliente.productos_por_categoria(cat, desde=desde, hasta=desde + 49)
                except VtexError as exc:
                    stats.errores += 1
                    print(f"[!] {cadena.nombre} cat {cat} p{pagina}: {exc}")
                    break
                if not crudos:
                    break
                for raw in crudos:
                    for oferta in normalizar(cadena.id, raw, cadena.host_api):
                        _guardar(cur, cadena_id, sucursal_id, cache, oferta, stats)
                if len(crudos) < 50:
                    break
            conn.commit()
    finally:
        cliente.cerrar()


def _cargar_la_banderita_catalogo(cur, conn, cadena, cadena_id, sucursal_id,
                                  stats, cat_max_paginas, cat_marcas=None) -> None:
    """La Banderita: recorre TODO el catálogo por marca (`?brand=`)."""
    cliente = LaBanderitaClient(cadena.host)
    cache: dict[str, int] = {}
    n = 0
    try:
        for raw in cliente.catalogo(max_paginas=cat_max_paginas, max_marcas=cat_marcas):
            oferta = normalizar_la_banderita(cadena.id, raw)
            if oferta is None:
                continue
            _guardar(cur, cadena_id, sucursal_id, cache, oferta, stats)
            n += 1
            if n % 500 == 0:
                conn.commit()
        conn.commit()
    finally:
        cliente.cerrar()


def cargar(ids_cadena, terminos=None, *, por_pagina: int = 50,
           max_paginas: int = 1, catalogo: bool = False,
           cat_max_paginas: int = 50, cat_marcas: int = None,
           cat_terminos: int = None, ean_ficha: bool = False, conn=None) -> ImportStats:
    """Extract + transform + load (MERGE) de las cadenas pedidas."""
    terminos = list(terminos or TERMINOS_DEFAULT)
    propias = conn is None
    conn = conn or get_connection()
    cur = conn.cursor()
    ensure_tablas(cur, conn)
    stats = ImportStats()
    try:
        for cid in ids_cadena:
            cadena = CADENAS.get(cid)
            if cadena is None:
                print(f"[!] cadena desconocida: {cid}")
                stats.salteadas.append(cid)
                continue
            if not cadena.host_api:
                print(f"[!] {cadena.nombre}: sin host confirmado, se saltea")
                stats.salteadas.append(cid)
                continue
            cadena_id = upsert_cadena(
                cur, codigo=cadena.id, nombre=cadena.nombre,
                plataforma=cadena.tipo.upper(), host=cadena.host or None,
                api_host=cadena.api_host or None,
                cuenta_vtex=_cuenta_vtex(cadena.host_api),
            )
            sucursal_id = upsert_sucursal(
                cur, cadena_id=cadena_id, codigo=_SUCURSAL_ONLINE, tipo="ONLINE",
                nombre=f"{cadena.nombre} (online)",
            )
            conn.commit()
            stats.cadenas += 1

            if cadena.tipo == "coope":
                if catalogo:
                    _cargar_coope_catalogo(cur, conn, cadena, cadena_id, sucursal_id,
                                           stats, cat_max_paginas, cat_terminos)
                else:
                    _cargar_coope(cur, conn, cadena, cadena_id, sucursal_id, terminos,
                                  max_paginas, stats)
            elif cadena.tipo == "la_banderita":
                if catalogo:
                    _cargar_la_banderita_catalogo(
                        cur, conn, cadena, cadena_id, sucursal_id, stats,
                        cat_max_paginas, cat_marcas)
                else:
                    _cargar_la_banderita(cur, conn, cadena, cadena_id, sucursal_id,
                                         terminos, max_paginas, stats, ean_ficha)
            elif catalogo:
                _cargar_vtex_catalogo(cur, conn, cadena, cadena_id, sucursal_id, stats,
                                      cat_max_paginas)
            else:
                _cargar_vtex(cur, conn, cadena, cadena_id, sucursal_id, terminos,
                             por_pagina, max_paginas, stats)
        return stats
    finally:
        if propias:
            conn.close()
