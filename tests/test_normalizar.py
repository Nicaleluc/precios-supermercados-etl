"""Tests del transform (normalización VTEX) y del comparador. Sin red ni DB."""
from __future__ import annotations

from etl.dominios.comparador.canasta import Cotizacion
from etl.dominios.precios.modelos import Oferta, Producto
from etl.dominios.precios.normalizar import normalizar
from etl.dominios.precios.normalizar_coope import normalizar as normalizar_coope
from etl.dominios.precios.normalizar_la_banderita import _precio, normalizar as normalizar_lb

_PRODUCTO_CRUDO = {
    "productId": "123",
    "productName": "Leche entera 1 L",
    "brand": "La Serenísima",
    "linkText": "leche-entera-1l",
    "categories": ["/Almacen/Lacteos/"],
    "items": [
        {
            "itemId": "456",
            "nameComplete": "Leche entera La Serenísima 1 L",
            "ean": "7790742123456",
            "measurementUnit": "un",
            "sellers": [
                {"commertialOffer": {"Price": 1500.0, "ListPrice": 1800.0, "AvailableQuantity": 8}}
            ],
        }
    ],
}


def test_normalizar_basico():
    ofertas = normalizar("vea", _PRODUCTO_CRUDO, host="www.vea.com.ar")
    assert len(ofertas) == 1
    oferta = ofertas[0]
    assert oferta.producto.cadena == "vea"
    assert oferta.producto.sku_id == "456"
    assert oferta.producto.ean == "7790742123456"
    assert oferta.producto.marca == "La Serenísima"
    assert oferta.producto.categoria == "/Almacen/Lacteos/"
    assert oferta.producto.subcategoria == "Lacteos"
    assert oferta.producto.url == "https://www.vea.com.ar/leche-entera-1l/p"
    assert oferta.precio == 1500.0
    assert oferta.precio_lista == 1800.0
    assert oferta.disponible is True


def test_normalizar_descarta_precio_invalido():
    crudo = {
        "productName": "Producto",
        "items": [
            {"itemId": "1", "sellers": [{"commertialOffer": {"Price": 0}}]},
            {"itemId": "2", "sellers": [{"commertialOffer": {"Price": None}}]},
        ],
    }
    assert normalizar("vea", crudo) == []


def test_comparador_elige_mas_barato():
    p_vea = Producto(cadena="vea", sku_id="1", nombre="Leche")
    p_coope = Producto(cadena="cooperativa_obrera", sku_id="2", nombre="Leche")
    cot = Cotizacion(
        termino="leche",
        por_cadena={
            "vea": Oferta(producto=p_vea, precio=1500.0),
            "cooperativa_obrera": Oferta(producto=p_coope, precio=1200.0),
        },
    )
    mejor = cot.mejor
    assert mejor is not None
    assert mejor[0] == "cooperativa_obrera"
    assert mejor[1].precio == 1200.0


def test_comparador_sin_match():
    cot = Cotizacion(termino="x", por_cadena={"vea": None})
    assert cot.mejor is None


def test_precio_la_banderita():
    assert _precio("$2.599") == 2599.0
    assert _precio("$ 2.147,93") == 2147.93
    assert _precio("$1.234,56") == 1234.56
    assert _precio(None) is None
    assert _precio("") is None


def test_normalizar_la_banderita():
    raw = {
        "producto_id": "4534684",
        "nombre": "Arroz Con Leche Chocolate Tregar 180 gr",
        "marca": "Tregar",
        "categoria": "Postres",
        "precio_txt": "$2.190",
        "precio_lista_txt": None,
        "precio_sin_imp_txt": "$ 1.809,92",
        "url": "https://www.labanderita.ar/shop/product/x-WS4534684",
        "imagen": "https://cdn/img.jpg",
    }
    o = normalizar_lb("la_banderita", raw)
    assert o is not None
    assert o.precio == 2190.0
    assert o.precio_sin_imp == 1809.92
    assert o.producto.sku_id == "4534684"
    assert o.producto.marca == "Tregar"
    assert o.producto.categoria == "Postres"


def test_normalizar_coope():
    d = {
        "cod_interno": "318298",
        "descripcion": "LECHE CHOCOLATADA NESTLÉ 190cm3",
        "precio": "3490.00",
        "precio_anterior": "3490.00",
        "precio_sin_impuestos": "2884.30",
        "precio_unitario": "18368.42",
        "gramaje": "190.00",
        "unimed_desc": "cm3",
        "stock": "24",
        "disponibilidad": True,
        "existe_promo": False,
        "marca_desc": "NESTLE",
        "id_categoria": "359",
        "categoria_inicial_desc": "Frescos",
        "categoria_secundaria_desc": "Leches",
        "categoria_terciaria_desc": "Chocolatada/Saborizada",
    }
    o = normalizar_coope("cooperativa_obrera", d)
    assert o is not None
    assert o.precio == 3490.0
    assert o.precio_sin_imp == 2884.30
    assert o.precio_unitario == 18368.42
    assert o.stock == 24
    assert o.producto.categoria == "Frescos > Leches > Chocolatada/Saborizada"
    assert o.producto.subcategoria == "Chocolatada/Saborizada"
    assert o.producto.contenido_neto == 190.0
    assert o.producto.ean is None
