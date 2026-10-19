"""Esquema del dominio de precios en SQL Server (idempotente).

Mismo DDL que `sql/001_create_precios_supermercados.sql`; el importador lo
ejecuta en cada corrida (`ensure_tablas`). Cada sentencia va por separado
(pyodbc no acepta lotes con GO).
"""
from __future__ import annotations

_DDL_CADENA = """
IF NOT EXISTS (SELECT 1 FROM sys.objects
    WHERE object_id = OBJECT_ID(N'dbo.D_PrecioCadena') AND type = N'U')
BEGIN
    CREATE TABLE dbo.D_PrecioCadena
    (
        CadenaId     TINYINT       IDENTITY(1,1) NOT NULL,
        Codigo       VARCHAR(40)   NOT NULL,
        Nombre       NVARCHAR(100) NOT NULL,
        Plataforma   VARCHAR(30)   NOT NULL CONSTRAINT DF_D_PrecioCadena_Plataforma DEFAULT ('VTEX'),
        Host         VARCHAR(120)  NULL,
        ApiHost      VARCHAR(120)  NULL,
        CuentaVtex   VARCHAR(60)   NULL,
        Activa       BIT           NOT NULL CONSTRAINT DF_D_PrecioCadena_Activa DEFAULT (1),
        FechaAlta    DATETIME2     NOT NULL CONSTRAINT DF_D_PrecioCadena_FechaAlta DEFAULT (SYSDATETIME()),
        CONSTRAINT PK_D_PrecioCadena PRIMARY KEY CLUSTERED (CadenaId),
        CONSTRAINT UQ_D_PrecioCadena_Codigo UNIQUE (Codigo)
    );
END
"""

_DDL_SUCURSAL = """
IF NOT EXISTS (SELECT 1 FROM sys.objects
    WHERE object_id = OBJECT_ID(N'dbo.D_PrecioSucursal') AND type = N'U')
BEGIN
    CREATE TABLE dbo.D_PrecioSucursal
    (
        SucursalId      INT           IDENTITY(1,1) NOT NULL,
        CadenaId        TINYINT       NOT NULL,
        CodigoSucursal  VARCHAR(40)   NOT NULL,
        Tipo            VARCHAR(20)   NOT NULL CONSTRAINT DF_D_PrecioSucursal_Tipo DEFAULT ('SUPER'),
        Nombre          NVARCHAR(150) NULL,
        Direccion       NVARCHAR(200) NULL,
        Localidad       NVARCHAR(100) NULL,
        Provincia       NVARCHAR(60)  NULL,
        CodigoPostal    VARCHAR(12)   NULL,
        Latitud         DECIMAL(9,6)  NULL,
        Longitud        DECIMAL(9,6)  NULL,
        CodigoSepa      VARCHAR(40)   NULL,
        Activa          BIT           NOT NULL CONSTRAINT DF_D_PrecioSucursal_Activa DEFAULT (1),
        FechaAlta       DATETIME2     NOT NULL CONSTRAINT DF_D_PrecioSucursal_FechaAlta DEFAULT (SYSDATETIME()),
        CONSTRAINT PK_D_PrecioSucursal PRIMARY KEY CLUSTERED (SucursalId),
        CONSTRAINT UQ_D_PrecioSucursal_CadenaCodigo UNIQUE (CadenaId, CodigoSucursal),
        CONSTRAINT FK_D_PrecioSucursal_Cadena
            FOREIGN KEY (CadenaId) REFERENCES dbo.D_PrecioCadena (CadenaId)
    );
END
"""

_DDL_PRODUCTO = """
IF NOT EXISTS (SELECT 1 FROM sys.objects
    WHERE object_id = OBJECT_ID(N'dbo.D_PrecioProducto') AND type = N'U')
BEGIN
    CREATE TABLE dbo.D_PrecioProducto
    (
        ProductoId     BIGINT        IDENTITY(1,1) NOT NULL,
        CadenaId       TINYINT       NOT NULL,
        SkuId          VARCHAR(40)   NOT NULL,
        ProductoExtId  VARCHAR(40)   NULL,
        Ean            VARCHAR(14)   NULL,
        Nombre         NVARCHAR(300) NOT NULL,
        Marca          NVARCHAR(120) NULL,
        Categoria      NVARCHAR(300) NULL,
        CategoriaId    VARCHAR(40)   NULL,
        Subcategoria   NVARCHAR(150) NULL,
        CategoriaCanonica VARCHAR(40) NULL,
        Unidad         VARCHAR(10)   NULL,
        Multiplicador  DECIMAL(9,3)  NULL,
        ContenidoNeto  DECIMAL(12,3) NULL,
        Url            NVARCHAR(500) NULL,
        Imagen         NVARCHAR(500) NULL,
        Descripcion    NVARCHAR(1000) NULL,
        CodigoRef      VARCHAR(60)   NULL,
        FechaPublicacion DATE        NULL,
        PrimeraVez     DATETIME2     NOT NULL CONSTRAINT DF_D_PrecioProducto_PrimeraVez DEFAULT (SYSDATETIME()),
        UltimaVez      DATETIME2     NOT NULL CONSTRAINT DF_D_PrecioProducto_UltimaVez  DEFAULT (SYSDATETIME()),
        CONSTRAINT PK_D_PrecioProducto PRIMARY KEY CLUSTERED (ProductoId),
        CONSTRAINT UQ_D_PrecioProducto_CadenaSku UNIQUE (CadenaId, SkuId),
        CONSTRAINT FK_D_PrecioProducto_Cadena
            FOREIGN KEY (CadenaId) REFERENCES dbo.D_PrecioCadena (CadenaId)
    );
END
"""

