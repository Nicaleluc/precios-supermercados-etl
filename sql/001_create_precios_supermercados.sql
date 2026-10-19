-- 001_create_precios_supermercados.sql
-- Dominio "Precios de supermercados" para SQL Server.
-- Bootstrap idempotente (SSMS / sqlcmd -i). Re-ejecutable sin riesgo.
--
-- Modelo estrella (prefijo de dominio "D_Precio*"):
--   1. D_PrecioCadena    : supermercados (Vea, Jumbo, Coope, DIA, ...).
--   2. D_PrecioSucursal  : sucursales/puntos de venta de cada cadena.
--   3. D_PrecioProducto  : productos (uno por cadena + SKU, con EAN).
--   4. D_PrecioOferta    : HECHOS. Precio en (Producto x Sucursal x Fecha).
--
-- Granularidad de precio (relevante): el online de VTEX/Coope es un precio
-- valido para TODA la cadena, no por local. Para no dejar SucursalId NULL se
-- crea UNA sucursal sintetica por cadena con CodigoSucursal='ONLINE'
-- (Tipo='ONLINE'); el precio por local (SEPA) usa la sucursal real.
--
-- Idempotencia:
--   D_PrecioProducto por (CadenaId, SkuId)
--   D_PrecioOferta   por (ProductoId, SucursalId, Fecha) -> re-correr el dia actualiza.
--
-- Comparar el mismo producto entre cadenas: JOIN por Ean (indice IX_.._Ean).
-- Si hiciera falta agrupar productos sin EAN (Coope), sumar despues una tabla
-- de equivalencia; no se incluye en esta version.
--
-- Collation de la base: Modern_Spanish_CI_AS.

SET NOCOUNT ON;
GO

-- 1) Cadenas (supermercados) --------------------------------------------
IF NOT EXISTS (
    SELECT 1 FROM sys.objects
    WHERE object_id = OBJECT_ID(N'dbo.D_PrecioCadena') AND type = N'U'
)
BEGIN
    CREATE TABLE dbo.D_PrecioCadena
    (
        CadenaId     TINYINT       IDENTITY(1,1) NOT NULL,
        Codigo       VARCHAR(40)   NOT NULL,  -- 'vea','jumbo','dia','coope',...
        Nombre       NVARCHAR(100) NOT NULL,
        Plataforma   VARCHAR(30)   NOT NULL CONSTRAINT DF_D_PrecioCadena_Plataforma DEFAULT ('VTEX'),
                                              -- VTEX | COOPE | WOO | CUSTOM | SEPA
        Host         VARCHAR(120)  NULL,      -- storefront (www.vea.com.ar)
        ApiHost      VARCHAR(120)  NULL,      -- host de la API si difiere (diaio.vtexcommercestable.com.br)
        CuentaVtex   VARCHAR(60)   NULL,      -- 'veaargentina','diaio',...
        Activa       BIT           NOT NULL CONSTRAINT DF_D_PrecioCadena_Activa DEFAULT (1),
        FechaAlta    DATETIME2     NOT NULL CONSTRAINT DF_D_PrecioCadena_FechaAlta DEFAULT (SYSDATETIME()),
        CONSTRAINT PK_D_PrecioCadena PRIMARY KEY CLUSTERED (CadenaId),
        CONSTRAINT UQ_D_PrecioCadena_Codigo UNIQUE (Codigo)
    );
END
GO

-- 2) Sucursales (puntos de venta) ---------------------------------------
IF NOT EXISTS (
    SELECT 1 FROM sys.objects
    WHERE object_id = OBJECT_ID(N'dbo.D_PrecioSucursal') AND type = N'U'
)
BEGIN
    CREATE TABLE dbo.D_PrecioSucursal
    (
        SucursalId      INT           IDENTITY(1,1) NOT NULL,
        CadenaId        TINYINT       NOT NULL,
        CodigoSucursal  VARCHAR(40)   NOT NULL,  -- codigo de la cadena, o 'ONLINE'
        Tipo            VARCHAR(20)   NOT NULL CONSTRAINT DF_D_PrecioSucursal_Tipo DEFAULT ('SUPER'),
                                                 -- SUPER | HIPER | EXPRESS | MAYORISTA | ONLINE
        Nombre          NVARCHAR(150) NULL,
        Direccion       NVARCHAR(200) NULL,
        Localidad       NVARCHAR(100) NULL,      -- 'Bahía Blanca'
        Provincia       NVARCHAR(60)  NULL,
        CodigoPostal    VARCHAR(12)   NULL,
        Latitud         DECIMAL(9,6)  NULL,
        Longitud        DECIMAL(9,6)  NULL,
        CodigoSepa      VARCHAR(40)   NULL,      -- id de comercio en SEPA (para cruzar)
        Activa          BIT           NOT NULL CONSTRAINT DF_D_PrecioSucursal_Activa DEFAULT (1),
        FechaAlta       DATETIME2     NOT NULL CONSTRAINT DF_D_PrecioSucursal_FechaAlta DEFAULT (SYSDATETIME()),
        CONSTRAINT PK_D_PrecioSucursal PRIMARY KEY CLUSTERED (SucursalId),
        CONSTRAINT UQ_D_PrecioSucursal_CadenaCodigo UNIQUE (CadenaId, CodigoSucursal),
        CONSTRAINT FK_D_PrecioSucursal_Cadena
            FOREIGN KEY (CadenaId) REFERENCES dbo.D_PrecioCadena (CadenaId)
    );
