-- 006_precio_normal.sql
-- Vista de referencia: por EAN, el "precio normal" segun SEPA (mediana entre
-- sucursales), rango y cantidad de sucursales/promos.
-- Ejecutar:  sqlcmd -S "localhost" -d precios-supermercados-etl -E -i sql\006_precio_normal.sql

SET NOCOUNT ON;
GO

CREATE OR ALTER VIEW dbo.V_PrecioNormal
AS
WITH sepa AS (
    SELECT p.Ean, p.Nombre, o.Precio, o.PrecioLista, o.EnPromo, o.SucursalId
    FROM dbo.D_PrecioOferta o
    JOIN dbo.D_PrecioProducto p ON p.ProductoId = o.ProductoId
    WHERE o.Origen = 'SEPA' AND p.Ean IS NOT NULL
),
stats AS (
    SELECT Ean,
           MAX(Nombre)                          AS Nombre,
           COUNT(DISTINCT SucursalId)           AS N_Sucursales,
           MIN(Precio)                          AS PrecioMin,
           MAX(Precio)                          AS PrecioMax,
           AVG(Precio)                          AS PrecioPromedio,
           MAX(PrecioLista)                     AS PrecioReferencia,
           SUM(CASE WHEN EnPromo = 1 THEN 1 ELSE 0 END) AS N_Promo
    FROM sepa
    GROUP BY Ean
),
med AS (
    SELECT DISTINCT Ean,
           PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY Precio)
               OVER (PARTITION BY Ean) AS Mediana
    FROM sepa
)
SELECT s.Ean,
       s.Nombre,
       s.N_Sucursales,
       CAST(m.Mediana AS decimal(18,2))        AS PrecioNormal,
       CAST(s.PrecioMin AS decimal(18,2))      AS PrecioMin,
       CAST(s.PrecioMax AS decimal(18,2))      AS PrecioMax,
       CAST(s.PrecioPromedio AS decimal(18,2)) AS PrecioPromedio,
       CAST(s.PrecioReferencia AS decimal(18,2)) AS PrecioReferencia,
       s.N_Promo
FROM stats s
JOIN med m ON m.Ean = s.Ean;
GO
