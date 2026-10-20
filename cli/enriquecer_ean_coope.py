"""Enriquece los productos de la Cooperativa Obrera con su EAN.

La API de la Coope **no expone** el EAN, pero su autocomplete
(`/api/buscar?q=<EAN>`) **sí devuelve el producto** cuando se consulta por EAN.
Estrategia:

  1. Tomar los productos de la Coope sin EAN (SkuId, Nombre, Marca).
  2. Buscar candidatos EAN de las otras cadenas (VTEX/SEPA) por similitud de
     nombre (`matching.similitud`).
  3. Para el/los mejores candidatos, consultar la Coope por ese EAN; si el
     resultado apunta al **mismo SkuId**, setear el EAN.

Uso:
  py -u -m cli.enriquecer_ean_coope --limite 50 --dry-run
  py -u -m cli.enriquecer_ean_coope
"""
from __future__ import annotations

import argparse
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from etl.conn.coope import CoopeClient, CoopeError
from etl.conn.db import get_connection
from etl.dominios.comparador.matching import similitud
from etl.dominios.precios.constants import CADENAS

_COOPE = "cooperativa_obrera"


def _candidatos(cur) -> list[tuple[str, str, str]]:
    """(Ean, Nombre, Marca) distintos de las cadenas que sí exponen EAN."""
    cur.execute(
        """
        SELECT p.Ean, MAX(p.Nombre) AS Nombre, MAX(p.Marca) AS Marca
        FROM dbo.D_PrecioProducto p
        JOIN dbo.D_PrecioCadena ch ON ch.CadenaId = p.CadenaId
        WHERE ch.Codigo <> ? AND p.Ean IS NOT NULL AND p.Ean <> ''
        GROUP BY p.Ean
        """,
        (_COOPE,),
    )
    return [(e, n, m) for e, n, m in cur.fetchall()]


def _productos_coope(cur) -> list[tuple[str, str, str]]:
    cur.execute(
        """
        SELECT p.SkuId, p.Nombre, p.Marca
        FROM dbo.D_PrecioProducto p
        JOIN dbo.D_PrecioCadena ch ON ch.CadenaId = p.CadenaId
        WHERE ch.Codigo = ? AND (p.Ean IS NULL OR p.Ean = '')
        """,
        (_COOPE,),
    )
    return [(s, n, m) for s, n, m in cur.fetchall()]


def main() -> int:
    p = argparse.ArgumentParser(description="Mapear EAN en productos de la Coope.")
    p.add_argument("--limite", type=int, help="Máximo de productos Coope a procesar.")
    p.add_argument("--umbral", type=float, default=0.70,
                   help="Similitud mínima nombre Coope vs candidato (default 0.70).")
    p.add_argument("--pausa", type=float, default=0.2, help="Pausa entre requests (s).")
    p.add_argument("--dry-run", action="store_true", help="No actualiza, solo muestra.")
    args = p.parse_args()

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT CadenaId FROM dbo.D_PrecioCadena WHERE Codigo = ?", (_COOPE,))
    fila = cur.fetchone()
    if fila is None:
        print("[!] No existe la cadena cooperativa_obrera en la base.")
        return 1
    coope_id = int(fila[0])

    cands = _candidatos(cur)
    coope = _productos_coope(cur)
    if args.limite:
        coope = coope[:args.limite]
    print(f"Candidatos EAN: {len(cands)} | productos Coope sin EAN: {len(coope)}")

    cliente = CoopeClient(CADENAS[_COOPE].host_api)
    mapeados = 0
    revisados = 0
    try:
        for sku, nombre, marca in coope:
            revisados += 1
            # mejores candidatos por similitud de nombre
            ordenados = sorted(
                cands, key=lambda c: similitud(nombre, c[1]), reverse=True)[:3]
            elegido = None
            for ean, cand_nombre, _ in ordenados:
                if similitud(nombre, cand_nombre) < args.umbral:
                    continue
                try:
                    stubs = cliente.buscar(ean)
                except CoopeError:
                    continue
                time.sleep(args.pausa)
                if any(str(s.get("cod_interno")) == sku for s in stubs):
                    elegido = (ean, cand_nombre)
                    break
            if elegido is None:
                continue
            ean, cand_nombre = elegido
            print(f"  {sku:>8}  EAN {ean}  {nombre[:40]:40}  <=  {cand_nombre[:34]}")
            if not args.dry_run:
                cur.execute(
                    "UPDATE dbo.D_PrecioProducto SET Ean = ? "
                    "WHERE CadenaId = ? AND SkuId = ? AND (Ean IS NULL OR Ean = '')",
                    (ean, coope_id, sku),
                )
                mapeados += 1
                if mapeados % 20 == 0:
                    conn.commit()
        conn.commit()
    finally:
        cliente.cerrar()
        conn.close()

    print(f"[OK] revisados={revisados} mapeados={mapeados} "
          f"{'(dry-run)' if args.dry_run else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
