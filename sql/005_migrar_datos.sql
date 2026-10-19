-- 005_migrar_datos.sql
-- Copia los datos del dominio desde una base origen (OrigenDB) a la base nueva (cambia OrigenDB por tu base)
-- [precios-supermercados-etl] (mismo server). Ejecutar PARADO en la base nueva:
--   sqlcmd -S "localhost" -d "precios-supermercados-etl" -E -i sql\005_migrar_datos.sql
--
-- Orden por FKs: Cadena -> Sucursal -> Producto -> Oferta.
-- Conserva los IDs (IDENTITY_INSERT) y re-siembra las identidades.

SET NOCOUNT ON;

-- 1) Cadenas
SET IDENTITY_INSERT dbo.D_PrecioCadena ON;
INSERT INTO dbo.D_PrecioCadena
    (CadenaId, Codigo, Nombre, Plataforma, Host, ApiHost, CuentaVtex, Activa, FechaAlta)
SELECT CadenaId, Codigo, Nombre, Plataforma, Host, ApiHost, CuentaVtex, Activa, FechaAlta
FROM OrigenDB.dbo.D_PrecioCadena;
SET IDENTITY_INSERT dbo.D_PrecioCadena OFF;
GO

-- 2) Sucursales
SET IDENTITY_INSERT dbo.D_PrecioSucursal ON;
INSERT INTO dbo.D_PrecioSucursal
    (SucursalId, CadenaId, CodigoSucursal, Tipo, Nombre, Direccion, Localidad,
     Provincia, CodigoPostal, Latitud, Longitud, CodigoSepa, Activa, FechaAlta)
SELECT SucursalId, CadenaId, CodigoSucursal, Tipo, Nombre, Direccion, Localidad,
       Provincia, CodigoPostal, Latitud, Longitud, CodigoSepa, Activa, FechaAlta
FROM OrigenDB.dbo.D_PrecioSucursal;
SET IDENTITY_INSERT dbo.D_PrecioSucursal OFF;
GO

-- 3) Productos
SET IDENTITY_INSERT dbo.D_PrecioProducto ON;
INSERT INTO dbo.D_PrecioProducto
    (ProductoId, CadenaId, SkuId, ProductoExtId, Ean, Nombre, Marca, Categoria,
     CategoriaId, Subcategoria, CategoriaCanonica, Unidad, Multiplicador,
     ContenidoNeto, Url, Imagen, Descripcion, CodigoRef, FechaPublicacion,
     PrimeraVez, UltimaVez)
SELECT ProductoId, CadenaId, SkuId, ProductoExtId, Ean, Nombre, Marca, Categoria,
       CategoriaId, Subcategoria, CategoriaCanonica, Unidad, Multiplicador,
       ContenidoNeto, Url, Imagen, Descripcion, CodigoRef, FechaPublicacion,
       PrimeraVez, UltimaVez
FROM OrigenDB.dbo.D_PrecioProducto;
SET IDENTITY_INSERT dbo.D_PrecioProducto OFF;
GO

-- 4) Precios
SET IDENTITY_INSERT dbo.D_PrecioOferta ON;
INSERT INTO dbo.D_PrecioOferta
    (OfertaId, ProductoId, SucursalId, Fecha, Precio, PrecioLista, PrecioSinImp,
     PrecioUnitario, EnPromo, DescripcionPromo, PromoDesde, PromoHasta,
     DescuentoPorc, Stock, Moneda, Disponible, Origen, FechaCarga)
SELECT OfertaId, ProductoId, SucursalId, Fecha, Precio, PrecioLista, PrecioSinImp,
       PrecioUnitario, EnPromo, DescripcionPromo, PromoDesde, PromoHasta,
       DescuentoPorc, Stock, Moneda, Disponible, Origen, FechaCarga
FROM OrigenDB.dbo.D_PrecioOferta;
SET IDENTITY_INSERT dbo.D_PrecioOferta OFF;
GO

-- 5) Re-sembrar identidades (para inserciones futuras)
DBCC CHECKIDENT ('dbo.D_PrecioCadena', RESEED) WITH NO_INFOMSGS;
DBCC CHECKIDENT ('dbo.D_PrecioSucursal', RESEED) WITH NO_INFOMSGS;
DBCC CHECKIDENT ('dbo.D_PrecioProducto', RESEED) WITH NO_INFOMSGS;
DBCC CHECKIDENT ('dbo.D_PrecioOferta', RESEED) WITH NO_INFOMSGS;
GO
