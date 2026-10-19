"""Cargar sucursales (puntos de venta) a `D_PrecioSucursal`.

Uso:
  py -u -m cli.cargar_sucursales
  py -u -m cli.cargar_sucursales --sin-coope
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
from etl.dominios.precios.schema import ensure_tablas
from etl.dominios.precios.sucursales import cargar


def main() -> int:
    parser = argparse.ArgumentParser(description="Carga sucursales a D_PrecioSucursal.")
    parser.add_argument("--sin-coope", action="store_true",
                        help="No traer las localidades de la Coope (solo la semilla de BB).")
    args = parser.parse_args()

    conn = get_connection()
    cur = conn.cursor()
    ensure_tablas(cur, conn)
    stats = cargar(cur, conn, con_coope=not args.sin_coope)
    conn.close()
    print(f"[OK] bahia_blanca={stats['bahia_blanca']} "
          f"coope_localidades={stats['coope_localidades']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
