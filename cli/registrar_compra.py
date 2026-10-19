"""Registrar una compra en `D_Compra` + `D_CompraDetalle`.

Uso:
  py -u -m cli.registrar_compra --comercio "Verdulería" --total 10000 ^
      --item "Mandarina:1:kg" --item "Kiwi:0.5:kg" --item "Frutilla:0.25:kg" ^
      --item "Banana:3:un" --item "Brócoli:1:un" --item "Chaucha:0.25:kg"

  py -u -m cli.registrar_compra --comercio "Coto" --total 25000 --json compra.json

`--item` admite precio unitario opcional (4to campo, $/kg o $/un):
      --item "Mandarina:1:kg:1299" --item "Kiwi:0.5:kg:7999"

JSON:
  {"comercio":"...", "total":0, "fecha":"YYYY-MM-DD",
   "items":[{"item":"Mandarina","cantidad":1,"unidad":"kg","precio_unitario":1299}]}
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from etl.conn.db import get_connection
from etl.dominios.precios.categorias import canonica

_DDL = (
    """
    IF NOT EXISTS (SELECT 1 FROM sys.objects
        WHERE object_id = OBJECT_ID(N'dbo.D_Compra') AND type = N'U')
    CREATE TABLE dbo.D_Compra (
        CompraId int IDENTITY(1,1) NOT NULL,
        Fecha date NOT NULL, Comercio nvarchar(120) NOT NULL,
        Total decimal(18,2) NOT NULL, Notas nvarchar(400) NULL,
        FechaCarga datetime2 NOT NULL DEFAULT (SYSDATETIME()),
        CONSTRAINT PK_D_Compra PRIMARY KEY CLUSTERED (CompraId))
    """,
    """
    IF NOT EXISTS (SELECT 1 FROM sys.objects
        WHERE object_id = OBJECT_ID(N'dbo.D_CompraDetalle') AND type = N'U')
    CREATE TABLE dbo.D_CompraDetalle (
        DetalleId int IDENTITY(1,1) NOT NULL,
        CompraId int NOT NULL, Item nvarchar(120) NOT NULL,
        Cantidad decimal(10,3) NOT NULL, Unidad varchar(10) NOT NULL,
        PrecioUnitario decimal(18,2) NULL, Subtotal decimal(18,2) NULL,
        Ean varchar(14) NULL, ProductoId bigint NULL,
        CategoriaCanonica varchar(40) NULL, Notas nvarchar(200) NULL,
        CONSTRAINT PK_D_CompraDetalle PRIMARY KEY CLUSTERED (DetalleId),
        CONSTRAINT FK_D_CompraDetalle_Compra FOREIGN KEY (CompraId)
            REFERENCES dbo.D_Compra (CompraId))
    """,
)
_ALTERS = (
    ("PrecioUnitario", "decimal(18,2) NULL"),
    ("Subtotal", "decimal(18,2) NULL"),
    ("Ean", "varchar(14) NULL"),
    ("ProductoId", "bigint NULL"),
    ("CategoriaCanonica", "varchar(40) NULL"),
)


def _num(txt) -> float:
    return float(str(txt).replace(",", "."))


def _parse_item(txt: str) -> tuple[str, float, str, float | None]:
    partes = txt.split(":")
    if len(partes) not in (3, 4):
        raise SystemExit(f"Item inválido '{txt}'. Usá Nombre:Cantidad:Unidad[:PrecioUnitario]")
    nombre, cant, unidad = partes[0].strip(), partes[1].strip(), partes[2].strip().lower()
    if unidad not in ("kg", "un"):
        raise SystemExit(f"Unidad inválida '{unidad}' (kg|un)")
    precio = _num(partes[3]) if len(partes) == 4 and partes[3].strip() else None
    return nombre, _num(cant), unidad, precio


def main() -> int:
    p = argparse.ArgumentParser(description="Registrar una compra.")
    p.add_argument("--fecha", default=date.today().isoformat())
    p.add_argument("--comercio")
    p.add_argument("--total")
    p.add_argument("--notas")
    p.add_argument("--item", action="append", dest="items", default=[],
                   help="Nombre:Cantidad:Unidad[:PrecioUnitario] (repetible)")
    p.add_argument("--json")
    args = p.parse_args()

    if args.json:
        data = json.load(open(args.json, encoding="utf-8"))
        comercio, total = data["comercio"], _num(data["total"])
        fecha, notas = data.get("fecha", args.fecha), data.get("notas", args.notas)
        items = [(i["item"], _num(i["cantidad"]), i["unidad"],
                  _num(i["precio_unitario"]) if i.get("precio_unitario") else None)
                 for i in data["items"]]
    else:
        if not args.comercio or not args.total:
            p.error("indicá --comercio y --total (o --json)")
        comercio, total, fecha, notas = args.comercio, _num(args.total), args.fecha, args.notas
        items = [_parse_item(t) for t in args.items]

    if not items:
        p.error("agregá al menos un --item")

    conn = get_connection()
    cur = conn.cursor()
    for ddl in _DDL:
        cur.execute(ddl)
    for col, tipo in _ALTERS:
        cur.execute(
            f"IF COL_LENGTH('dbo.D_CompraDetalle', ?) IS NULL "
            f"ALTER TABLE dbo.D_CompraDetalle ADD [{col}] {tipo}", (col,))
    conn.commit()

    cur.execute(
        "INSERT INTO dbo.D_Compra (Fecha, Comercio, Total, Notas) "
        "OUTPUT inserted.CompraId VALUES (?, ?, ?, ?)",
        (fecha, comercio, total, notas),
    )
    compra_id = int(cur.fetchone()[0])
    filas = []
    for nombre, cant, unidad, precio in items:
        subtotal = round(cant * precio, 2) if precio is not None else None
        filas.append((compra_id, nombre, cant, unidad, precio, subtotal,
                      canonica(nombre)))
    cur.executemany(
        "INSERT INTO dbo.D_CompraDetalle "
        "(CompraId, Item, Cantidad, Unidad, PrecioUnitario, Subtotal, CategoriaCanonica) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        filas,
    )
    conn.commit()
    conn.close()
    print(f"[OK] compra #{compra_id}: {comercio} ${total:,.2f} ({len(items)} ítems)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
