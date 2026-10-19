"""Importar precios de supermercados al store local.

Uso:
  py -u -m cli.importar_precios
  py -u -m cli.importar_precios --cadena vea --termino leche --termino yerba
  py -u -m cli.importar_precios --paginas 3
"""
from __future__ import annotations

import argparse
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from config.settings import CADENAS, MAX_PAGINAS, POR_PAGINA
from etl.dominios.precios.importer import cargar


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract de catálogos VTEX -> store local SQLite."
    )
    parser.add_argument(
        "--cadena", action="append", dest="cadenas",
        help="id de cadena (repetible). Default: CADENAS del .env.",
    )
    parser.add_argument(
        "--termino", action="append", dest="terminos",
        help="término de búsqueda (repetible). Default: semilla de constants.py.",
    )
    parser.add_argument("--por-pagina", type=int, default=POR_PAGINA,
                        help=f"Resultados por página (default {POR_PAGINA}).")
    parser.add_argument("--paginas", type=int, default=MAX_PAGINAS,
                        help=f"Páginas máximas por término (default {MAX_PAGINAS}).")
    parser.add_argument("--catalogo", action="store_true",
                        help="Recorrer TODO el catálogo VTEX por categoría (no por término).")
    parser.add_argument("--cat-paginas", type=int, default=50,
                        help="Páginas máximas por categoría/marca en modo --catalogo.")
    parser.add_argument("--cat-marcas", type=int, default=None,
                        help="La Banderita: limitar a N marcas en modo --catalogo (prueba).")
    parser.add_argument("--cat-terminos", type=int, default=None,
                        help="Coope: limitar a N categorías-término en modo --catalogo (prueba).")
    parser.add_argument("--ean-ficha", action="store_true",
                        help="La Banderita: traer el EAN abriendo cada ficha (1 request c/u).")
    args = parser.parse_args()

    stats = cargar(
        args.cadenas or CADENAS,
        args.terminos,
        por_pagina=args.por_pagina,
        max_paginas=args.paginas,
        catalogo=args.catalogo,
        cat_max_paginas=args.cat_paginas,
        cat_marcas=args.cat_marcas,
        cat_terminos=args.cat_terminos,
        ean_ficha=args.ean_ficha,
    )
    print(
        f"[OK] cadenas={stats.cadenas} terminos={stats.terminos} "
        f"ofertas={stats.ofertas} errores={stats.errores}"
    )
    if stats.salteadas:
        print(f"[!] salteadas: {', '.join(stats.salteadas)}")
    return 0 if stats.cadenas else 1


if __name__ == "__main__":
    raise SystemExit(main())
