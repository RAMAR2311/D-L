from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
import pytz

db = SQLAlchemy()

def obtener_hora_bogota():
    """Inyecta el uso de red horario en Colombia a nivel de sistema operativo."""
    return datetime.now(pytz.timezone('America/Bogota')).replace(tzinfo=None)

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    telefono = db.Column(db.String(20)) # Nuevo Campo de Contacto (Nullable por Defecto)
    password_hash = db.Column(db.String(256), nullable=False)
    rol = db.Column(db.String(50), nullable=False, default='vendedor')
    local_asignado = db.Column(db.Integer, nullable=True, default=1) # 1, 2, 3
    
    ventas = db.relationship('Sale', backref='vendedor', lazy=True)
    ajustes_stock = db.relationship('StockAdjustment', backref='admin', lazy=True)
    arqueos = db.relationship('ArqueoCaja', backref='cajero', lazy=True)

    def __init__(self, nombre=None, email=None, telefono=None, password_hash=None, rol=None, local_asignado=None, **kwargs):
        if nombre is not None: kwargs['nombre'] = nombre
        if email is not None: kwargs['email'] = email
        if telefono is not None: kwargs['telefono'] = telefono
        if password_hash is not None: kwargs['password_hash'] = password_hash
        if rol is not None: kwargs['rol'] = rol
        if local_asignado is not None: kwargs['local_asignado'] = local_asignado
        super(User, self).__init__(**kwargs)

class Product(db.Model):
    __tablename__ = 'products'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False)
    sku = db.Column(db.String(50), unique=True, nullable=False, index=True)
    tipo_inventario = db.Column(db.String(50), nullable=False, server_default='tienda') # 'tienda' o 'bodega'
    cantidad_stock = db.Column(db.Integer, nullable=False, default=0)
    precio_costo = db.Column(db.Numeric(10, 2), nullable=False, default=0.00) # El Costo de Bodega
    precio_minimo = db.Column(db.Numeric(10, 2), nullable=False)
    precio_sugerido = db.Column(db.Numeric(10, 2), nullable=False)
    imagen = db.Column(db.String(255), nullable=True) # Nombre de la foto subida
    observacion = db.Column(db.Text, nullable=True) # Nota descriptiva
    fecha_creacion = db.Column(db.DateTime, default=obtener_hora_bogota)
    
    
    detalles_venta = db.relationship('SaleDetail', backref='producto', lazy=True)
    ajustes_stock = db.relationship('StockAdjustment', backref='producto_rel', lazy=True)
    variantes = db.relationship('ProductVariant', backref='producto', lazy=True, cascade="all, delete-orphan")

    stock_local_1 = db.Column(db.Integer, nullable=False, default=0)
    stock_local_2 = db.Column(db.Integer, nullable=False, default=0)
    stock_local_3 = db.Column(db.Integer, nullable=False, default=0)
    descontar_inventario = db.Column(db.Boolean, nullable=False, default=False)

    def __init__(self, **kwargs):
        super(Product, self).__init__(**kwargs)

    @property
    def total_stock(self):
        if self.variantes:
            return sum(v.total_stock for v in self.variantes)
        return (self.stock_local_1 or 0) + (self.stock_local_2 or 0) + (self.stock_local_3 or 0)

    def get_stock_local(self, local_code='central'):
        local_code = str(local_code or 'central').lower()
        if self.variantes:
            return sum(v.get_stock_local(local_code) for v in self.variantes)
        if local_code in ['1', 'local1', 'local 1']:
            return self.stock_local_1 or 0
        elif local_code in ['2', 'local2', 'local 2']:
            return self.stock_local_2 or 0
        elif local_code in ['3', 'local3', 'local 3']:
            return self.stock_local_3 or 0
        else:
            return (self.stock_local_1 or 0) + (self.stock_local_2 or 0) + (self.stock_local_3 or 0)

    @property
    def rango_precios(self):
        if not self.variantes:
            return None
        precios = [v.precio_sugerido for v in self.variantes if v.precio_sugerido is not None]
        if not precios:
            return None
        min_p = min(precios)
        max_p = max(precios)
        if min_p == max_p:
            return min_p
        return (min_p, max_p)

    @property
    def rango_costos(self):
        if not self.variantes:
            return None
        precios = [v.precio_costo for v in self.variantes if v.precio_costo is not None]
        if not precios:
            return None
        min_p = min(precios)
        max_p = max(precios)
        if min_p == max_p:
            return min_p
        return (min_p, max_p)

    @property
    def rango_minimos(self):
        if not self.variantes:
            return None
        precios = [v.precio_minimo for v in self.variantes if v.precio_minimo is not None]
        if not precios:
            return None
        min_p = min(precios)
        max_p = max(precios)
        if min_p == max_p:
            return min_p
        return (min_p, max_p)

