"""Comparar precios de una lista de compras entre supermercados.

Dos fuentes:
  * `--bd` (default): lee el store en SQL Server (tablas `D_Precio*`) —
    incluye TODAS las cadenas cargadas (VTEX, Coope, La Banderita).
  * `--vivo`: consulta los sitios VTEX en el momento (sin usar la base).

Uso:
  py -u -m cli.comparar leche yerba aceite          # sobre la base
  py -u -m cli.comparar --vivo leche pan            # en vivo (solo VTEX)
  py -u -m cli.comparar --ean 7790742123456         # un EAN en todas las cadenas
"""
from __future__ import annotations

import argparse
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from config.settings import CADENAS, POR_PAGINA
from etl.dominios.comparador.canasta import cotizar, recomendar
from etl.dominios.comparador.cruzado import comparar as comparar_bd, equivalentes, por_ean
from etl.dominios.precios.constants import CADENAS as REGISTRO
from etl.dominios.precios.constants import TERMINOS_DEFAULT

_ANCHO = 18
_COL = 16


def _plata(valor: float) -> str:
    return f"${valor:,.0f}"


def _tabla(cotizaciones, activas, nombres) -> None:
    enc = "Termino".ljust(_ANCHO)
    for cid in activas:
        enc += nombres.get(cid, cid)[:_COL - 1].rjust(_COL)
    enc += "  Mejor"
    print(enc)
    print("-" * len(enc))
    for cot in cotizaciones:
        fila = cot.termino[:_ANCHO - 1].ljust(_ANCHO)
        for cid in activas:
            o = cot.por_cadena.get(cid)
            fila += (_plata(o.precio).rjust(_COL) if o else "-".rjust(_COL))
        m = cot.mejor
        if m:
            fila += f"  {nombres.get(m[0], m[0])} {_plata(m[1].precio)}"
        else:
            fila += "  sin match"
        print(fila)


def _totales(cotizaciones, nombres) -> None:
    rec = recomendar(cotizaciones)
    print()
    for cid, total in sorted(rec["totales"].items(), key=lambda kv: kv[1]):
        print(f"  {nombres.get(cid, cid):<22} total {_plata(total)}")
    print(f"  {'Carrito dividido':<22} total {_plata(rec['split'])}")
    if rec["cadena_mas_barata"]:
        print(f"  Cadena más barata para todo: {nombres.get(rec['cadena_mas_barata'])}")
    if rec["ahorro_vs_mejor_cadena"] > 0:
        print(f"  Ahorro si dividís el carrito: {_plata(rec['ahorro_vs_mejor_cadena'])}")


def _nombres_bd(cur) -> dict[str, str]:
    cur.execute("SELECT Codigo, Nombre FROM dbo.D_PrecioCadena")
    return {cod: nom for cod, nom in cur.fetchall()}


def _modo_bd(args) -> int:
    from etl.conn.db import get_connection

    conn = get_connection()
    cur = conn.cursor()
    nombres = _nombres_bd(cur)
    cadenas = args.cadenas or None

    if args.ean:
        print(f"EAN {args.ean} por cadena:")
        opciones = por_ean(cur, args.ean, cadenas)
        if not opciones:
            print("  (sin datos para ese EAN)")
        for o in sorted(opciones, key=lambda x: x.precio):
            print(f"  {nombres.get(o.cadena, o.cadena):<22} {_plata(o.precio):>10}  {o.nombre[:40]}")
        conn.close()
        return 0

    if args.producto:
        print(f"Equivalentes de '{args.producto}':")
        eq = equivalentes(cur, args.producto, args.marca, cadenas)
        if not eq:
            print("  (sin equivalentes por encima del umbral)")
        for cid, (score, o) in sorted(eq.items(), key=lambda kv: kv[1][1].precio):
            print(f"  {nombres.get(cid, cid):<22} {_plata(o.precio):>10} "
                  f"({score:.0%})  {o.nombre[:38]}")
        conn.close()
        return 0

    terminos = args.terminos or list(TERMINOS_DEFAULT)
    cotizaciones = comparar_bd(cur, terminos, cadenas, por_unidad=args.por_unidad)
    activas = cadenas or sorted({c for cot in cotizaciones for c in cot.por_cadena})
    conn.close()
    if not activas:
        print("[!] No hay datos en la base. Corré cli.importar_precios primero.")
        return 1
    _tabla(cotizaciones, activas, nombres)
    _totales(cotizaciones, nombres)
    return 0


def _modo_vivo(args) -> int:
    terminos = args.terminos or list(TERMINOS_DEFAULT)
    ids = args.cadenas or CADENAS
    activas = [c for c in ids if REGISTRO.get(c) and REGISTRO[c].host_api]
    if not activas:
        print("[!] No hay cadenas con host confirmado para comparar en vivo.")
        return 1
    cotizaciones = cotizar(ids, terminos, por_pagina=args.por_pagina)
    nombres = {cid: REGISTRO[cid].nombre for cid in REGISTRO}
    _tabla(cotizaciones, activas, nombres)
    _totales(cotizaciones, nombres)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compara una lista de compras entre cadenas (base o en vivo).")
    parser.add_argument("terminos", nargs="*", help="lo que hay que comprar")
    parser.add_argument("--vivo", action="store_true",
                        help="Consultar los sitios VTEX en vivo (default: leer la base).")
    parser.add_argument("--cadena", action="append", dest="cadenas",
                        help="id de cadena (repetible).")
    parser.add_argument("--ean", help="Comparar un EAN puntual entre cadenas.")
    parser.add_argument("--producto", help="Equivalentes (fuzzy) de un producto entre cadenas.")
    parser.add_argument("--marca", help="Marca para desempatar --producto.")
    parser.add_argument("--por-unidad", action="store_true",
                        help="Elegir el más barato por kg/l (no por precio absoluto).")
    parser.add_argument("--por-pagina", type=int, default=POR_PAGINA)
    args = parser.parse_args()
    return _modo_vivo(args) if args.vivo else _modo_bd(args)


if __name__ == "__main__":
    raise SystemExit(main())
