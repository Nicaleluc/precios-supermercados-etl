"""Conexión a SQL Server (tablas `D_Precio*`).

Estilo `deli/etl/conn/db.py`: pyodbc para el pipeline + SQLAlchemy opcional
(`fast_executemany`). Soporta Windows Auth (sin `SQL_USERNAME`) o usuario/pass.

ODBC Driver 18: `TrustServerCertificate=yes` para entornos locales.
"""
from __future__ import annotations

import pyodbc
from sqlalchemy import create_engine

from config.settings import SQL_DATABASE, SQL_PASSWORD, SQL_SERVER, SQL_USERNAME

_DRIVER = "ODBC Driver 18 for SQL Server"


def _auth_params() -> str:
    if SQL_USERNAME:
        return f"UID={SQL_USERNAME};PWD={SQL_PASSWORD};"
    return "Trusted_Connection=yes;"


def _conn_str() -> str:
    return (
        f"DRIVER={{{_DRIVER}}};"
        f"SERVER={SQL_SERVER};"
        f"DATABASE={SQL_DATABASE};"
        f"{_auth_params()}"
        "TrustServerCertificate=yes;"
    )


def get_connection() -> pyodbc.Connection:
    return pyodbc.connect(_conn_str())


def get_engine():
    driver = _DRIVER.replace(" ", "+")
    if SQL_USERNAME:
        url = (
            f"mssql+pyodbc://{SQL_USERNAME}:{SQL_PASSWORD}"
            f"@{SQL_SERVER}/{SQL_DATABASE}"
            f"?driver={driver}&TrustServerCertificate=yes"
        )
    else:
        url = (
            f"mssql+pyodbc://@{SQL_SERVER}/{SQL_DATABASE}"
            f"?driver={driver}&TrustServerCertificate=yes&trusted_connection=yes"
        )
    return create_engine(url, fast_executemany=True)
