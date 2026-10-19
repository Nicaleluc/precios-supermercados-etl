-- 004_ref_productos.sql
-- Referencias: fija el SKU EXACTO por (Item, Cadena) para que la vista de compras
-- use el mismo producto que el usuario mira en la pagina (no el "mas barato generico").
-- PrecioPorKg: override cuando el producto se vende por pack y hay que expresar $/kg.
-- Ejecutar:  sqlcmd -S "localhost" -d precios-supermercados-etl -E -i sql\004_ref_productos.sql

SET NOCOUNT ON;

IF NOT EXISTS (SELECT 1 FROM sys.objects
    WHERE object_id = OBJECT_ID(N'dbo.D_CompraProductoRef') AND type = N'U')
BEGIN
    CREATE TABLE dbo.D_CompraProductoRef
    (
        Item       nvarchar(120) NOT NULL,
        Cadena     varchar(40)   NOT NULL,
        SkuId      varchar(40)   NOT NULL,
        PrecioPorKg decimal(18,2) NULL,   -- override ($/kg) para packs
        Notas      nvarchar(200) NULL,
        CONSTRAINT PK_D_CompraProductoRef PRIMARY KEY CLUSTERED (Item, Cadena)
    );
END
GO

MERGE dbo.D_CompraProductoRef AS t
USING (VALUES
    (N'Mandarina', 'vea',                '167937', NULL, NULL),
    (N'Mandarina', 'carrefour',          '7826',   NULL, NULL),
    (N'Kiwi',      'vea',                '10200',  NULL, NULL),
    (N'Kiwi',      'carrefour',          '50162',  NULL, NULL),
    (N'Frutilla',  'vea',                '10230',  NULL, NULL),
    (N'Frutilla',  'carrefour',          '11148',  NULL, NULL),
    (N'Banana',    'vea',                '148856', NULL, NULL),
    (N'Banana',    'carrefour',          '185818', NULL, NULL),
    (N'Brócoli',   'vea',                '10211',  NULL,     N'Precio por kg (el nombre "x 500 Grs" esta mal)'),
    (N'Brócoli',   'carrefour',          '8376',   NULL, NULL),
    (N'Chaucha',   'vea',                '24514',  NULL, NULL),
    (N'Chaucha',   'carrefour',          '8229',   NULL, NULL)
) AS s (Item, Cadena, SkuId, PrecioPorKg, Notas)
   ON t.Item = s.Item AND t.Cadena = s.Cadena
WHEN MATCHED THEN
    UPDATE SET t.SkuId = s.SkuId, t.PrecioPorKg = s.PrecioPorKg, t.Notas = s.Notas
WHEN NOT MATCHED THEN
    INSERT (Item, Cadena, SkuId, PrecioPorKg, Notas)
    VALUES (s.Item, s.Cadena, s.SkuId, s.PrecioPorKg, s.Notas);
GO