_DDL_OFERTA = """
IF NOT EXISTS (SELECT 1 FROM sys.objects
    WHERE object_id = OBJECT_ID(N'dbo.D_PrecioOferta') AND type = N'U')
BEGIN
    CREATE TABLE dbo.D_PrecioOferta
    (
        OfertaId        BIGINT        IDENTITY(1,1) NOT NULL,
        ProductoId      BIGINT        NOT NULL,
        SucursalId      INT           NOT NULL,
        Fecha           DATE          NOT NULL,
        Precio          DECIMAL(18,2) NOT NULL,
        PrecioLista     DECIMAL(18,2) NULL,
        PrecioSinImp    DECIMAL(18,2) NULL,
        PrecioUnitario  DECIMAL(18,4) NULL,
        EnPromo         BIT           NOT NULL CONSTRAINT DF_D_PrecioOferta_EnPromo DEFAULT (0),
        DescripcionPromo NVARCHAR(200) NULL,
        PromoDesde      DATE          NULL,
        PromoHasta      DATE          NULL,
        DescuentoPorc   DECIMAL(5,2)  NULL,
        Stock           INT           NULL,
        Moneda          CHAR(3)       NOT NULL CONSTRAINT DF_D_PrecioOferta_Moneda DEFAULT ('ARS'),
        Disponible      BIT           NOT NULL CONSTRAINT DF_D_PrecioOferta_Disponible DEFAULT (1),
        Origen          VARCHAR(20)   NOT NULL CONSTRAINT DF_D_PrecioOferta_Origen DEFAULT ('API'),
        FechaCarga      DATETIME2     NOT NULL CONSTRAINT DF_D_PrecioOferta_FechaCarga DEFAULT (SYSDATETIME()),
        CONSTRAINT PK_D_PrecioOferta PRIMARY KEY CLUSTERED (OfertaId),
        CONSTRAINT UQ_D_PrecioOferta_ProdSucFecha UNIQUE (ProductoId, SucursalId, Fecha),
        CONSTRAINT FK_D_PrecioOferta_Producto
            FOREIGN KEY (ProductoId) REFERENCES dbo.D_PrecioProducto (ProductoId),
        CONSTRAINT FK_D_PrecioOferta_Sucursal
            FOREIGN KEY (SucursalId) REFERENCES dbo.D_PrecioSucursal (SucursalId)
    );
END
"""

_DDL_INDICES = (
    """
    IF NOT EXISTS (SELECT 1 FROM sys.indexes
        WHERE name = N'IX_D_PrecioProducto_Ean' AND object_id = OBJECT_ID(N'dbo.D_PrecioProducto'))
        CREATE INDEX IX_D_PrecioProducto_Ean
            ON dbo.D_PrecioProducto (Ean) INCLUDE (CadenaId, Nombre, Marca)
    """,
    """
    IF NOT EXISTS (SELECT 1 FROM sys.indexes
        WHERE name = N'IX_D_PrecioSucursal_Localidad' AND object_id = OBJECT_ID(N'dbo.D_PrecioSucursal'))
        CREATE INDEX IX_D_PrecioSucursal_Localidad
            ON dbo.D_PrecioSucursal (Localidad, Provincia, CadenaId) INCLUDE (Tipo)
    """,
    """
    IF NOT EXISTS (SELECT 1 FROM sys.indexes
        WHERE name = N'IX_D_PrecioOferta_SucursalFecha' AND object_id = OBJECT_ID(N'dbo.D_PrecioOferta'))
        CREATE INDEX IX_D_PrecioOferta_SucursalFecha
            ON dbo.D_PrecioOferta (SucursalId, Fecha) INCLUDE (ProductoId, Precio, Disponible)
    """,
    """
    IF NOT EXISTS (SELECT 1 FROM sys.indexes
        WHERE name = N'IX_D_PrecioOferta_ProdSucFecha' AND object_id = OBJECT_ID(N'dbo.D_PrecioOferta'))
        CREATE INDEX IX_D_PrecioOferta_ProdSucFecha
            ON dbo.D_PrecioOferta (ProductoId, SucursalId, Fecha DESC) INCLUDE (Precio, Disponible)
    """,
    """
    IF NOT EXISTS (SELECT 1 FROM sys.indexes
        WHERE name = N'IX_D_PrecioOferta_Fecha' AND object_id = OBJECT_ID(N'dbo.D_PrecioOferta'))
        CREATE INDEX IX_D_PrecioOferta_Fecha
            ON dbo.D_PrecioOferta (Fecha) INCLUDE (ProductoId, SucursalId, Precio)
    """,
)

_DDL_ALTER = (
    # Columna agregada después de la v1 (idempotente para bases existentes).
    """
    IF COL_LENGTH('dbo.D_PrecioProducto', 'CategoriaCanonica') IS NULL
        ALTER TABLE dbo.D_PrecioProducto ADD CategoriaCanonica VARCHAR(40) NULL
    """,
)

_ESTATEMENTS = (_DDL_CADENA, _DDL_SUCURSAL, _DDL_PRODUCTO, _DDL_OFERTA) + _DDL_INDICES + _DDL_ALTER


def ensure_tablas(cursor, conn) -> None:
    """Crea tablas e índices si faltan (idempotente)."""
    for sentencia in _ESTATEMENTS:
        cursor.execute(sentencia)
    conn.commit()
