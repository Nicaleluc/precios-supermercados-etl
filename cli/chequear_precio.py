"""Chequear si un precio es "normal" usando SEPA como referencia.

Uso:
  py -u -m cli.chequear_precio --ean 7798338291803
  py -u -m cli.chequear_precio --ean 7798338291803 --precio 3190
  py -u -m cli.chequear_precio --ean 7798338291803 --cadena vea --cadena dia

Muestra el precio normal (mediana SEPA entre sucursales), min/max, y compara
el precio indicado y/o el de cada cadena cargada contra ese normal.
"""
from __future__ import annotations

import argparse
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from etl.conn.db import get_connection

_UMBRAL = 10.0  # % de tolerancia para considerar "normal"


def _comparar(precio: float, normal: float, etiqueta: str) -> None:
    diff = (precio - normal) / normal * 100 if normal else 0.0
    if abs(diff) <= _UMBRAL:
        estado = "normal"
    elif diff > 0:
        estado = "CARO"
    else:
        estado = "barato"
    print(f"  {etiqueta:22} ${precio:>10,.2f}  ({diff:+6.1f}% vs normal)  {estado}")


def main() -> int:
    p = argparse.ArgumentParser(description="Chequea un precio contra el normal de SEPA.")
    p.add_argument("--ean", required=True, help="Código de barras (EAN/GTIN).")
    p.add_argument("--precio", type=float, help="Precio puntual a comparar.")
    p.add_argument("--cadena", action="append", dest="cadenas",
                   help="Filtrar cadenas (repetible).")
    args = p.parse_args()

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT Ean, Nombre, N_Sucursales, PrecioNormal, PrecioMin, PrecioMax, "
        "PrecioReferencia, N_Promo FROM dbo.V_PrecioNormal WHERE Ean = ?",
        (args.ean,),
    )
    ref = cur.fetchone()
    if ref is None:
        print(f"[!] EAN {args.ean}: sin datos SEPA (o todavía no se cargó ese grupo).")
        conn.close()
        return 1

    ean, nombre, n_suc, normal, pmin, pmax, prefer, npromo = ref
    print(f"EAN {ean}  {nombre}")
    print(f"  SEPA: normal ${normal:,.2f} (mediana de {n_suc} sucursales; "
          f"min ${pmin:,.2f} / max ${pmax:,.2f}; ref ${prefer:,.2f}; promos {npromo})")

    if args.precio is not None:
        _comparar(args.precio, float(normal), "precio indicado")

    filtro = ""
    params: list = [args.ean]
    if args.cadenas:
        marcas = ",".join("?" * len(args.cadenas))
        filtro = f" AND ch.Codigo IN ({marcas})"
        params.extend(args.cadenas)
    cur.execute(
        "SELECT ch.Nombre, MIN(o.Precio) "
        "FROM dbo.D_PrecioOferta o "
        "JOIN dbo.D_PrecioProducto p ON p.ProductoId = o.ProductoId "
        "JOIN dbo.D_PrecioCadena ch ON ch.CadenaId = p.CadenaId "
        "WHERE p.Ean = ? AND o.Origen <> 'SEPA'" + filtro +
        " GROUP BY ch.Nombre ORDER BY MIN(o.Precio)",
        params,
    )
    filas = cur.fetchall()
    if filas:
        print("  Precios cargados (no SEPA):")
        for cad, precio in filas:
            _comparar(float(precio), float(normal), cad)
    else:
        print("  (sin precios no-SEPA cargados para ese EAN)")

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
