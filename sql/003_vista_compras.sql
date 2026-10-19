-- 003_vista_compras.sql
-- Vista PIVOTADA: cada item comprado (filas) x cada cadena (columnas), con el
-- precio actual mas barato de ESE producto en esa cadena.
--
-- Usa `D_CompraProductoRef` para fijar el SKU exacto que el usuario mira en la
-- pagina (por Item+Cadena). Si no hay ref, cae al mejor match por nombre.
-- `PrecioPorKg` (ref) permite expresar en $/kg los productos vendidos por pack.
--
-- Ejecutar:  sqlcmd -S "localhost" -d precios-supermercados-etl -E -i sql\003_vista_compras.sql

SET NOCOUNT ON;
GO

CREATE OR ALTER VIEW dbo.V_CompraPrecioBarato
AS
WITH items AS (
    SELECT Item, Unidad, MAX(CategoriaCanonica) AS CategoriaCanonica
    FROM dbo.D_CompraDetalle
    GROUP BY Item, Unidad
),
ult AS (
    SELECT p.ProductoId, p.SkuId, p.Nombre, p.CategoriaCanonica, p.Unidad,
           ch.Codigo AS Cadena, o.Precio,
           ROW_NUMBER() OVER (PARTITION BY p.ProductoId
                              ORDER BY o.Fecha DESC, o.OfertaId DESC) AS rn
    FROM dbo.D_PrecioOferta o
    JOIN dbo.D_PrecioProducto p ON p.ProductoId = o.ProductoId
    JOIN dbo.D_PrecioCadena ch ON ch.CadenaId = p.CadenaId
    WHERE ch.Codigo IN ('cooperativa_obrera', 'vea', 'carrefour', 'la_banderita')
),
ref AS (
    SELECT Item, Cadena, SkuId, PrecioPorKg FROM dbo.D_CompraProductoRef
),
cand_ref AS (
    SELECT i.Item, i.Unidad, u.Cadena,
           COALESCE(r.PrecioPorKg, u.Precio) AS Precio,
           ROW_NUMBER() OVER (PARTITION BY i.Item, i.Unidad, u.Cadena
                              ORDER BY COALESCE(r.PrecioPorKg, u.Precio)) AS rank
    FROM items i
    JOIN ref r ON r.Item = i.Item
    JOIN ult u ON u.rn = 1 AND u.Cadena = r.Cadena AND u.SkuId = r.SkuId
),
cand_gen AS (
    SELECT i.Item, i.Unidad, u.Cadena, u.Precio,
           ROW_NUMBER() OVER (PARTITION BY i.Item, i.Unidad, u.Cadena
                              ORDER BY u.Precio) AS rank
    FROM items i
    JOIN ult u ON u.rn = 1
        AND u.Nombre LIKE '%' + i.Item + '%'
        AND u.Unidad = i.Unidad
        AND (i.CategoriaCanonica IS NULL OR u.CategoriaCanonica = i.CategoriaCanonica)
        AND u.Precio >= 200
    WHERE NOT EXISTS (SELECT 1 FROM ref r WHERE r.Item = i.Item AND r.Cadena = u.Cadena)
),
cand AS (
    SELECT Item, Unidad, Cadena, Precio FROM cand_ref WHERE rank = 1
    UNION ALL
    SELECT Item, Unidad, Cadena, Precio FROM cand_gen WHERE rank = 1
)
SELECT i.Item,
       i.Unidad,
       CAST(MIN(CASE WHEN c.Cadena = 'cooperativa_obrera' THEN c.Precio END) AS decimal(18,2)) AS Coope,
       CAST(MIN(CASE WHEN c.Cadena = 'vea'                THEN c.Precio END) AS decimal(18,2)) AS Vea,
       CAST(MIN(CASE WHEN c.Cadena = 'carrefour'          THEN c.Precio END) AS decimal(18,2)) AS Carrefour,
       CAST(MIN(CASE WHEN c.Cadena = 'la_banderita'       THEN c.Precio END) AS decimal(18,2)) AS [La Banderita],
       CAST(MIN(c.Precio) AS decimal(18,2)) AS MasBarato
FROM items i
LEFT JOIN cand c ON c.Item = i.Item AND c.Unidad = i.Unidad
GROUP BY i.Item, i.Unidad;
GO