class ProductVariant(db.Model):
    __tablename__ = 'product_variants'

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    nombre_variante = db.Column(db.String(100), nullable=False)
    cantidad_stock = db.Column(db.Integer, nullable=False, default=0)
    stock_local_1 = db.Column(db.Integer, nullable=False, default=0)
    stock_local_2 = db.Column(db.Integer, nullable=False, default=0)
    stock_local_3 = db.Column(db.Integer, nullable=False, default=0)
    
    # Nuevos precios específicos para variantes
    precio_costo = db.Column(db.Numeric(10, 2), nullable=True) 
    precio_minimo = db.Column(db.Numeric(10, 2), nullable=True)
    precio_sugerido = db.Column(db.Numeric(10, 2), nullable=True)
    descontar_inventario = db.Column(db.Boolean, nullable=False, default=False)

    def __init__(self, **kwargs):
        super(ProductVariant, self).__init__(**kwargs)

    @property
    def total_stock(self):
        return (self.stock_local_1 or 0) + (self.stock_local_2 or 0) + (self.stock_local_3 or 0)

    def get_stock_local(self, local_code='central'):
        local_code = str(local_code or 'central').lower()
        if local_code in ['1', 'local1', 'local 1']:
            return self.stock_local_1 or 0
        elif local_code in ['2', 'local2', 'local 2']:
            return self.stock_local_2 or 0
        elif local_code in ['3', 'local3', 'local 3']:
            return self.stock_local_3 or 0
        else:
            return (self.stock_local_1 or 0) + (self.stock_local_2 or 0) + (self.stock_local_3 or 0)

class Sale(db.Model):
    __tablename__ = 'sales'
    
    id = db.Column(db.Integer, primary_key=True)
    vendedor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    asesor_id = db.Column(db.Integer, db.ForeignKey('asesores.id'), nullable=True)
    local_id = db.Column(db.Integer, nullable=True, default=1) # 1, 2, 3
    fecha_venta = db.Column(db.DateTime, default=obtener_hora_bogota)
    monto_total = db.Column(db.Numeric(10, 2), nullable=False, default=0.0)
    metodo_pago = db.Column(db.String(50), nullable=False, default='efectivo')

    detalles = db.relationship('SaleDetail', backref='venta', lazy=True, cascade="all, delete-orphan")
    pagos = db.relationship('SalePayment', backref='venta', lazy=True, cascade="all, delete-orphan")
    asesor = db.relationship('Asesor', backref='ventas', lazy=True)

    def __init__(self, **kwargs):
        super(Sale, self).__init__(**kwargs)

    @property
    def metodo_pago_display(self):
        """Retorna un resumen legible del método de pago.
        Si es pago único, retorna el nombre del método.
        Si es mixto, retorna 'Pago Mixto' con desglose."""
        if not self.pagos:
            # Retrocompatibilidad con ventas antiguas que solo tienen metodo_pago
            return self.metodo_pago.capitalize() if self.metodo_pago else 'Efectivo'
        if len(self.pagos) == 1:
            return self.pagos[0].metodo_pago.capitalize()
        return 'Pago Mixto'

class SalePayment(db.Model):
    """Modelo para soportar pagos mixtos/parciales por venta.
    Permite registrar múltiples métodos de pago en una sola venta.
    Ej: $50.000 en efectivo + $30.000 por Nequi = $80.000 total."""
    __tablename__ = 'sale_payments'

    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=False)
    metodo_pago = db.Column(db.String(50), nullable=False)  # efectivo, nequi, bancolombia, daviplata
    monto = db.Column(db.Numeric(10, 2), nullable=False)

    def __init__(self, **kwargs):
        super(SalePayment, self).__init__(**kwargs)



class SaleDetail(db.Model):
    __tablename__ = 'sale_details'
    
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True)
    variant_id = db.Column(db.Integer, db.ForeignKey('product_variants.id'), nullable=True)
    punto_id = db.Column(db.Integer, db.ForeignKey('puntos.id'), nullable=True)
    cantidad_vendida = db.Column(db.Integer, nullable=False)
    precio_venta_final = db.Column(db.Numeric(10, 2), nullable=False)
    # Campos para productos manuales (prestados de otros locales / puntos)
    nombre_manual = db.Column(db.String(200), nullable=True)
    precio_costo_manual = db.Column(db.Numeric(10, 2), nullable=True)

    variante = db.relationship('ProductVariant', backref='ventas_rel', lazy=True)
    punto = db.relationship('Punto', backref='detalles_venta', lazy=True)

    def __init__(self, **kwargs):
        super(SaleDetail, self).__init__(**kwargs)


