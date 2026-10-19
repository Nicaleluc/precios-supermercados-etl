"""Comparador de canasta.

Dada una lista de lo que hay que comprar (términos o EAN), consulta cada
cadena habilitada y responde:
  * qué producto conviene por ítem (el más barato entre cadenas), y
  * el total por cadena y el total "carrito dividido" (mínimo por ítem).

Consulta en vivo (mismo cliente VTEX del extract), no contra el store.
"""
from __future__ import annotations

from dataclasses import dataclass

from etl.conn.vtex import VtexClient, VtexError
from etl.dominios.precios.constants import CADENAS
from etl.dominios.precios.modelos import Oferta
from etl.dominios.precios.normalizar import normalizar


@dataclass
class Cotizacion:
    termino: str
    por_cadena: dict[str, Oferta | None]

    @property
    def mejor(self) -> tuple[str, Oferta] | None:
        """Cadena y oferta más baratas para el término (None si nadie tiene)."""
        disponibles = {c: o for c, o in self.por_cadena.items() if o is not None}
        if not disponibles:
            return None
        cadena = min(disponibles, key=lambda c: disponibles[c].precio)
        return cadena, disponibles[cadena]


def _mejor_de_cadena(cliente: VtexClient, cadena_id: str, termino: str, por_pagina: int) -> Oferta | None:
    try:
        crudos = cliente.buscar_termino(termino, pagina=1, por_pagina=por_pagina)
    except VtexError:
        return None
    ofertas: list[Oferta] = []
    for producto in crudos:
        ofertas.extend(normalizar(cadena_id, producto))
    disponibles = [o for o in ofertas if o.disponible and o.precio > 0]
    if not disponibles:
        return None
    return min(disponibles, key=lambda o: o.precio)


def cotizar(ids_cadena, terminos, *, por_pagina: int = 50) -> list[Cotizacion]:
    """Cotiza cada término en cada cadena habilitada con `host` confirmado."""
    clientes: dict[str, VtexClient] = {}
    for cid in ids_cadena:
        cadena = CADENAS.get(cid)
        if cadena and cadena.host_api:
            clientes[cid] = VtexClient(cadena.host_api)

    cotizaciones: list[Cotizacion] = []
    try:
        for termino in terminos:
            por_cadena = {
                cid: _mejor_de_cadena(cliente, cid, termino, por_pagina)
                for cid, cliente in clientes.items()
            }
            cotizaciones.append(Cotizacion(termino=termino, por_cadena=por_cadena))
    finally:
        for cliente in clientes.values():
            cliente.cerrar()
    return cotizaciones


def recomendar(cotizaciones: list[Cotizacion]) -> dict:
    """Totales por cadena + total del carrito dividido + ahorro estimado."""
    totales: dict[str, float] = {}
    for cot in cotizaciones:
        for cid, oferta in cot.por_cadena.items():
            if oferta is not None:
                totales[cid] = totales.get(cid, 0.0) + oferta.precio

    split = 0.0
    for cot in cotizaciones:
        if cot.mejor is not None:
            split += cot.mejor[1].precio

    completo_mas_barato = min(totales.values()) if totales else 0.0
    return {
        "totales": totales,
        "split": split,
        "cadena_mas_barata": (
            min(totales, key=lambda c: totales[c]) if totales else None
        ),
        "ahorro_vs_mejor_cadena": max(completo_mas_barato - split, 0.0),
    }
