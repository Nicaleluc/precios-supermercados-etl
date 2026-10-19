"""Matching fino entre productos de distintas cadenas.

Primitivas:
  * `normalizar`        : minúsculas, sin tildes, sin signos.
  * `medida`            : extrae (cantidad_base, 'g'|'ml'|'un') del nombre.
  * `precio_unidad`     : $/kg o $/l (para comparar peras con peras).
  * `similitud`         : 0..1 combinando texto (rapidfuzz) + tamaño.

Sin dependencias externas salvo `rapidfuzz` (ya usado en el ecosistema).
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

try:
    from rapidfuzz import fuzz

    def _ratio(a: str, b: str) -> float:
        # token_sort exige que estén TODOS los tokens (más discriminante que WRatio).
        return fuzz.token_sort_ratio(a, b) / 100.0
except Exception:  # fallback stdlib
    from difflib import SequenceMatcher

    def _ratio(a: str, b: str) -> float:
        return SequenceMatcher(None, sorted(a.split()), sorted(b.split())).ratio()


_UNIDADES = {
    "kg": ("g", 1000), "kilo": ("g", 1000), "kilos": ("g", 1000),
    "g": ("g", 1), "gr": ("g", 1), "grs": ("g", 1), "gramos": ("g", 1),
    "l": ("ml", 1000), "lt": ("ml", 1000), "lts": ("ml", 1000),
    "litro": ("ml", 1000), "litros": ("ml", 1000),
    "ml": ("ml", 1), "cm3": ("ml", 1), "cc": ("ml", 1),
    "un": ("un", 1), "u": ("un", 1), "unidad": ("un", 1), "unidades": ("un", 1),
}
_RE_MEDIDA = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(kg|kilos?|kilo|grs?|gramos?|g|lts?|litros?|litro|l|ml|cm3|cc|unidades?|un|u)\b",
    re.IGNORECASE,
)


def normalizar(texto) -> str:
    s = unicodedata.normalize("NFKD", texto or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9 ]", " ", s.lower())
    return re.sub(r"\s+", " ", s).strip()


def medida(nombre) -> tuple[float, str] | None:
    """(cantidad en base, unidad base) del nombre. `1,5 l` -> (1500, 'ml')."""
    m = _RE_MEDIDA.search(nombre or "")
    if not m:
        return None
    try:
        cant = float(m.group(1).replace(",", "."))
    except ValueError:
        return None
    base, factor = _UNIDADES.get(m.group(2).lower(), ("un", 1))
    return cant * factor, base


def precio_unidad(precio: float, nombre) -> float | None:
    """$/kg o $/l. None si no se puede interpretar la medida (o es por unidad)."""
    m = medida(nombre)
    if not m or precio is None:
        return None
    cant, unidad = m
    if unidad == "un" or cant <= 0:
        return None
    return precio / (cant / 1000.0)


def similitud(nombre_a, nombre_b) -> float:
    """0..1: texto (WRatio) penalizado si el tamaño difiere."""
    na, nb = normalizar(nombre_a), normalizar(nombre_b)
    if not na or not nb:
        return 0.0
    score = _ratio(na, nb)
    ma, mb = medida(nombre_a), medida(nombre_b)
    if ma and mb:
        if ma[1] == mb[1]:  # misma dimensión: castiga tamaño distinto
            ratio = min(ma[0], mb[0]) / max(ma[0], mb[0])
            score *= (0.5 + 0.5 * ratio)
        else:  # dimensiones distintas (g vs ml): castigo leve
            score *= 0.85
    return round(score, 4)


@dataclass
class Candidate:
    nombre: str
    marca: str | None
    score: float


def mejores(candidatos, referencia: str, marca=None, umbral: float = 0.6, tope: int = 5):
    """Ordena candidatos por (similitud, marca) y filtra por umbral."""
    out = []
    for c in candidatos:
        s = similitud(c.nombre, referencia)
        if marca and c.marca and normalizar(marca) in normalizar(c.marca):
            s = min(1.0, s + 0.15)
        if s >= umbral:
            out.append(Candidate(c.nombre, c.marca, s))
    return sorted(out, key=lambda c: -c.score)[:tope]
