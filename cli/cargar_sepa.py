"""Cargar SEPA (Precios Claros) al store.

Uso:
  py -u -m cli.cargar_sepa --zip C:\\SEPA\\sepa_martes.zip --max-grupos 2 --limite 500
  py -u -m cli.cargar_sepa --auto                 # baja el ZIP del día y lo carga
  py -u -m cli.cargar_sepa --auto --dia Lunes
  py -u -m cli.cargar_sepa --zip ...                (COMPLETO: puede tardar)

`banderas.json` (opcional) mapea id_bandera -> nombre; sin él se usa el nombre
de `comercio.csv` (cada id_comercio+id_bandera queda como una cadena).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import unicodedata
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from etl.conn.sepa import cargar

_API = "https://datos.produccion.gob.ar/api/3/action/package_show?id=sepa-precios"
_DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]


def _norm(texto) -> str:
    s = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def _descargar(dia: str | None, cache_dir: Path | None) -> Path:
    import datetime

    import requests

    if not dia:
        dia = _DIAS[datetime.date.today().weekday()]
    data = requests.get(_API, timeout=30).json()
    recursos = data["result"]["resources"]
    objetivo = _norm(dia)
    cand = [r for r in recursos if _norm(r.get("name", "")).startswith(objetivo)]
    if not cand:
        cand = [r for r in recursos if "sepa" in _norm(r.get("url", ""))]
    if not cand:
        raise SystemExit(f"No encontré recurso SEPA para '{dia}'.")
    recurso = cand[0]

    cache = cache_dir or Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / "DELI" / "sepa"
    cache.mkdir(parents=True, exist_ok=True)
    destino = cache / f"sepa_{_norm(dia)}.zip"
    if destino.exists() and destino.stat().st_size > 1_000_000:
        edad_horas = (time.time() - destino.stat().st_mtime) / 3600
        if edad_horas < 20:  # el recurso del día se actualiza a diario
            print(f"[=] usando cache ({edad_horas:.0f}h): {destino}")
            return destino
    print(f"[>] descargando {recurso.get('name')} ...")
    with requests.get(recurso["url"], stream=True, timeout=600) as r:
        r.raise_for_status()
        with open(destino, "wb") as fh:
            for chunk in r.iter_content(1 << 20):
                fh.write(chunk)
    print(f"[OK] {destino} ({destino.stat().st_size / 1e6:.0f} MB)")
    return destino


def main() -> int:
    parser = argparse.ArgumentParser(description="Carga un ZIP de SEPA al store.")
    parser.add_argument("--zip", help="ZIP de SEPA (outer o inner).")
    parser.add_argument("--auto", action="store_true",
                        help="Descargar el ZIP del día (o --dia) desde datos.gob.ar.")
    parser.add_argument("--dia", help="Lunes..Domingo (para --auto).")
    parser.add_argument("--cache", help="Carpeta de cache de los ZIP (--auto).")
    parser.add_argument("--banderas", help="JSON id_bandera -> nombre (opcional).")
    parser.add_argument("--limite", type=int, help="Corta tras N precios (prueba).")
    parser.add_argument("--max-grupos", type=int, help="Procesa solo N inner ZIPs (prueba).")
    args = parser.parse_args()

    if args.auto:
        entrada = _descargar(args.dia, Path(args.cache) if args.cache else None)
    elif args.zip:
        entrada = Path(args.zip)
    else:
        parser.error("indicá --zip o --auto")

    banderas = None
    if args.banderas:
        banderas = json.load(open(args.banderas, encoding="utf-8"))

    stats = cargar(entrada, banderas=banderas, limite=args.limite,
                   max_grupos=args.max_grupos)
    print(f"[OK] grupos={stats['grupos']} cadenas={stats['cadenas']} "
          f"sucursales={stats['sucursales']} productos={stats['productos']} "
          f"precios={stats['precios']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
