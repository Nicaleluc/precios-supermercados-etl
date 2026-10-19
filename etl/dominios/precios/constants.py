"""Registro de cadenas soportadas.

`id` es la clave que se guarda en la columna `Cadena` del store. `host` es el
dominio del storefront (sin esquema). `api_host` es el host de la API cuando
difiere del storefront (caso DIA: front FastStore en el dominio propio, API en
la cuenta VTEX). `host_api` resuelve cuál usar.

`host=""` = cadena en el registro pero sin endpoint confirmado: el importador
la saltea con aviso.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Cadena:
    id: str
    nombre: str
    host: str
    api_host: str = ""
    tipo: str = "vtex"

    @property
    def host_api(self) -> str:
        """Host de la API VTEX (usa `api_host` si está, si no el storefront)."""
        return self.api_host or self.host


# Verificado en vivo 2026-10-18: las 6 primeras devuelven el mismo shape
# (brand/categoria/categoryId/ean/measurementUnit/imagen/precio al 100%).
CADENAS: dict[str, Cadena] = {
    "vea": Cadena(id="vea", nombre="Vea", host="www.vea.com.ar"),
    "jumbo": Cadena(id="jumbo", nombre="Jumbo", host="www.jumbo.com.ar"),
    "disco": Cadena(id="disco", nombre="Disco", host="www.disco.com.ar"),
    "carrefour": Cadena(id="carrefour", nombre="Carrefour", host="www.carrefour.com.ar"),
    "changomas": Cadena(
        id="changomas", nombre="Changomas (Más Online)", host="www.masonline.com.ar"
    ),
    "cordiez": Cadena(id="cordiez", nombre="Cordiez", host="www.cordiez.com.ar"),
    # DIA: el front (FastStore) no expone la API en su dominio; se usa la cuenta.
    "dia": Cadena(
        id="dia",
        nombre="DIA",
        host="www.supermercadosdia.com.ar",
        api_host="diaio.vtexcommercestable.com.br",
    ),
    # Makro: NO es VTEX (corregido 2026-10-18). Es WordPress (tema Divi) detrás
    # de Bunny CDN (makro-com-ar.b-cdn.net), sin WooCommerce Store API ni CPT
    # de productos -> las ofertas salen como imagen/PDF. Requiere scraping HTML.
    "makro": Cadena(id="makro", nombre="Makro", host=""),

    # Cadenas con presencia en Bahía Blanca SIN API de precios usable
    # (host="" -> el importador las saltea). Existen para la dimensión Sucursal:
    #   diarco/vital  -> WooCommerce sin Store API / sin precios.
    #   la_anonima    -> custom (.NET) + API propia a descubrir; SEPA la cubre.
    #   la_banderita  -> WooCommerce local de BB; REST off -> scraping HTML (implementado).
    "diarco": Cadena(id="diarco", nombre="Diarco", host="", tipo="woo"),
    "vital": Cadena(id="vital", nombre="Vital", host="", tipo="woo"),
    "la_anonima": Cadena(id="la_anonima", nombre="La Anónima", host="", tipo="custom"),
    "la_banderita": Cadena(
        id="la_banderita", nombre="La Banderita",
        host="www.labanderita.ar", tipo="la_banderita",
    ),
    # Cooperativa Obrera ("La Coope en Casa", lacoopeencasa.coop): NO es VTEX.
    # Sitio Angular + API REST propia (sin auth) en api.lacoopeencasa.coop,
    # envelope {estado, mensaje, datos, ticket}:
    #   GET /api/buscar?q=<term>                   -> listado (top 5)
    #   GET /api/articulo/detalle?cod_interno=<id> -> ficha completa (precio/promo/stock)
    #   GET /api/categorias/arbol                  -> arbol de categorias
    # Cliente: etl/conn/coope.py ; transform: normalizar_coope.py.
    "cooperativa_obrera": Cadena(
        id="cooperativa_obrera", nombre="Cooperativa Obrera",
        host="www.lacoopeencasa.coop", api_host="api.lacoopeencasa.coop",
        tipo="coope",
    ),
}

# Términos semilla del extract cuando no se pasan por CLI.
TERMINOS_DEFAULT: tuple[str, ...] = (
    "leche",
    "yerba",
    "aceite",
    "azucar",
    "fideos",
    "arroz",
    "harina",
    "cafe",
    "manteca",
    "pan",
)
