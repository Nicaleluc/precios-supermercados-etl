"""Transform: producto crudo de VTEX -> `Oferta` normalizada."""
from __future__ import annotations

import re
from datetime import datetime, timezone

from .modelos import Oferta, Producto

_HTML = re.compile(r"<[^>]+>")


def _sin_html(valor) -> str | None:
    """Saca tags HTML (VTEX devuelve descripciones con markup)."""
    if not valor:
        return None
    texto = _HTML.sub(" ", str(valor)).replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", texto).strip() or None


def _a_float(valor) -> float | None:
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def _a_int(valor) -> int | None:
    try:
        return int(float(valor))
    except (TypeError, ValueError):
        return None


def _fecha_ms(valor) -> "datetime.date | None":
    """`releaseDate` de VTEX viene en epoch-ms."""
    ms = _a_int(valor)
    if not ms:
        return None
    try:
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).date()
    except (OverflowError, OSError, ValueError):
        return None


def _categoria(raw: dict) -> tuple[str | None, str | None]:
    """Devuelve (path completo, último nivel) del primer path de categoría."""
    cats = raw.get("categories") or []
    if isinstance(cats, list) and cats:
        path = str(cats[0])
        partes = [p for p in path.split("/") if p]
        return path, (partes[-1] if partes else None)
    return None, None


def normalizar(cadena_id: str, raw: dict, host: str = "") -> list[Oferta]:
    """Normaliza un producto crudo de VTEX a una oferta por SKU disponible.

    Toma el primer seller con precio válido de cada ítem; descarta precios
    nulos o <= 0.
    """
    nombre_producto = raw.get("productName") or raw.get("name") or ""
    marca = raw.get("brand") or None
    categoria, subcategoria = _categoria(raw)
    categoria_id = str(raw.get("categoryId") or "") or None
    link = raw.get("link")
    slug = raw.get("linkText")
    url = link or (f"https://{host}/{slug}/p" if host and slug else None)
    fecha_pub = _fecha_ms(raw.get("releaseDate"))

    ofertas: list[Oferta] = []
    for item in raw.get("items") or []:
        sku = str(item.get("itemId") or "")
        if not sku:
            continue
        nombre = item.get("nameComplete") or item.get("name") or nombre_producto
        refs = item.get("referenceId") or []
        codigo_ref = next(
            (str(r.get("Value")) for r in refs if r.get("Value")), None
        )
        imagenes = item.get("images") or []
        imagen = imagenes[0].get("imageUrl") if imagenes else None
        for seller in item.get("sellers") or []:
            offer = seller.get("commertialOffer") or {}
            precio = _a_float(offer.get("Price"))
            if precio is None or precio <= 0:
                continue
            ofertas.append(
                Oferta(
                    producto=Producto(
                        cadena=cadena_id,
                        sku_id=sku,
                        nombre=nombre,
                        ean=str(item.get("ean") or "") or None,
                        marca=marca,
                        categoria=categoria,
                        categoria_id=categoria_id,
                        subcategoria=subcategoria,
                        unidad=item.get("measurementUnit") or None,
                        multiplicador=_a_float(item.get("unitMultiplier")),
                        url=url,
                        imagen=imagen,
                        descripcion=_sin_html(raw.get("description")),
                        codigo_ref=codigo_ref,
                        producto_ext_id=str(raw.get("productId") or "") or None,
                        fecha_publicacion=fecha_pub,
                    ),
                    precio=precio,
                    precio_lista=_a_float(offer.get("ListPrice")),
                    stock=_a_int(offer.get("AvailableQuantity")),
                    moneda="ARS",
                    disponible=(offer.get("AvailableQuantity") or 0) > 0,
                )
            )
            break  # un precio por ítem (primer seller con oferta válida)
    return ofertas
