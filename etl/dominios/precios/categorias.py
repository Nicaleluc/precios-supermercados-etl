"""Categoría canónica entre cadenas.

Cada cadena trae su propio árbol de categorías (incluso con nicho distinto:
"Frescos > Leches > Chocolatada" vs "Lácteos"). Esta capa las mapea a un set
reducido y estable para agrupar/comparar por rubro. Vive en `precios/` porque
es parte del modelo de producto (y `repository` la usa al hacer upsert).
"""
from __future__ import annotations

import re
import unicodedata

CANONICAS: tuple[str, ...] = (
    "Lácteos", "Almacén", "Bebidas", "Carnes", "Frutas y Verduras",
    "Panificados", "Congelados", "Limpieza", "Perfumería", "Otros",
)

_REGLAS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Lácteos", ("lacte", "leche", "queso", "yogur", "manteca", "crema",
                 "ricota", "dulce de leche", "postre")),
    ("Bebidas", ("bebida", "gaseosa", "agua", "jugo", "cerveza", "vino",
                 "aperitivo", "sidra", "bebidas blancas", "energizante")),
    ("Carnes", ("carne", "pollo", "pata", "muslo", "cerdo", "vaca", "pescado",
                "merluza", "salmon", "embutido", "fiambre", "chacinado")),
    ("Frutas y Verduras", ("fruta", "verdura", "hortaliza", "tomate", "papa",
                           "cebolla", "manzana", "banana", "limon", "naranja",
                           "mandarina", "kiwi", "frutilla", "brocoli", "brócoli",
                           "chaucha", "lechuga", "zanahoria", "pera", "uva",
                           "durazno", "anana", "sandia", "melon", "zapallo",
                           "morron", "berenjena", "pepino", "acelga", "espinaca",
                           "puerro", "repollo", "coliflor", "remolacha", "apio")),
    ("Panificados", ("pan ", "panificado", "factura", "galletita", "budin",
                     "torta", "bizcochuelo", "harina")),
    ("Congelados", ("congelado", "helado", "congelad")),
    ("Limpieza", ("limpieza", "detergente", "lavandina", "jabon", "limpiador",
                  "suavizante", "papel higienico", "esponja")),
    ("Perfumería", ("perfum", "higiene", "shampoo", "desodorante", "jabon de tocador",
                    "colon", "crema de enjuague", "pasta dental")),
    ("Almacén", ("almacen", "desayuno", "yerba", "cafe", "aceite", "vinagre",
                 "arroz", "fideo", "pasta seca", "azucar", "sal", "conserva",
                 "legumbre", "enlatado", "reposteria", "condimento", "salsa")),
)


def _norm(texto) -> str:
    s = unicodedata.normalize("NFKD", texto or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9 ]", " ", s.lower())
    return re.sub(r"\s+", " ", s).strip()


def canonica(*textos) -> str:
    """Devuelve la categoría canónica a partir de categoría/subcategoría/nombre."""
    blob = _norm(" ".join(t for t in textos if t))
    if not blob:
        return "Otros"
    for canon, claves in _REGLAS:
        if any(k in blob for k in claves):
            return canon
    return "Otros"
