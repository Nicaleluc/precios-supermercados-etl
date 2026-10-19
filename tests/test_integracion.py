"""Test de integración con SQL Server (se salta si no hay conexión)."""
from __future__ import annotations

import pytest

from etl.conn.db import get_connection


def _db_ok() -> bool:
    try:
        c = get_connection()
        c.close()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_ok(), reason="sin conexión a SQL Server")


def test_tablas_del_dominio_existen():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT name FROM sys.tables WHERE name LIKE ?", ("D_Precio%",))
    nombres = {r[0] for r in cur.fetchall()}
    conn.close()
    assert {"D_PrecioCadena", "D_PrecioSucursal", "D_PrecioProducto",
            "D_PrecioOferta"} <= nombres


def test_producto_tiene_categoria_canonica():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COL_LENGTH('dbo.D_PrecioProducto', 'CategoriaCanonica')")
    assert cur.fetchone()[0] is not None
    conn.close()