END
GO

-- 3) Productos (uno por cadena + SKU) -----------------------------------
IF NOT EXISTS (
    SELECT 1 FROM sys.objects
    WHERE object_id = OBJECT_ID(N'dbo.D_PrecioProducto') AND type = N'U'
)
BEGIN
    CREATE TABLE dbo.D_PrecioProducto
    (
        ProductoId     BIGINT        IDENTITY(1,1) NOT NULL,
        CadenaId       TINYINT       NOT NULL,
        SkuId          VARCHAR(40)   NOT NULL,  -- VTEX itemId / Coope cod_interno / Woo id
        ProductoExtId  VARCHAR(40)   NULL,      -- VTEX productId
        Ean            VARCHAR(14)   NULL,      -- codigo de barras (puede venir vacio)
        Nombre         NVARCHAR(300) NOT NULL,
        Marca          NVARCHAR(120) NULL,
        Categoria      NVARCHAR(300) NULL,      -- path completo (VTEX) o jerarquia Coope
        CategoriaId    VARCHAR(40)   NULL,
        Subcategoria   NVARCHAR(150) NULL,
        CategoriaCanonica VARCHAR(40) NULL,   -- rubro unificado entre cadenas
        Unidad         VARCHAR(10)   NULL,      -- 'un','kg'
        Multiplicador  DECIMAL(9,3)  NULL,      -- unitMultiplier
        ContenidoNeto  DECIMAL(12,3) NULL,      -- gramaje / contenido
        Url            NVARCHAR(500) NULL,
        Imagen         NVARCHAR(500) NULL,
        Descripcion    NVARCHAR(1000) NULL,
        CodigoRef      VARCHAR(60)   NULL,      -- RefId
        FechaPublicacion DATE        NULL,      -- releaseDate
        PrimeraVez     DATETIME2     NOT NULL CONSTRAINT DF_D_PrecioProducto_PrimeraVez DEFAULT (SYSDATETIME()),
        UltimaVez      DATETIME2     NOT NULL CONSTRAINT DF_D_PrecioProducto_UltimaVez  DEFAULT (SYSDATETIME()),
        CONSTRAINT PK_D_PrecioProducto PRIMARY KEY CLUSTERED (ProductoId),
        CONSTRAINT UQ_D_PrecioProducto_CadenaSku UNIQUE (CadenaId, SkuId),
        CONSTRAINT FK_D_PrecioProducto_Cadena
            FOREIGN KEY (CadenaId) REFERENCES dbo.D_PrecioCadena (CadenaId)
    );
END
GO

