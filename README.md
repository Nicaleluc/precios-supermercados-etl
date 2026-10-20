# precios-supermercados-etl — Precios de supermercados → SQL Server + comparador

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Python](https://img.shields.io/badge/python-3.12%2B-blue)

ETL de catálogos, precios y sucursales de supermercados argentinos a **SQL Server**
(base `precios-supermercados-etl`, tablas `D_Precio*`), más:

- **comparador de canasta**: cargás la lista de lo que tenés que comprar y te dice
  qué cadena conviene por ítem y el total "carrito dividido";
- **registro de compras** + vista con el **mejor precio actual** por ítem.

Repo **fuera del ecosistema DELI**: no comparte el código de `deli/` (tiene su
propio `db.py`). Por eso **no** lleva prefijo `deli-` (como `tester-posnet`,
`editor-reportes`).

---

## Índice

- [Qué hace](#qué-hace)
- [Fuentes de datos](#fuentes-de-datos)
- [Cómo funciona](#cómo-funciona)
- [Requisitos](#requisitos)
- [Instalación y uso](#instalación-y-uso)
- [Cadenas soportadas](#cadenas-soportadas)
- [Configuración (`.env`)](#configuración-env)
- [Esquema del store](#esquema-del-store)
- [SEPA (precio por sucursal)](#sepa-precio-por-sucursal)
- [Comparador cruzado](#comparador-cruzado)
- [Compras y vista de mejor precio](#compras-y-vista-de-mejor-precio)
- [Automatización](#automatización)
- [Estructura](#estructura)
- [Buenas prácticas / notas técnicas](#buenas-prácticas--notas-técnicas)
- [Pendientes conocidos](#pendientes-conocidos)
- [Solución de problemas](#solución-de-problemas)
- [Licencia](#licencia)

---

## Qué hace

1. **Extract**: trae catálogos y precios de cada cadena desde su storefront/API
   pública (VTEX, la API de la Coope, scraping de La Banderita) y, opcionalmente,
   desde el **SEPA** oficial (precio por sucursal).
2. **Transform**: normaliza a un modelo único `Producto` + `Oferta` (EAN, nombre,
   marca, categoría, unidad, precio, precio de lista, promo, stock).
3. **Load**: `MERGE` idempotente en SQL Server, con **histórico de precios por día**.
4. **Comparar**: dado un término, EAN o producto, responde qué cadena conviene y
   el total por cadena / carrito dividido.
5. **Compras**: registra lo que compraste y una **vista** te muestra el precio más
   barato actual de cada ítem en Vea/Coope/Carrefour/La Banderita.

## Fuentes de datos

| Plataforma | Cadenas | Cómo se obtiene |
|---|---|---|
| **VTEX** | Vea, Jumbo, Disco, Carrefour, Changomas, Cordiez, DIA | Endpoints públicos del storefront (Intelligent Search / Catalog Search). |
| **API propia** | Cooperativa Obrera ("La Coope en Casa") | `api.lacoopeencasa.coop` (búsqueda paginada + detalle + localidades). |
| **Scraping HTML** | La Banderita (super local de Bahía Blanca) | `/shop?s=` + `Products_Search/List_Scroll` (paginado) + catálogo por marcas. |
| **SEPA (oficial)** | Comercios adheridos | ZIP oficial diario → precio **por sucursal** + EAN. |

## Cómo funciona

```
Fuentes (VTEX / Coope / La Banderita / SEPA)
        │
        ▼
normalizar → Producto + Oferta (modelo único entre cadenas)
        │
        ▼
SQL Server (base precios-supermercados-etl, tablas D_Precio*)
  D_PrecioCadena    (upsert por Codigo)
  D_PrecioSucursal  (upsert por CadenaId+CodigoSucursal; fila 'ONLINE')
  D_PrecioProducto  (upsert por CadenaId+SkuId)
  D_PrecioOferta    (upsert por ProductoId+SucursalId+Fecha → histórico diario)
        │
        ├── comparador de canasta → "conviene Vea para la leche, Coope para la yerba"
        └── compras + vista → "de lo que compraste, dónde está más barato hoy"
```

* **Idempotencia** (todo por `MERGE`): `Producto` por `(CadenaId, SkuId)`,
  `Oferta` por `(ProductoId, SucursalId, Fecha)`. Re-correr el mismo día
  actualiza, no duplica.
* **Sucursal `ONLINE`**: el precio online es válido para toda la cadena, no por
  local. Se crea una sucursal sintética por cadena (`CodigoSucursal='ONLINE'`)
  para que la FK nunca quede nula; el precio por local (SEPA) usa la sucursal real.
* **Histórico**: un registro por producto/sucursal/día → sirve para ver variación.

## Requisitos

* Python ≥ 3.12
* **ODBC Driver 18 for SQL Server**
* Acceso a SQL Server (base `precios-supermercados-etl`) con permiso de
  `CREATE TABLE`/`MERGE` en `dbo`. Windows Auth por defecto (o usuario/pass).
* Conexión a internet (los catálogos se consultan en vivo)

## Instalación y uso

```bash
pip install -e .
copy .env.template .env      # completar SQL_SERVER / SQL_DATABASE
```

**Cargar precios:**

```bash
py -u -m cli.importar_precios
py -u -m cli.importar_precios --cadena vea --termino leche --termino yerba
py -u -m cli.importar_precios --cadena cooperativa_obrera --termino leche
py -u -m cli.importar_precios --cadena la_banderita --termino leche --ean-ficha
py -u -m cli.importar_precios --catalogo          # catálogo completo (VTEX/Coope/Banderita)
```

**Cargar sucursales (`D_PrecioSucursal`):**

```bash
py -u -m cli.cargar_sucursales            # semilla Bahía Blanca + localidades Coope
py -u -m cli.cargar_sucursales --sin-coope
```

**Cargar SEPA (precio por sucursal):**

```bash
py -u -m cli.cargar_sepa --auto                              # baja el ZIP del día
py -u -m cli.cargar_sepa --zip .\sepa_martes.zip --max-grupos 2 --limite 500
```

**Chequear si un precio es "normal" (referencia SEPA):**

```bash
py -u -m cli.chequear_precio --ean 7798338291803
py -u -m cli.chequear_precio --ean 7798338291803 --precio 3190
```

**Enriquecer EAN de la Coope (su API no lo expone):**

```bash
py -u -m cli.enriquecer_ean_coope --limite 50 --dry-run
py -u -m cli.enriquecer_ean_coope
```

> La Coope no publica el EAN, pero su autocomplete **busca por EAN**. El CLI
> toma los productos sin EAN, busca candidatos en VTEX/SEPA por similitud de
> nombre y confirma consultando ese EAN en la Coope (si devuelve el mismo
> `cod_interno`, setea el EAN).

**Comparar una lista de compras:**

```bash
py -u -m cli.comparar leche yerba aceite        # lee la base (todas las cadenas)
py -u -m cli.comparar --vivo leche pan          # en vivo (solo VTEX)
py -u -m cli.comparar --ean 7793913013474       # un EAN en todas las cadenas
py -u -m cli.comparar --producto "Leche entera 1 litro"   # equivalentes (fuzzy)
py -u -m cli.comparar --por-unidad leche        # elige el más barato por kg/l
```

**Registrar una compra:**

```bash
py -u -m cli.registrar_compra --comercio "Verdulería" --total 10000 ^
  --item "Mandarina:1:kg" --item "Kiwi:0.5:kg" --item "Frutilla:0.25:kg" ^
  --item "Banana:0.54:kg" --item "Brócoli:0.6:kg" --item "Chaucha:0.25:kg"
```

Se importa por paquete raíz (`from etl.dominios.precios...`), nunca con
`sys.path.insert`.

En Windows: `cargar.bat`, `cargar_sucursales.bat`, `cargar_todo.bat`,
`cargar_diario.bat`, `cargar_semanal.bat`, `cargar_sepa.bat`, `comparar.bat`
(activan `.venv` si existe y reenvían los argumentos).

### Flags

| CLI | Flag | Efecto |
|---|---|---|
| `importar_precios` | `--cadena ID` | Cadena a cargar (repetible). Default: `CADENAS` del `.env`. |
| | `--termino T` | Término de búsqueda (repetible). Default: semilla de `constants.py`. |
| | `--por-pagina N` / `--paginas N` | Paginación por término (`--paginas` también rige La Banderita). |
| | `--catalogo` / `--cat-paginas N` | Recorrer **todo el catálogo** (VTEX por categoría, Coope por categoría, La Banderita por marca). |
| | `--cat-marcas N` / `--cat-terminos N` | Limitar marcas (Banderita) / categorías-término (Coope) en `--catalogo`. |
| | `--ean-ficha` | La Banderita: traer EAN abriendo cada ficha (1 request c/u). |
| `comparar` | `terminos...` | Lo que hay que comprar (si se omite, lista semilla). |
| | `--vivo` | Consultar los sitios VTEX en vivo (default: leer la base). |
| | `--ean EAN` | Comparar un EAN puntual entre cadenas. |
| | `--producto NOMBRE` / `--marca M` | Equivalentes (fuzzy) de un producto entre cadenas. |
| | `--por-unidad` | Elegir el más barato por kg/l (no por precio absoluto). |
| | `--cadena ID` | Filtrar a cadenas (repetible). |
| `cargar_sucursales` | `--sin-coope` | No traer localidades de la Coope (solo semilla BB). |
| `cargar_sepa` | `--auto` / `--dia D` / `--cache DIR` | Bajar el ZIP del día (o de un día) desde datos.gob.ar. |
| | `--zip FILE` | Cargar un ZIP ya descargado (outer o inner). |
| | `--max-grupos N` / `--limite N` | Procesar solo N inner ZIPs / cortar tras N precios (prueba). |
| | `--banderas F.json` | Mapa id_bandera → nombre comercial (opcional). |
| `registrar_compra` | `--comercio` / `--total` / `--fecha` | Cabecera de la compra. |
| | `--item Nombre:Cantidad:Unidad[:PrecioUnitario]` | Ítem (repetible). |
| | `--json FILE` | Alternativa: JSON con comercio/total/items. |

### Tests

```bash
pip install -e ".[dev]"
pytest
```

Cubren el transform (VTEX/Coope/La Banderita), el matching y un test de
integración con la DB (se salta si no hay conexión).

## Cadenas soportadas

El registro vive en `etl/dominios/precios/constants.py` (id, nombre, host,
api_host). Verificado en vivo: las cadenas VTEX devuelven el mismo shape (marca,
categoría, categoryId, EAN, unidad, imagen y precio al 100%).

| id | Cadena | Host | Estado |
|---|---|---|---|
| `vea` | Vea | `www.vea.com.ar` | ✅ VTEX |
| `jumbo` | Jumbo | `www.jumbo.com.ar` | ✅ VTEX |
| `disco` | Disco | `www.disco.com.ar` | ✅ VTEX |
| `carrefour` | Carrefour | `www.carrefour.com.ar` | ✅ VTEX |
| `changomas` | Changomas (Más Online) | `www.masonline.com.ar` | ✅ VTEX |
| `cordiez` | Cordiez | `www.cordiez.com.ar` | ✅ VTEX |
| `dia` | DIA | `www.supermercadosdia.com.ar` | ✅ VTEX vía cuenta `diaio` (`api_host`) |
| `cooperativa_obrera` | Cooperativa Obrera | `www.lacoopeencasa.coop` | ✅ API propia (búsqueda paginada + catálogo; EAN por enriquecimiento) |
| `la_banderita` | La Banderita (BB) | `www.labanderita.ar` | ✅ Scraper HTML (paginado + EAN + marcas) |
| `makro` | Makro | — | ❌ No es VTEX (WordPress), sin API de productos |
| `diarco`, `vital`, `la_anonima` | — | — | ⚠️ Sin API de precios usable (cubiertas por SEPA o scraping) |

Agregar una cadena: registrar su `Cadena(id, nombre, host[, api_host])` en
`constants.py` y, si no es VTEX, extender `etl/conn/` con un cliente nuevo.

## Configuración (`.env`)

| Variable | Uso |
|---|---|
| `SQL_SERVER` | Instancia (default `localhost\SQLEXPRESS`) |
| `SQL_DATABASE` | Base (default `precios-supermercados-etl`) |
| `SQL_USERNAME` / `SQL_PASSWORD` | Usuario SQL. **Vacío = Windows Auth** |
| `USER_AGENT` | Identificación del cliente HTTP |
| `HTTP_TIMEOUT` | Timeout por request (s) |
| `HTTP_REINTENTOS` | Reintentos ante 429/red |
| `HTTP_PAUSA` | Pausa base entre reintentos (s) |
| `CADENAS` | Ids habilitados por defecto (coma-separados) |
| `POR_PAGINA` | Resultados por página |
| `MAX_PAGINAS` | Páginas máximas por término |

Credenciales y rutas: solo en `.env` (nunca se commitea; ver `.env.template`).

## Esquema del store

| Tabla | Clave | Contenido |
|---|---|---|
| `D_PrecioCadena` | `Codigo` | cadena → plataforma, host, cuenta VTEX |
| `D_PrecioSucursal` | `(CadenaId, CodigoSucursal)` | localidad, dirección, geo, tipo (`SUPER`/`ONLINE`/…) |
| `D_PrecioProducto` | `(CadenaId, SkuId)` | EAN, nombre, marca, categoría (+ canónica), unidad, URL, imagen |
| `D_PrecioOferta` | `(ProductoId, SucursalId, Fecha)` | precio, lista, sin impuestos, unitario, promo, stock, origen |
| `D_Compra` | `CompraId` | fecha, comercio, total |
| `D_CompraDetalle` | `DetalleId` | ítem, cantidad, unidad, precio unitario, subtotal, EAN, categoría |
| `D_CompraProductoRef` | `(Item, Cadena)` | fija el SKU exacto por ítem/cadena (y override `$/kg`) |
| `V_CompraPrecioBarato` | vista | ítems comprados × Coope/Vea/Carrefour/La Banderita + más barato |
| `V_PrecioNormal` | vista | por EAN: precio normal (mediana SEPA), min/max, referencia, promos |

DDL idempotente en `etl/dominios/precios/schema.py` y en `sql/` (001-004);
se crea solo en la primera carga.

## SEPA (precio por sucursal)

`etl/conn/sepa.py` + `cli/cargar_sepa.py` leen el **ZIP oficial** (estructura
anidada: `<fecha>/sepa_*_comercio-sepa-*.zip` → `comercio.csv`, `sucursales.csv`,
`productos.csv`, delimitado por `|`, UTF-8) y lo mapean a:

* `D_PrecioCadena`   (id_comercio + id_bandera → nombre comercial),
* `D_PrecioSucursal` (dirección/localidad/provincia/geo),
* `D_PrecioProducto` + `D_PrecioOferta` (**precio por sucursal**, EAN = `id_producto`, `Origen='SEPA'`).

Validado con el ZIP real de 2026-10-13 (`INC S.A.` = Carrefour).

Carga **bulk** (staging + MERGE set-based) para los ~12 M de filas/día: los CSV
se vuelcan a tablas temporales con `fast_executemany` y se hacen `MERGE`/`INSERT`
de conjuntos. `precio_lista` → `Precio`; `precio_referencia` → `PrecioLista`.

```bash
py -u -m cli.cargar_sepa --auto                 # baja el ZIP del día y lo carga
py -u -m cli.cargar_sepa --zip ... --max-grupos 2 --limite 500   # prueba
```

## Precio normal (SEPA)

`V_PrecioNormal` calcula, por EAN, el **precio normal** como la **mediana entre
sucursales** del SEPA, más mínimo, máximo, referencia y cantidad de promos.
`cli.chequear_precio` compara un precio (o los precios cargados de cada cadena)
contra ese normal:

```bash
py -u -m cli.chequear_precio --ean 7798338291803
```

```
EAN 7798338291803  LECHE C PROTEINA VIDA ACTIVA LAS TRES NINAS X 1LT
  SEPA: normal $3.119 (mediana de 6 sucursales; min $2.999 / max $3.275; promos 0)
  Cordiez              $2.269  (-27.3% vs normal)  barato
  Cooperativa Obrera   $2.290  (-26.6% vs normal)  barato
  Carrefour            $3.119  (  0.0% vs normal)  normal
  DIA                  $3.120  (  0.0% vs normal)  normal
  Vea                  $3.190  ( +2.3% vs normal)  normal
```

## Comparador cruzado

`cli.comparar` (sin `--vivo`) lee las tablas y cruza **todas** las cadenas
cargadas. Tres niveles de matching:

* **por nombre** (contiene, normalizado) → resuelve un término de compra;
* **por EAN** (`--ean <código>`) → el mismo producto entre cadenas, exacto;
* **fuzzy** (`--producto "<nombre>"`, `etl/dominios/comparador/matching.py`) →
  equivalentes entre cadenas (rapidfuzz + tamaño/medida), y `--por-unidad` para
  elegir por **$/kg** o **$/l**.

Cada producto se guarda con `CategoriaCanonica` (rubro unificado,
`etl/dominios/precios/categorias.py`), para agrupar por rubro.

## Compras y vista de mejor precio

`cli.registrar_compra` guarda la compra (`D_Compra` + `D_CompraDetalle`) y la
vista `V_CompraPrecioBarato` la cruza con el último precio por cadena:

```sql
SELECT * FROM dbo.V_CompraPrecioBarato;
```

| Ítem | Unidad | Coope | Vea | Carrefour | La Banderita | MasBarato |
|---|---|---|---|---|---|---|
| Banana | kg | — | 2.499 | 1.999 | — | 1.999 |
| Brócoli | kg | — | 4.999 | 5.999 | — | 4.999 |

La vista usa `D_CompraProductoRef` para fijar el **SKU exacto** de cada
ítem/cadena (y `PrecioPorKg` para packs); si no hay ref, cae al mejor match por
nombre. Para el cuadro de productos puntuales (por EAN/nombre) está
`sql/consulta_productos.sql`.

## Automatización

```bash
programar_tareas.bat   # diaria 07:00 (precios+sucursales+SEPA) + semanal dom 03:00 (catálogo)
cargar_diario.bat      # diaria headless (logs en logs/)
cargar_semanal.bat     # catálogo completo headless (logs/catalogo.log)
cargar_sepa.bat        # SEPA del día
```

## Estructura

```
cargar.bat / cargar_sucursales.bat / cargar_todo.bat / cargar_diario.bat /
cargar_semanal.bat / cargar_sepa.bat / comparar.bat
programar_diario.bat / programar_tareas.bat
cli/importar_precios.py           # extract + flags (--catalogo, --ean-ficha)
cli/comparar.py                   # comparador (base por defecto; --vivo, --ean, --producto)
cli/cargar_sucursales.py          # sucursales a D_PrecioSucursal
cli/cargar_sepa.py                # SEPA (--auto / --zip)
cli/registrar_compra.py           # registra compras (D_Compra/Detalle)
cli/chequear_precio.py            # compara un precio contra el normal de SEPA
cli/enriquecer_ean_coope.py       # mapea EAN -> cod_interno de la Coope
config/settings.py                # lee .env (SQL_*, HTTP_*, cadenas)
etl/conn/db.py                    # pyodbc + SQLAlchemy (ODBC Driver 18, Windows Auth)
etl/conn/vtex.py                  # cliente VTEX (búsqueda, EAN, categorías)
etl/conn/coope.py                 # cliente de la API de La Coope en Casa
etl/conn/la_banderita.py          # scraper HTML (paginado + EAN)
etl/conn/sepa.py                  # lector de ZIP/CSV de SEPA
etl/dominios/precios/constants.py # registro de cadenas + términos semilla
etl/dominios/precios/modelos.py   # Producto, Oferta
etl/dominios/precios/categorias.py# categoría canónica entre cadenas
etl/dominios/precios/normalizar*.py # VTEX / Coope / La Banderita -> Oferta
etl/dominios/precios/schema.py    # DDL SQL Server idempotente (+ migraciones)
etl/dominios/precios/repository.py# upserts con MERGE
etl/dominios/precios/importer.py  # extract por plataforma / catálogo
etl/dominios/precios/sucursales.py# semilla BB + localidades Coope
etl/dominios/comparador/canasta.py# cotizar en vivo + recomendar
etl/dominios/comparador/cruzado.py# comparar sobre la base + EAN + equivalentes
etl/dominios/comparador/matching.py# similitud, medida, precio por unidad
sql/001_create_precios_supermercados.sql  # tablas + índices
sql/002_compras.sql                       # compras (cabecera/detalle)
sql/003_vista_compras.sql                 # vista V_CompraPrecioBarato
sql/004_ref_productos.sql                 # refs de SKU por ítem/cadena
sql/005_migrar_datos.sql                  # migración desde otra base (opcional)
sql/006_precio_normal.sql                 # vista V_PrecioNormal
sql/consulta_productos.sql                # cuadro por EAN/nombre
tests/                            # transform, matching, integración (DB se salta si no hay)
```

## Buenas prácticas / notas técnicas

* **HTTP**: retries con backoff ante `429`/red, `User-Agent` identificable,
  pausa configurable. Sin martillar el sitio.
* **SQL siempre parametrizado** (sin literales inline): ver `repository.py`
  (`MERGE ... USING (VALUES (...))` con `?`).
* **Idempotencia** en todo el load (`MERGE` por clave lógica).
* **Truncado seguro**: los textos se recortan a la longitud de columna (`_txt`).
* **Modelo único entre cadenas**: la variación de plataforma vive en `etl/conn/`;
  el dominio solo conoce `Producto`/`Oferta`.
* **`temp/`**: solo en la raíz del repo; se vacía al cerrar sesión.

## Pendientes conocidos

* **La Anónima**: su backend online está caído (`RedisException`) y el endpoint de
  listado no se pudo descubrir; SEPA la cubre.
* **Diarco / Vital / Makro**: sin API de precios usable → SEPA (mayorista) o scraping.
* **Catálogo completo**: el código existe (`--catalogo`), pero es pesado; está
  programado semanal (no diario).
* **EAN de La Banderita**: parcial o completo con `--ean-ficha`.

## Solución de problemas

| Síntoma | Causa / solución |
|---|---|
| `Can't open lib 'ODBC Driver 18 for SQL Server'` | Falta el ODBC Driver 18 en el host. |
| `Login failed` | Completar `SQL_USERNAME`/`SQL_PASSWORD` o habilitar Windows Auth. |
| `String or binary data would be truncated` | Un campo supera su columna; ya se recorta con `_txt`. |
| `sin host confirmado, se saltea` | Cadena en el registro sin `host` (ej. `makro`, `diarco`). Completar en `constants.py`. |
| `GET ... falló tras N intentos` | Red, proxy o el endpoint cambió. Verificar con DevTools → Network. |
| Precios en `0` o vacíos | El sitio devolvió otro formato; revisar el JSON crudo y ajustar `normalizar.py`. |

## Licencia

MIT — ver [`LICENSE`](LICENSE). Uso libre con atribución (conservar aviso de
copyright).