class Punto(db.Model):
    __tablename__ = 'puntos'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False, unique=True)
    telefono = db.Column(db.String(50), nullable=True)
    direccion = db.Column(db.String(200), nullable=True)
    observaciones = db.Column(db.Text, nullable=True)
    fecha_creacion = db.Column(db.DateTime, default=obtener_hora_bogota)

    transacciones = db.relationship('PuntoTransaction', backref='punto', lazy=True, cascade='all, delete-orphan')

    def __init__(self, **kwargs):
        super(Punto, self).__init__(**kwargs)

    @property
    def saldo_deuda(self):
        cargos = sum((t.monto for t in self.transacciones if t.tipo_movimiento == 'cargo'), Decimal('0.00'))
        abonos = sum((t.monto for t in self.transacciones if t.tipo_movimiento == 'abono'), Decimal('0.00'))
        return Decimal(str(cargos)) - Decimal(str(abonos))


class PuntoTransaction(db.Model):
    __tablename__ = 'punto_transactions'

    id = db.Column(db.Integer, primary_key=True)
    punto_id = db.Column(db.Integer, db.ForeignKey('puntos.id'), nullable=False)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    tipo_movimiento = db.Column(db.String(20), nullable=False)  # 'cargo' o 'abono'
    monto = db.Column(db.Numeric(12, 2), nullable=False)
    metodo_pago = db.Column(db.String(50), nullable=True, default='efectivo')
    descripcion = db.Column(db.String(255), nullable=True)
    local_id = db.Column(db.Integer, nullable=True, default=1) # 1, 2, 3
    fecha = db.Column(db.DateTime, default=obtener_hora_bogota)

    usuario = db.relationship('User', backref='punto_transacciones', lazy=True)
    venta = db.relationship('Sale', backref='punto_transacciones', lazy=True)

    def __init__(self, **kwargs):
        super(PuntoTransaction, self).__init__(**kwargs)


class StockAdjustment(db.Model):
    __tablename__ = 'stock_adjustments'
    
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    tipo_movimiento = db.Column(db.String(100), nullable=True) # Ej: Creación Inicial, Ajuste Manual
    stock_anterior = db.Column(db.Integer, nullable=False)
    stock_nuevo = db.Column(db.Integer, nullable=False)
    fecha_ajuste = db.Column(db.DateTime, default=obtener_hora_bogota)

    def __init__(self, **kwargs):
        super(StockAdjustment, self).__init__(**kwargs)

class StockTransfer(db.Model):
    __tablename__ = 'stock_transfers'

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    variant_id = db.Column(db.Integer, db.ForeignKey('product_variants.id'), nullable=True)
    local_origen_id = db.Column(db.Integer, nullable=False)  # 1, 2, 3
    local_destino_id = db.Column(db.Integer, nullable=False) # 1, 2, 3
    cantidad = db.Column(db.Integer, nullable=False, default=1)
    usuario_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    asesor_id = db.Column(db.Integer, db.ForeignKey('asesores.id'), nullable=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=True)
    es_facturado = db.Column(db.Boolean, default=False)
    observacion = db.Column(db.String(255), nullable=True)
    fecha_transferencia = db.Column(db.DateTime, default=obtener_hora_bogota)

    producto = db.relationship('Product', backref='traslados', lazy=True)
    variante = db.relationship('ProductVariant', backref='traslados', lazy=True)
    usuario = db.relationship('User', backref='traslados_realizados', lazy=True)
    asesor = db.relationship('Asesor', backref='traslados_solicitados', lazy=True)
    venta = db.relationship('Sale', backref='traslados_asociados', lazy=True)

    def __init__(self, **kwargs):
        super(StockTransfer, self).__init__(**kwargs)

class ArqueoCaja(db.Model):
    __tablename__ = 'arqueo_caja'
    
    id = db.Column(db.Integer, primary_key=True)
    vendedor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    fecha_arqueo = db.Column(db.Date, nullable=False)

    base_inicial = db.Column(db.Numeric(10, 2), nullable=False, default=0.0)
    gastos_del_dia = db.Column(db.Numeric(10, 2), nullable=False, default=0.0)
    observaciones_gastos = db.Column(db.String(255), nullable=True)
    total_efectivo_sistema = db.Column(db.Numeric(10, 2), nullable=False, default=0.0)
    total_transferencia_sistema = db.Column(db.Numeric(10, 2), nullable=False, default=0.0)
    total_unidades_ch = db.Column(db.Numeric(10, 2), nullable=False, default=0.0)
    local_id = db.Column(db.Integer, nullable=True, default=1) # 1, 2, 3

    fecha_creacion = db.Column(db.DateTime, default=obtener_hora_bogota)

    def __init__(self, **kwargs):
        super(ArqueoCaja, self).__init__(**kwargs)

