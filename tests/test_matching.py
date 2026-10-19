"""Tests de matching fino y categorías canónicas (sin red ni DB)."""
from __future__ import annotations

from etl.dominios.comparador.matching import medida, normalizar, precio_unidad, similitud
from etl.dominios.precios.categorias import canonica


def test_normalizar():
    assert normalizar("Leche Entera NESTLÉ 1 L") == "leche entera nestle 1 l"
    assert normalizar("Yerba Mate, 500 g.") == "yerba mate 500 g"


def test_medida():
    assert medida("Leche 1 L") == (1000.0, "ml")
    assert medida("Yerba 1 kg") == (1000.0, "g")
    assert medida("Leche chocolatada 190cm3") == (190.0, "ml")
    assert medida("Alfajor sin medida") is None


def test_precio_unidad():
    assert precio_unidad(1000, "Leche 1 L") == 1000.0
    assert precio_unidad(1000, "Yerba 500 g") == 2000.0
    assert precio_unidad(1500, "Alfajor") is None


def test_similitud():
    assert similitud("Leche entera 1 L", "Leche entera 1 L Milkaut") > 0.7
    assert similitud("Leche entera 1 L", "Gaseosa Pepsi 1.5 L") < 0.5
    # mismo texto pero distinto tamaño -> penalizado
    assert similitud("Yerba 500 g", "Yerba 1 kg") < similitud("Yerba 500 g", "Yerba 500 g")


def test_canonica():
    assert canonica("Frescos", "Leches", "Chocolatada") == "Lácteos"
    assert canonica("Almacén", "Aceite y Vinagre") == "Almacén"
    assert canonica("Bebidas") == "Bebidas"
    assert canonica("Limpieza", "Detergentes") == "Limpieza"
    assert canonica(None) == "Otros"
    assert canonica("Zzz") == "Otros"
