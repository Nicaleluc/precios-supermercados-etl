"""Transform: ficha de la Coope (`/api/articulo/detalle`) -> `Oferta`.

La API de la Coope NO expone EAN ni URL de producto; sí precio, promos,
precio unitario, categoría jerárquica, marca, gramaje y stock.
"""
from __future__ import annotations

from datetime import date, datetime

from .modelos import Oferta, Producto


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


def _a_bool(valor, default: bool = False) -> bool:
    if isinstance(valor, bool):
        return valor
    if valor is None:
        return default
    return str(valor).strip().lower() in ("1", "true", "si", "sí", "t", "yes")


def _fecha(valor) -> date | None:
    if not valor:
        return None
    s = str(valor).strip()[:10]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def normalizar(cadena_id: str, d: dict) -> Oferta | None:
    """Convierte una ficha de la Coope en `Oferta` (None si no tiene precio)."""
    if not d:
        return None
    cod = str(d.get("cod_interno") or "")
    precio = _a_float(d.get("precio"))
    if not cod or precio is None or precio <= 0:
        return None

    niveles = [
        d.get("categoria_inicial_desc"),
        d.get("categoria_secundaria_desc"),
        d.get("categoria_terciaria_desc"),
    ]
    niveles = [n for n in niveles if n]
    categoria = " > ".join(niveles) or (d.get("categoria_desc") or None)
    subcategoria = niveles[-1] if niveles else (d.get("categoria_desc") or None)

    return Oferta(
        producto=Producto(
            cadena=cadena_id,
            sku_id=cod,
            nombre=d.get("descripcion") or "",
            ean=None,  # la API no expone EAN
            marca=d.get("marca_desc") or None,
            categoria=categoria,
            categoria_id=str(d.get("id_categoria") or "") or None,
            subcategoria=subcategoria,
            unidad=d.get("unimed_desc") or None,
            contenido_neto=_a_float(d.get("gramaje")),
            imagen=d.get("imagen") or None,
            descripcion=d.get("desc_larga") or None,
        ),
        precio=precio,
        precio_lista=_a_float(d.get("precio_anterior")),
        precio_sin_imp=_a_float(d.get("precio_sin_impuestos")),
        precio_unitario=_a_float(d.get("precio_unitario")),
        en_promo=_a_bool(d.get("existe_promo")),
        descripcion_promo=d.get("descripcion_promo") or None,
        promo_desde=_fecha(d.get("vigencia_promo_desde")),
        promo_hasta=_fecha(d.get("vigencia_promo")),
        descuento_porc=_a_float(d.get("descuento_porcentaje_promo")),
        stock=_a_int(d.get("stock")),
        moneda="ARS",
        disponible=_a_bool(d.get("disponibilidad"), default=True),
    )
