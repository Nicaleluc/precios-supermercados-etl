"""Scraper HTML de La Banderita (`www.labanderita.ar`), super local de Bahía Blanca.

WooCommerce con la REST deshabilitada (`wp-json` -> 404), sobre el tema
**Batitienda**. Fuentes:
  * `GET /shop?s=<term>`                 búsqueda por texto;
  * `GET /shop?brand=<slug>`             filtro por marca (server-side);
  * `GET /Products_Search/List_Scroll`   paginación (JSON: `rows` HTML + cursor).
El HTML trae un array JS con el **EAN** (best-effort) y la ficha del producto
(`getAccessedProductInfo`) trae EAN/medida/precio limpios.

Catálogo completo: se enumeran las ~400 marcas del shop y se pagina cada una.
"""
from __future__ import annotations

import json
import re
import time

import bs4
import requests

from config.settings import HTTP_PAUSA, HTTP_REINTENTOS, HTTP_TIMEOUT, USER_AGENT

_URL_SCROLL = "/Products_Search/List_Scroll"
_RE_EAN = re.compile(
    r"\{\s*a:\s*'(\d+)',\s*b:\s*'([^']*)',\s*c:\s*'([^']*)',\s*d:\s*'([^']*)'"
)
_RE_PRODINFO = re.compile(r"getAccessedProductInfo\(\)\s*\{\s*return\s*(\{[^}]*\})\s*;")
_RE_BRAND = re.compile(r"brand=([a-zA-Z0-9\-_]+)")


class LaBanderitaError(RuntimeError):
    """Falla al traer/parsear el HTML/JSON de La Banderita."""


def _sopa(html: str) -> bs4.BeautifulSoup:
    try:
        return bs4.BeautifulSoup(html, "lxml")
    except Exception:  # lxml opcional
        return bs4.BeautifulSoup(html, "html.parser")


def _texto(el) -> str | None:
    return el.get_text(" ", strip=True) if el is not None else None


def _norm(valor) -> str:
    return re.sub(r"\s+", " ", (valor or "").strip()).lower()


class LaBanderitaClient:
    def __init__(self, host: str, *, esquema: str = "https"):
        self.host = host
        self.esquema = esquema
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": USER_AGENT, "Accept": "text/html"})

    def _get(self, path: str, params: dict) -> requests.Response:
        url = f"{self.esquema}://{self.host}{path}"
        ultimo_error: Exception | None = None
        for intento in range(1, HTTP_REINTENTOS + 1):
            try:
                resp = self._session.get(url, params=params, timeout=HTTP_TIMEOUT)
                if resp.status_code == 429:
                    raise LaBanderitaError("429 rate limit")
                resp.raise_for_status()
                return resp
            except (requests.RequestException, LaBanderitaError) as exc:
                ultimo_error = exc
                if intento < HTTP_REINTENTOS:
                    time.sleep(HTTP_PAUSA * intento)
        raise LaBanderitaError(f"GET {url} falló tras {HTTP_REINTENTOS} intentos: {ultimo_error}")

    def _extraer(self, prod) -> dict | None:
        cont = prod.select_one(".product-list-item")
        pid = (cont.get("data-product") if cont else None) or ""
        precio_el = prod.select_one(".price > .amount") or prod.select_one(".price .amount")
        if not pid or precio_el is None:
            return None
        enlace = prod.select_one("a[href]")
        href = enlace.get("href") if enlace else None
        if href and href.startswith("/"):
            href = f"{self.esquema}://{self.host}{href}"
        img = prod.select_one("img")
        return {
            "producto_id": str(pid),
            "nombre": _texto(prod.select_one("h3.kw-details-title")),
            "marca": _texto(prod.select_one(".product-name")),
            "categoria": _texto(prod.select_one(".product-category")),
            "precio_txt": _texto(precio_el),
            "precio_lista_txt": _texto(prod.select_one(".price del .amount")),
            "precio_sin_imp_txt": _texto(prod.select_one(".price-without-taxes")),
            "url": href,
            "imagen": (img.get("data-src") or img.get("src")) if img else None,
            "ean": None,
        }

    def _ean_map(self, html: str) -> dict[str, str]:
        return {_norm(b): a for a, b, _c, _d in _RE_EAN.findall(html)}

    def _paginar(self, soup, items, *, search_text="", brand_name="",
                 max_paginas=20) -> list[dict]:
        ean_map = self._ean_map(str(soup))
        cursor_el = soup.select_one("#Cursor")
        cursor = cursor_el.get("value") if cursor_el else None
        base = {
            "GetNextPage": "false", "ProductCategoryName": "", "OrderBy": "",
            "SearchText": search_text, "BrandName": brand_name,
        }
        paginas = 1
        while cursor and paginas < max_paginas:
            data = self._get(_URL_SCROLL, {**base, "Cursor": cursor}).json()
            rows = _sopa(data.get("rows") or "")
            mas = [it for it in (self._extraer(p) for p in rows.select(".product")) if it]
            items.extend(mas)
            paginas += 1
            if data.get("isLastPage") or not mas:
                break
            cursor = data.get("cursor")
        for it in items:
            it["ean"] = ean_map.get(_norm(it.get("nombre")))
        return items

    def ean_de_producto(self, url: str) -> str | None:
        path = url.split(self.host, 1)[-1] if self.host in url else url
        try:
            html = self._get(path, {}).text
        except LaBanderitaError:
            return None
        m = _RE_PRODINFO.search(html)
        if not m:
            return None
        try:
            info = json.loads(m.group(1))
        except ValueError:
            return None
        return str(info.get("c") or "").strip() or None

    def _completar_ean(self, items) -> None:
        for it in items:
            if not it.get("ean") and it.get("url"):
                it["ean"] = self.ean_de_producto(it["url"])
                time.sleep(HTTP_PAUSA)

    def buscar(self, termino: str, *, max_paginas: int = 20,
               con_ean: bool = False) -> list[dict]:
        soup = _sopa(self._get("/shop", {"s": termino}).text)
        items = [it for it in (self._extraer(p) for p in soup.select(".product")) if it]
        items = self._paginar(soup, items, search_text=termino, max_paginas=max_paginas)
        if con_ean:
            self._completar_ean(items)
        return items

    def buscar_por_marca(self, slug: str, *, max_paginas: int = 20) -> list[dict]:
        soup = _sopa(self._get("/shop", {"brand": slug}).text)
        items = [it for it in (self._extraer(p) for p in soup.select(".product")) if it]
        return self._paginar(soup, items, brand_name=slug, max_paginas=max_paginas)

    def marcas(self) -> list[str]:
        """Slugs de marca del shop (~400). Cada uno filtra server-side."""
        html = self._get("/shop", {}).text
        return sorted(set(_RE_BRAND.findall(html)))

    def catalogo(self, *, max_paginas: int = 20, max_marcas: int | None = None,
                 pausa: float | None = None):
        """Genera TODO el catálogo recorriendo las marcas (1 request por marca+)."""
        pausa = HTTP_PAUSA if pausa is None else pausa
        vistos: set[str] = set()
        slugs = self.marcas()
        if max_marcas:
            slugs = slugs[:max_marcas]
        for slug in slugs:
            try:
                lote = self.buscar_por_marca(slug, max_paginas=max_paginas)
            except LaBanderitaError:
                continue
            for it in lote:
                pid = it["producto_id"]
                if pid in vistos:
                    continue
                vistos.add(pid)
                yield it
            time.sleep(pausa)

    def cerrar(self) -> None:
        self._session.close()
