"""Cliente de la API de "La Coope en Casa" (Cooperativa Obrera).

NO es VTEX: es una API REST propia, pública (sin auth), con envelope
`{estado, mensaje, datos, ticket}` (estado=1 OK, estado=3 error).
Base: `https://api.lacoopeencasa.coop`

Endpoints usados:
  GET /api/buscar?q=<term>                    -> {producto, marca, categoria}
  GET /api/articulo/detalle?cod_interno=<id>  -> ficha completa
  GET /api/categorias/arbol                   -> árbol de categorías

Es la API de producción de la Coope (no documentada): usarla con respeto.
"""
from __future__ import annotations

import time

import requests

from config.settings import HTTP_PAUSA, HTTP_REINTENTOS, HTTP_TIMEOUT, USER_AGENT


class CoopeError(RuntimeError):
    """Falla al consultar la API de la Coope (red, status o `estado != 1`)."""


class CoopeClient:
    def __init__(self, host: str, *, esquema: str = "https"):
        self.host = host
        self.esquema = esquema
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        })

    def _peticion(self, metodo: str, path: str, *, params: dict | None = None,
                  json_body: dict | None = None) -> object:
        url = f"{self.esquema}://{self.host}{path}"
        ultimo_error: Exception | None = None
        for intento in range(1, HTTP_REINTENTOS + 1):
            try:
                resp = self._session.request(
                    metodo, url, params=params, json=json_body, timeout=HTTP_TIMEOUT)
                if resp.status_code == 429:
                    raise CoopeError("429 rate limit")
                resp.raise_for_status()
                data = resp.json()
                if isinstance(data, dict) and data.get("estado") != 1:
                    raise CoopeError(f"estado={data.get('estado')}: {data.get('mensaje')}")
                return data.get("datos") if isinstance(data, dict) else data
            except (requests.RequestException, ValueError, CoopeError) as exc:
                ultimo_error = exc
                if intento < HTTP_REINTENTOS:
                    time.sleep(HTTP_PAUSA * intento)
        raise CoopeError(f"{metodo} {url} falló tras {HTTP_REINTENTOS} intentos: {ultimo_error}")

    def _get(self, path: str, params: dict) -> object:
        return self._peticion("GET", path, params=params)

    def _post(self, path: str, body: dict) -> object:
        return self._peticion("POST", path, json_body=body)

    def buscar(self, termino: str) -> list[dict]:
        """Listado por término (top 5): cod_interno, descripcion, marca_desc."""
        datos = self._get("/api/buscar", {"q": termino}) or {}
        return datos.get("producto", []) if isinstance(datos, dict) else []

    def detalle(self, cod_interno: str) -> dict:
        """Ficha completa de un artículo (precio, promo, stock, categoría)."""
        return self._get("/api/articulo/detalle", {"cod_interno": cod_interno}) or {}

    def categorias_arbol(self) -> list[dict]:
        return self._get("/api/categorias/arbol", {}) or []

    def localidades(self, *, exclusivas: int = 1) -> list[dict]:
        """Localidades servidas (con coordenadas). `exclusivas=1` = las online."""
        return self._get("/api/localidades", {"exclusivas": exclusivas}) or []

    # --- búsqueda paginada (el `buscar` de arriba es el autocomplete top-5) ---
    _FILTROS_BASE = {
        "preciomenor": -1, "preciomayor": -1, "categoria": [], "marca": [],
        "tipo_seleccion": "busqueda", "tipo_relacion": "busqueda",
        "filtros_gramaje": [], "filtros_descuento": [], "ofertas": False,
        "modificado": False, "primer_filtro": "",
    }

    def buscar_paginado(self, termino: str, *, max_paginas: int = 50) -> list[dict]:
        """Todos los artículos que matchean el término (8 por página)."""
        filtros = dict(self._FILTROS_BASE)
        filtros["termino"] = termino
        out: list[dict] = []
        for pagina in range(1, max_paginas + 1):
            datos = self._post(
                "/api/articulos/pagina_busqueda",
                {"pagina": pagina, "filtros": filtros, "orden": 0},
            )
            if not isinstance(datos, dict):
                break
            arts = datos.get("articulos") or []
            out.extend(arts)
            total = datos.get("cantidad_articulos")
            if not arts or (total is not None and len(out) >= total):
                break
        return out

    def categorias_nombres(self) -> list[str]:
        """Nombres de todas las categorías del árbol (para recorrer por término)."""
        acc: list[str] = []

        def walk(nodes):
            for n in nodes or []:
                d = n.get("descripcion")
                if d:
                    acc.append(d)
                walk(n.get("hijos"))

        walk(self.categorias_arbol())
        return acc

    def cerrar(self) -> None:
        self._session.close()
