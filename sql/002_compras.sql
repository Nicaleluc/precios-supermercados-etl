-- 002_compras.sql
-- Registro de compras (para comparar lo pagado contra precios de supermercado).
-- Ejecutar:  sqlcmd -S "localhost" -d precios-supermercados-etl -E -i sql\002_compras.sql
--
-- Diseno: 2 tablas (cabecera + detalle).
--   D_Compra        : una fila por compra (fecha, comercio, total).
--   D_CompraDetalle : una fila por item (cantidad/unidad y, si se tiene, precio).
-- Opcionales en el detalle: PrecioUnitario / Subtotal (para comparar exacto),
-- Ean / ProductoId (para cruzar con D_PrecioProducto) y CategoriaCanonica.

SET NOCOUNT ON;

IF NOT EXISTS (SELECT 1 FROM sys.objects
    WHERE object_id = OBJECT_ID(N'dbo.D_Compra') AND type = N'U')
BEGIN
    CREATE TABLE dbo.D_Compra
    (
        CompraId   int IDENTITY(1,1) NOT NULL,
        Fecha      date          NOT NULL,
        Comercio   nvarchar(120) NOT NULL,
        Total      decimal(18,2) NOT NULL,
        Notas      nvarchar(400) NULL,
        FechaCarga datetime2     NOT NULL CONSTRAINT DF_D_Compra_FechaCarga DEFAULT (SYSDATETIME()),
        CONSTRAINT PK_D_Compra PRIMARY KEY CLUSTERED (CompraId)
    );
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.objects
    WHERE object_id = OBJECT_ID(N'dbo.D_CompraDetalle') AND type = N'U')
BEGIN
    CREATE TABLE dbo.D_CompraDetalle
    (
        DetalleId       int IDENTITY(1,1) NOT NULL,
        CompraId        int           NOT NULL,
        Item            nvarchar(120) NOT NULL,
        Cantidad        decimal(10,3) NOT NULL,
        Unidad          varchar(10)   NOT NULL,   -- kg | un
        PrecioUnitario  decimal(18,2) NULL,       -- $/kg o $/un
        Subtotal        decimal(18,2) NULL,       -- cantidad * PrecioUnitario
        Ean             varchar(14)   NULL,
        ProductoId      bigint        NULL,       -- link a D_PrecioProducto (opcional)
        CategoriaCanonica varchar(40) NULL,
        Notas           nvarchar(200) NULL,
        CONSTRAINT PK_D_CompraDetalle PRIMARY KEY CLUSTERED (DetalleId),
        CONSTRAINT FK_D_CompraDetalle_Compra FOREIGN KEY (CompraId)
            REFERENCES dbo.D_Compra (CompraId)
    );
END
GO

-- Migracion idempotente (bases creadas antes de agregar estas columnas)
IF COL_LENGTH('dbo.D_CompraDetalle', 'PrecioUnitario') IS NULL
    ALTER TABLE dbo.D_CompraDetalle ADD PrecioUnitario decimal(18,2) NULL;
GO
IF COL_LENGTH('dbo.D_CompraDetalle', 'Subtotal') IS NULL
    ALTER TABLE dbo.D_CompraDetalle ADD Subtotal decimal(18,2) NULL;
GO
IF COL_LENGTH('dbo.D_CompraDetalle', 'Ean') IS NULL
    ALTER TABLE dbo.D_CompraDetalle ADD Ean varchar(14) NULL;
GO
IF COL_LENGTH('dbo.D_CompraDetalle', 'ProductoId') IS NULL
    ALTER TABLE dbo.D_CompraDetalle ADD ProductoId bigint NULL;
GO
IF COL_LENGTH('dbo.D_CompraDetalle', 'CategoriaCanonica') IS NULL
    ALTER TABLE dbo.D_CompraDetalle ADD CategoriaCanonica varchar(40) NULL;
GO

-- Compra de EJEMPLO (sintetica). Para cargar una compra real usa:
--   py -u -m cli.registrar_compra --comercio "..." --total ... --item "Nombre:Cantidad:Unidad"
IF NOT EXISTS (
    SELECT 1 FROM dbo.D_Compra
    WHERE Fecha = '2026-10-19' AND Comercio = N'Verdulería (ejemplo)' AND Total = 10000
)
BEGIN
    DECLARE @id int;
    INSERT INTO dbo.D_Compra (Fecha, Comercio, Total, Notas)
    VALUES ('2026-10-19', N'Verdulería (ejemplo)', 10000, N'Compra de ejemplo (sintética)');
    SET @id = SCOPE_IDENTITY();

    INSERT INTO dbo.D_CompraDetalle (CompraId, Item, Cantidad, Unidad, CategoriaCanonica, Notas) VALUES
        (@id, N'Mandarina', 1.000,  'kg', N'Frutas y Verduras', NULL),
        (@id, N'Kiwi',      0.500,  'kg', N'Frutas y Verduras', NULL),
        (@id, N'Frutilla',  0.250,  'kg', N'Frutas y Verduras', NULL),
        (@id, N'Banana',    0.540,  'kg', N'Frutas y Verduras', N'3 bananas (~0.18 kg c/u)'),
        (@id, N'Brócoli',   0.600,  'kg', N'Frutas y Verduras', N'1 brócoli grande (~0.6 kg)'),
        (@id, N'Chaucha',   0.250,  'kg', N'Frutas y Verduras', NULL);
END
GO