class Maneo(db.Model):
    __tablename__ = 'maneos'

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    variant_id = db.Column(db.Integer, db.ForeignKey('product_variants.id'), nullable=True)
    local_vecino = db.Column(db.String(150), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False)
    valor_unidad = db.Column(db.Numeric(12, 2), nullable=True, default=0)  # Valor pactado por unidad
    estado = db.Column(db.String(50), nullable=False, default='PENDIENTE') # PENDIENTE, FACTURADO, DEVUELTO
    fecha_prestamo = db.Column(db.DateTime, default=obtener_hora_bogota)
    fecha_resolucion = db.Column(db.DateTime, nullable=True)

    producto = db.relationship('Product', backref='maneos', lazy=True)
    variante = db.relationship('ProductVariant', backref='maneos_rel', lazy=True)

    def __init__(self, **kwargs):
        super(Maneo, self).__init__(**kwargs)

class Expense(db.Model):
    __tablename__ = 'expenses'
    
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    tipo_gasto = db.Column(db.String(50), nullable=False) # 'Gasto Diario' o 'Costo Indirecto'
    categoria = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.String(255), nullable=True)
    monto = db.Column(db.Numeric(10, 2), nullable=False)
    metodo_pago = db.Column(db.String(50), nullable=False, default='efectivo')
    local_id = db.Column(db.Integer, nullable=True, default=1) # 1, 2, 3
    fecha_gasto = db.Column(db.DateTime, default=obtener_hora_bogota)

    usuario = db.relationship('User', backref='gastos', lazy=True)

    def __init__(self, **kwargs):
        super(Expense, self).__init__(**kwargs)

class Cliente(db.Model):
    __tablename__ = 'clientes'

    id = db.Column(db.Integer, primary_key=True)
    nombre_o_razon_social = db.Column(db.String(150), nullable=False)
    documento_o_nit = db.Column(db.String(50), unique=True, nullable=False, index=True)
    telefono = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(120), nullable=True)
    direccion = db.Column(db.String(255), nullable=True)
    creado_por_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True) # ID del vendedor/admin que lo creó
    fecha_registro = db.Column(db.DateTime, default=obtener_hora_bogota)

    facturas = db.relationship('FacturaBodega', backref='cliente', lazy=True)
    abonos = db.relationship('AbonoBodega', backref='cliente', lazy=True)

    def __init__(self, **kwargs):
        super(Cliente, self).__init__(**kwargs)

    @property
    def total_contado(self):
        return sum(f.monto_total for f in self.facturas if f.modalidad == 'contado')

    @property
    def total_credito(self):
        return sum(f.monto_total for f in self.facturas if f.modalidad == 'credito')

    @property
    def total_abonado(self):
        # Solo sumamos abonos que NO son de facturas de contado (los de contado ya se reflejan en total_contado)
        return sum(a.monto for a in self.abonos if not (a.factura and a.factura.modalidad == 'contado'))

    @property
    def deuda_total(self):
        # La deuda es el total de crédito menos lo abonado a crédito o a cuenta global
        return self.total_credito - self.total_abonado

    @property
    def estado_global(self):
        return "Con Deuda" if self.deuda_total > 0 else "Al Día"

class FacturaBodega(db.Model):
    __tablename__ = 'facturas_bodega'

    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    numero_factura = db.Column(db.String(100), nullable=False)
    archivo_ruta = db.Column(db.String(255), nullable=True)
    monto_total = db.Column(db.Numeric(10, 2), nullable=False, default=0.0)
    modalidad = db.Column(db.String(50), nullable=False, default='credito') # contado o credito
    estado = db.Column(db.String(50), nullable=False, default='Pendiente') # Pendiente, Parcial, Pagado
    fecha_subida = db.Column(db.DateTime, default=obtener_hora_bogota)

    usuario = db.relationship('User', backref='facturas_subidas', lazy=True)
    abonos = db.relationship('AbonoBodega', backref='factura', lazy=True, cascade="all, delete-orphan")
    detalles = db.relationship('FacturaBodegaDetalle', backref='factura', lazy=True, cascade="all, delete-orphan")

    def __init__(self, **kwargs):
        super(FacturaBodega, self).__init__(**kwargs)

    @property
    def saldo_pendiente(self):
        # Esta propiedad se vuelve menos relevante con abonos globales, 
        # pero podemos mantenerla como una referencia teórica si no hay abonos.
        # Sin embargo, para no romper código existente, la dejamos así por ahora.
        total_abonado_factura = sum(abono.monto for abono in self.abonos) or 0
        return self.monto_total - total_abonado_factura

