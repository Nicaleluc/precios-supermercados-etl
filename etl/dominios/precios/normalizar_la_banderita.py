"""Transform: producto crudo de La Banderita (HTML) -> `Oferta`.

Precios en formato AR (`$2.599` = miles, `$ 2.147,93` = decimales).
La Banderita no expone EAN en el listado.
"""
from __future__ import annotations

import re

from .modelos import Oferta, Producto


def _precio(txt) -> float | None:
    """Parsea un precio AR: `$2.599` -> 2599.0 ; `$ 2.147,93` -> 2147.93."""
    if not txt:
        return None
    s = re.sub(r"[^\d,\.]", "", str(txt))
    if not s:
        return None
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    elif re.match(r"^\d{1,3}(\.\d{3})+$", s):
        s = s.replace(".", "")  # separador de miles
    try:
        return float(s)
    except ValueError:
        return None


def normalizar(cadena_id: str, raw: dict) -> Oferta | None:
    """Convierte un producto crudo (dict) de La Banderita en `Oferta`."""
    if not raw:
        return None
    sku = str(raw.get("producto_id") or "")
    precio = _precio(raw.get("precio_txt"))
    if not sku or precio is None or precio <= 0:
        return None
    categoria = raw.get("categoria") or None
    return Oferta(
        producto=Producto(
            cadena=cadena_id,
            sku_id=sku,
            nombre=raw.get("nombre") or "",
            ean=raw.get("ean") or None,
            marca=raw.get("marca") or None,
            categoria=categoria,
            subcategoria=categoria,
            url=raw.get("url") or None,
            imagen=raw.get("imagen") or None,
        ),
        precio=precio,
        precio_lista=_precio(raw.get("precio_lista_txt")),
        precio_sin_imp=_precio(raw.get("precio_sin_imp_txt")),
        moneda="ARS",
        disponible=True,
    )
