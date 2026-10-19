-- consulta_productos.sql
-- Cuadro de precios: filas = productos, columnas = cadenas (Vea / Coope /
-- Carrefour / La Banderita), valor = ULTIMO precio conocido (efectivo: si hay
-- promo, ya viene el precio de promo).
--
-- Como se usa:
--   * Agregar productos en @productos (una fila por producto/packaging).
--   * Si tenes el EAN, ponelo en `Ean` (match preciso). Si no, deja Ean NULL
--     y usa P1/P2/Excluir (LIKE por nombre).
--   * Ejecutar en SSMS o:
--     sqlcmd -S "localhost" -d precios-supermercados-etl -E -i consulta_productos.sql
--
-- Notas:
--   * Coope y La Banderita NO exponen EAN en su API/scraping.
--   * El ultimo precio se toma por ProductoId (ROW_NUMBER por Fecha DESC).
--   * Precio = precio efectivo (VTEX commertialOffer.Price, Coope `precio`
--     promocional, La Banderita `.price` actual).

SET NOCOUNT ON;

DECLARE @cadenas TABLE (Codigo varchar(40) PRIMARY KEY);
INSERT INTO @cadenas (Codigo) VALUES
    ('vea'), ('cooperativa_obrera'), ('carrefour'), ('la_banderita');

DECLARE @productos TABLE (
    Orden    int PRIMARY KEY,
    Producto nvarchar(160),
    Ean      varchar(14) NULL,
    P1       nvarchar(120) NULL,
    P2       nvarchar(120) NULL,
    Excluir  nvarchar(120) NULL
);
INSERT INTO @productos (Orden, Producto, Ean, P1, P2, Excluir) VALUES
    (1, N'Las Tres Niñas con Proteína 0% lactosa 1 L', N'7798338291803', NULL, NULL, NULL),
    (2, N'La Serenísima Protein — SACHET 1 L',         N'7790742352101', NULL, NULL, NULL),
    (3, N'La Serenísima Protein — CAJA/BOTELLA 1 L',   N'7790742358608', NULL, NULL, NULL);

WITH ult AS (
    SELECT p.ProductoId, p.Ean, ch.Codigo AS Cadena, p.Nombre, o.Precio,
           ROW_NUMBER() OVER (PARTITION BY p.ProductoId
                              ORDER BY o.Fecha DESC, o.OfertaId DESC) AS rn
    FROM dbo.D_PrecioOferta o
    JOIN dbo.D_PrecioProducto p ON p.ProductoId = o.ProductoId
    JOIN dbo.D_PrecioCadena  ch ON ch.CadenaId = p.CadenaId
    JOIN @cadenas c ON c.Codigo = ch.Codigo
),
match AS (
    SELECT pr.Orden, u.Cadena, u.Precio
    FROM ult u
    JOIN @productos pr
      ON ( (pr.Ean IS NOT NULL AND u.Ean = pr.Ean)
           OR (pr.Ean IS NULL AND u.Nombre LIKE pr.P1
               AND (pr.P2 IS NULL OR u.Nombre LIKE pr.P2)
               AND (pr.Excluir IS NULL OR u.Nombre NOT LIKE pr.Excluir)) )
    WHERE u.rn = 1
)
SELECT pr.Orden, pr.Producto, pr.Ean,
       CAST(MIN(CASE WHEN m.Cadena = 'vea'                THEN m.Precio END) AS decimal(18,2)) AS Vea,
       CAST(MIN(CASE WHEN m.Cadena = 'cooperativa_obrera' THEN m.Precio END) AS decimal(18,2)) AS Coope,
       CAST(MIN(CASE WHEN m.Cadena = 'carrefour'          THEN m.Precio END) AS decimal(18,2)) AS Carrefour,
       CAST(MIN(CASE WHEN m.Cadena = 'la_banderita'       THEN m.Precio END) AS decimal(18,2)) AS [La Banderita]
FROM @productos pr
LEFT JOIN match m ON m.Orden = pr.Orden
GROUP BY pr.Orden, pr.Producto, pr.Ean
ORDER BY pr.Orden;