class FacturaBodegaDetalle(db.Model):
    __tablename__ = 'facturas_bodega_detalles'

    id = db.Column(db.Integer, primary_key=True)
    factura_id = db.Column(db.Integer, db.ForeignKey('facturas_bodega.id'), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    variant_id = db.Column(db.Integer, db.ForeignKey('product_variants.id'), nullable=True)
    cantidad = db.Column(db.Integer, nullable=False)
    precio_venta = db.Column(db.Numeric(10, 2), nullable=True) # Opcional para futuros análisis

    producto = db.relationship('Product', backref='detalles_factura_bodega', lazy=True)
    variante = db.relationship('ProductVariant', backref='detalles_factura_bodega_rel', lazy=True)

    def __init__(self, **kwargs):
        super(FacturaBodegaDetalle, self).__init__(**kwargs)

class AbonoBodega(db.Model):
    __tablename__ = 'abonos_bodega'

    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    factura_id = db.Column(db.Integer, db.ForeignKey('facturas_bodega.id'), nullable=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    monto = db.Column(db.Numeric(10, 2), nullable=False)
    metodo_pago = db.Column(db.String(50), nullable=False, default='efectivo')
    observacion = db.Column(db.String(255), nullable=True)
    fecha_abono = db.Column(db.DateTime, default=obtener_hora_bogota)

    usuario = db.relationship('User', backref='abonos_registrados', lazy=True)

    def __init__(self, **kwargs):
        super(AbonoBodega, self).__init__(**kwargs)

class LocalConfig(db.Model):
    __tablename__ = 'local_configs'

    id = db.Column(db.Integer, primary_key=True)
    local_id = db.Column(db.Integer, unique=True, nullable=False) # 1, 2, 3
    descontar_inventario = db.Column(db.Boolean, nullable=False, default=False)
    fecha_actualizacion = db.Column(db.DateTime, default=obtener_hora_bogota, onupdate=obtener_hora_bogota)

    def __init__(self, **kwargs):
        super(LocalConfig, self).__init__(**kwargs)


class Provider(db.Model):
    __tablename__ = 'providers'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False)
    empresa = db.Column(db.String(150), nullable=True)
    telefono = db.Column(db.String(50), nullable=True)
    fecha_creacion = db.Column(db.DateTime, default=obtener_hora_bogota)

    invoices = db.relationship('ProviderInvoice', backref='provider', lazy=True, cascade='all, delete-orphan')
    payments = db.relationship('ProviderPayment', backref='provider', lazy=True, cascade='all, delete-orphan')

    def __init__(self, **kwargs):
        super(Provider, self).__init__(**kwargs)


class ProviderInvoice(db.Model):
    __tablename__ = 'provider_invoices'

    id = db.Column(db.Integer, primary_key=True)
    provider_id = db.Column(db.Integer, db.ForeignKey('providers.id', ondelete='CASCADE'), nullable=False)
    monto_total = db.Column(db.Numeric(12, 2), nullable=False)
    numero_factura = db.Column(db.String(100), nullable=True)
    descripcion = db.Column(db.String(255), nullable=True)
    comprobante = db.Column(db.String(255), nullable=True)
    fecha_factura = db.Column(db.DateTime, default=obtener_hora_bogota)

    def __init__(self, **kwargs):
        super(ProviderInvoice, self).__init__(**kwargs)


class ProviderPayment(db.Model):
    __tablename__ = 'provider_payments'

    id = db.Column(db.Integer, primary_key=True)
    provider_id = db.Column(db.Integer, db.ForeignKey('providers.id', ondelete='CASCADE'), nullable=False)
    monto_abonado = db.Column(db.Numeric(12, 2), nullable=False)
    observacion = db.Column(db.String(255), nullable=True)
    fecha_pago = db.Column(db.DateTime, default=obtener_hora_bogota)

    def __init__(self, **kwargs):
        super(ProviderPayment, self).__init__(**kwargs)


class Asesor(db.Model):
    __tablename__ = 'asesores'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False)
    local_id = db.Column(db.Integer, nullable=False, default=1) # 1, 2, 3
    estado = db.Column(db.String(20), nullable=False, default='Activo') # 'Activo' o 'Inactivo'
    fecha_registro = db.Column(db.DateTime, default=obtener_hora_bogota)

    def __init__(self, **kwargs):
        super(Asesor, self).__init__(**kwargs)


