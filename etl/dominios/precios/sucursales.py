"""Sucursales (puntos de venta) por cadena -> `D_PrecioSucursal`.

Dos fuentes:
  * Semilla curada de **Bahía Blanca** (páginas de sucursales y catálogos
    locales, 2026-10). Es data, no código: mantener a mano.
  * **Cooperativa Obrera**: sus localidades servidas se traen de su API
    (`/api/localidades`, con coordenadas).

Idempotente: upsert por `(CadenaId, CodigoSucursal)` vía `repository`.
"""
from __future__ import annotations

import json

from etl.conn.coope import CoopeClient, CoopeError

from .constants import CADENAS
from .repository import upsert_cadena, upsert_sucursal

LOCALIDAD_BB = "Bahía Blanca"
PROVINCIA_BB = "Buenos Aires"

# Semilla curada de Bahía Blanca (direcciones verificadas en fuentes 2026-10).
SUCURSALES_BAHIA_BLANCA: tuple[dict, ...] = (
    {"cadena": "vea", "codigo": "BB-CASANOVA", "tipo": "SUPER", "direccion": "Casanova 472"},
    {"cadena": "vea", "codigo": "BB-MARTINEZ", "tipo": "SUPER", "direccion": "Capitán Martínez 1356"},
    {"cadena": "changomas", "codigo": "BB-SARMIENTO", "tipo": "HIPER", "direccion": "Sarmiento 4114"},
    {"cadena": "carrefour", "codigo": "BB-BROWN", "tipo": "SUPER", "direccion": "Brown 51"},
    {"cadena": "makro", "codigo": "BB-CABRERA", "tipo": "MAYORISTA", "direccion": "Av. Cabrera 4162"},
    {"cadena": "diarco", "codigo": "BB-COLON", "tipo": "MAYORISTA", "direccion": "Av. Colón 2621"},
    {"cadena": "vital", "codigo": "BB-RUTA3", "tipo": "MAYORISTA", "direccion": "Ruta 3"},
    {"cadena": "la_banderita", "codigo": "BB-LIBERTAD", "tipo": "SUPER", "direccion": "Libertad 2144"},
)


def _cadena_id(cur, codigo: str) -> int:
    cadena = CADENAS.get(codigo)
    return upsert_cadena(
        cur,
        codigo=codigo,
        nombre=cadena.nombre if cadena else codigo,
        plataforma=(cadena.tipo.upper() if cadena else "OTRA"),
        host=(cadena.host or None) if cadena else None,
        api_host=(cadena.api_host or None) if cadena else None,
    )


def cargar_bahia_blanca(cur) -> int:
    total = 0
    for s in SUCURSALES_BAHIA_BLANCA:
        cadena_id = _cadena_id(cur, s["cadena"])
        cadena = CADENAS.get(s["cadena"])
        upsert_sucursal(
            cur, cadena_id=cadena_id, codigo=s["codigo"], tipo=s["tipo"],
            nombre=f"{(cadena.nombre if cadena else s['cadena'])} {LOCALIDAD_BB}",
            direccion=s["direccion"], localidad=LOCALIDAD_BB, provincia=PROVINCIA_BB,
        )
        total += 1
    return total


def _coord(dato) -> tuple[float | None, float | None]:
    if not dato:
        return None, None
    try:
        obj = json.loads(dato) if isinstance(dato, str) else dato
        c = (obj or {}).get("coordenadas") or {}
        return c.get("latitud"), c.get("longitud")
    except (ValueError, TypeError):
        return None, None


def cargar_coope_localidades(cur, *, exclusivas: int = 1) -> int:
    cadena = CADENAS.get("cooperativa_obrera")
    if cadena is None or not cadena.host_api:
        return 0
    cadena_id = _cadena_id(cur, "cooperativa_obrera")
    cliente = CoopeClient(cadena.host_api)
    total = 0
    try:
        for loc in cliente.localidades(exclusivas=exclusivas):
            id_loc = str(loc.get("id_localidad") or "")
            desc = loc.get("descripcion") or ""
            if not id_loc:
                continue
            lat, lon = _coord(loc.get("datos"))
            upsert_sucursal(
                cur, cadena_id=cadena_id, codigo=f"LOC-{id_loc}", tipo="LOCALIDAD",
                nombre=desc, localidad=desc, codigo_postal=loc.get("cod_postal"),
                latitud=lat, longitud=lon,
            )
            total += 1
    except CoopeError as exc:
        print(f"[!] Coope localidades: {exc}")
    finally:
        cliente.cerrar()
    return total


def cargar(cur, conn, *, con_coope: bool = True) -> dict:
    stats = {"bahia_blanca": cargar_bahia_blanca(cur)}
    stats["coope_localidades"] = cargar_coope_localidades(cur) if con_coope else 0
    conn.commit()
    return stats