-- 4) Precios observados (hechos) ----------------------------------------
IF NOT EXISTS (
    SELECT 1 FROM sys.objects
    WHERE object_id = OBJECT_ID(N'dbo.D_PrecioOferta') AND type = N'U'
)
BEGIN
    CREATE TABLE dbo.D_PrecioOferta
    (
        OfertaId        BIGINT        IDENTITY(1,1) NOT NULL,
        ProductoId      BIGINT        NOT NULL,
        SucursalId      INT           NOT NULL,  -- sucursal real o 'ONLINE' de la cadena
        Fecha           DATE          NOT NULL,  -- dia de observacion
        Precio          DECIMAL(18,2) NOT NULL,
        PrecioLista     DECIMAL(18,2) NULL,      -- ListPrice / precio anterior
        PrecioSinImp    DECIMAL(18,2) NULL,      -- precio_sin_impuestos
        PrecioUnitario  DECIMAL(18,4) NULL,      -- por kg/l (Coope lo trae)
        EnPromo         BIT           NOT NULL CONSTRAINT DF_D_PrecioOferta_EnPromo DEFAULT (0),
        DescripcionPromo NVARCHAR(200) NULL,
        PromoDesde      DATE          NULL,
        PromoHasta      DATE          NULL,
        DescuentoPorc   DECIMAL(5,2)  NULL,
        Stock           INT           NULL,
        Moneda          CHAR(3)       NOT NULL CONSTRAINT DF_D_PrecioOferta_Moneda DEFAULT ('ARS'),
        Disponible      BIT           NOT NULL CONSTRAINT DF_D_PrecioOferta_Disponible DEFAULT (1),
        Origen          VARCHAR(20)   NOT NULL CONSTRAINT DF_D_PrecioOferta_Origen DEFAULT ('API'),
                                                 -- API | SEPA | SCRAPING
        FechaCarga      DATETIME2     NOT NULL CONSTRAINT DF_D_PrecioOferta_FechaCarga DEFAULT (SYSDATETIME()),
        CONSTRAINT PK_D_PrecioOferta PRIMARY KEY CLUSTERED (OfertaId),
        CONSTRAINT UQ_D_PrecioOferta_ProdSucFecha UNIQUE (ProductoId, SucursalId, Fecha),
        CONSTRAINT FK_D_PrecioOferta_Producto
            FOREIGN KEY (ProductoId) REFERENCES dbo.D_PrecioProducto (ProductoId),
        CONSTRAINT FK_D_PrecioOferta_Sucursal
            FOREIGN KEY (SucursalId) REFERENCES dbo.D_PrecioSucursal (SucursalId)
    );
END
GO

-- 5) Indices ------------------------------------------------------------
-- Comparar el mismo producto entre cadenas (por EAN).
IF NOT EXISTS (SELECT 1 FROM sys.indexes
    WHERE name = N'IX_D_PrecioProducto_Ean' AND object_id = OBJECT_ID(N'dbo.D_PrecioProducto'))
    CREATE INDEX IX_D_PrecioProducto_Ean
        ON dbo.D_PrecioProducto (Ean) INCLUDE (CadenaId, Nombre, Marca);
GO

-- Sucursales por localidad ("qué supers hay en Bahía Blanca").
IF NOT EXISTS (SELECT 1 FROM sys.indexes
    WHERE name = N'IX_D_PrecioSucursal_Localidad' AND object_id = OBJECT_ID(N'dbo.D_PrecioSucursal'))
    CREATE INDEX IX_D_PrecioSucursal_Localidad
        ON dbo.D_PrecioSucursal (Localidad, Provincia, CadenaId) INCLUDE (Tipo, Latitud, Longitud);
GO

-- Precios de una sucursal en una fecha (el caso "comparar en mi ciudad").
IF NOT EXISTS (SELECT 1 FROM sys.indexes
    WHERE name = N'IX_D_PrecioOferta_SucursalFecha' AND object_id = OBJECT_ID(N'dbo.D_PrecioOferta'))
    CREATE INDEX IX_D_PrecioOferta_SucursalFecha
        ON dbo.D_PrecioOferta (SucursalId, Fecha) INCLUDE (ProductoId, Precio, Disponible);
GO

-- Ultimo precio por producto y sucursal (min por ítem).
IF NOT EXISTS (SELECT 1 FROM sys.indexes
    WHERE name = N'IX_D_PrecioOferta_ProdSucFecha' AND object_id = OBJECT_ID(N'dbo.D_PrecioOferta'))
    CREATE INDEX IX_D_PrecioOferta_ProdSucFecha
        ON dbo.D_PrecioOferta (ProductoId, SucursalId, Fecha DESC) INCLUDE (Precio, Disponible);
GO

-- Serie por fecha (tendencias de precios).
IF NOT EXISTS (SELECT 1 FROM sys.indexes
    WHERE name = N'IX_D_PrecioOferta_Fecha' AND object_id = OBJECT_ID(N'dbo.D_PrecioOferta'))
    CREATE INDEX IX_D_PrecioOferta_Fecha
        ON dbo.D_PrecioOferta (Fecha) INCLUDE (ProductoId, SucursalId, Precio);
GO

-- 6) Migraciones (columnas agregadas despues de la v1) -------------------
IF COL_LENGTH('dbo.D_PrecioProducto', 'CategoriaCanonica') IS NULL
    ALTER TABLE dbo.D_PrecioProducto ADD CategoriaCanonica VARCHAR(40) NULL;
GO
