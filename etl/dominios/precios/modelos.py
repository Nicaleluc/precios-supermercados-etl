"""Modelo de dominio: producto y oferta normalizados."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Producto:
    """Producto (SKU) de una cadena, normalizado entre cadenas."""

    cadena: str
    sku_id: str
    nombre: str
    ean: str | None = None
    marca: str | None = None
    categoria: str | None = None       # path completo (VTEX) o jerarquía (Coope)
    categoria_id: str | None = None
    subcategoria: str | None = None    # último nivel del path
    unidad: str | None = None
    multiplicador: float | None = None
    contenido_neto: float | None = None
    url: str | None = None
    imagen: str | None = None
    descripcion: str | None = None
    codigo_ref: str | None = None
    producto_ext_id: str | None = None
    fecha_publicacion: date | None = None


@dataclass(frozen=True)
class Oferta:
    """Precio observado de un producto en una fecha."""

    producto: Producto
    precio: float
    precio_lista: float | None = None
    precio_sin_imp: float | None = None
    precio_unitario: float | None = None
    en_promo: bool = False
    descripcion_promo: str | None = None
    promo_desde: date | None = None
    promo_hasta: date | None = None
    descuento_porc: float | None = None
    stock: int | None = None
    moneda: str = "ARS"
    disponible: bool = True
    fecha: date | None = None
