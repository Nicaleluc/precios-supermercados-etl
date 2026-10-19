"""Cliente HTTP base para catálogos VTEX (storefront público).

La mayoría de los supermercados argentinos corre sobre VTEX. No hay API de
productos con credenciales: se usan los mismos endpoints públicos que llama
el front del sitio (Intelligent Search y Catalog Search). Los hosts y paths
por cadena viven en `etl/dominios/precios/constants.py`.

Referencia de endpoints (VTEX IO):
  - Intelligent Search: `GET /api/io/_v/api/intelligent-search/product_search/`
      ?query=<texto>&count=<n>&page=<p>
  - Catalog Search:     `GET /api/catalog_system/pub/products/search/`
      ?fq=alternateIds_Ean:<ean>

Nota: los endpoints no están versionados como API pública estable; si una
cadena los cambia, ajustar su entrada en constants.py.
"""
from __future__ import annotations

import time

import requests

from config.settings import HTTP_PAUSA, HTTP_REINTENTOS, HTTP_TIMEOUT, USER_AGENT


class VtexError(RuntimeError):
    """Falla al consultar el catálogo VTEX (red, status o JSON inválido)."""


class VtexClient:
    """Cliente mínimo de catálogo VTEX para una cadena concreta.

    `host` es el dominio del storefront (ej. `www.vea.com.ar`), sin esquema.
    """

    def __init__(self, host: str, *, esquema: str = "https"):
        self.host = host
        self.esquema = esquema
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        })

    def _get(self, path: str, params: dict) -> dict:
        url = f"{self.esquema}://{self.host}{path}"
        ultimo_error: Exception | None = None
        for intento in range(1, HTTP_REINTENTOS + 1):
            try:
                resp = self._session.get(url, params=params, timeout=HTTP_TIMEOUT)
                if resp.status_code == 429:
                    raise VtexError("429 rate limit")
                resp.raise_for_status()
                return resp.json()
            except (requests.RequestException, ValueError, VtexError) as exc:
                ultimo_error = exc
                if intento < HTTP_REINTENTOS:
                    time.sleep(HTTP_PAUSA * intento)
        raise VtexError(f"GET {url} falló tras {HTTP_REINTENTOS} intentos: {ultimo_error}")

    def buscar_termino(self, termino: str, *, pagina: int = 1, por_pagina: int = 50) -> list[dict]:
        """Busca productos por texto (Intelligent Search). Devuelve `products`."""
        data = self._get(
            "/api/io/_v/api/intelligent-search/product_search/",
            {"query": termino, "count": por_pagina, "page": pagina},
        )
        return data.get("products", []) or []

    def buscar_por_ean(self, ean: str) -> list[dict]:
        """Busca productos por EAN (Catalog Search). Devuelve la lista cruda."""
        data = self._get(
            "/api/catalog_system/pub/products/search/",
            {"fq": f"alternateIds_Ean:{ean}"},
        )
        return data or []

    def categorias_arbol(self) -> list[dict]:
        """Árbol de categorías (id, name, children)."""
        return self._get("/api/catalog_system/pub/category/tree/3", {}) or []

    def productos_por_categoria(self, category_id, *, desde: int = 0, hasta: int = 49) -> list[dict]:
        """Productos de una categoría (Catalog Search). Máx 50 por página."""
        return self._get(
            "/api/catalog_system/pub/products/search",
            {"fq": f"C:/{category_id}/", "_from": desde, "_to": hasta},
        ) or []

    def cerrar(self) -> None:
        self._session.close()
