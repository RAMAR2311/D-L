"""
Script para sembrar egresos de demostración en el Módulo de Tesorería y Flujo de Caja.
Genera ejemplos realistas de:
- Abonos a Proveedores
- Pagos a Puntos / Locales Aliados
- Gastos Operativos (Servicios, Nómina, Arriendos, Mantenimiento, Insumos)
Distribuidos entre Efectivo, Nequi, Bancolombia, Daviplata, Bold y Addi en Septiembre 2026.
"""

from app import create_app
from models import db, Expense, User, Punto, Provider
from datetime import datetime

app = create_app()

with app.app_context():
    print("Iniciando registro de egresos de ejemplo para Tesorería...")

    admin_user = User.query.filter_by(rol='admin').first() or User.query.first()
    vendedor_1 = User.query.filter_by(id=2).first() or admin_user
    vendedor_2 = User.query.filter_by(id=3).first() or admin_user

    egresos_ejemplo = [
        # --- 1. ABONOS A PROVEEDORES ---
        {
            'usuario_id': admin_user.id,
            'tipo_gasto': 'Costo Indirecto',
            'categoria': 'Abono a Proveedor',
            'descripcion': 'Abono Factura #FAC-98401 Tech Import Colombia (Protectores y Cargadores)',
            'monto': 850000.0,
            'metodo_pago': 'bancolombia',
            'local_id': 1,
            'fecha_gasto': datetime(2026, 9, 4, 11, 30)
        },
        {
            'usuario_id': admin_user.id,
            'tipo_gasto': 'Costo Indirecto',
            'categoria': 'Abono a Proveedor',
            'descripcion': 'Abono Factura Lote Textil & Jeans Denim Mayorista',
            'monto': 620000.0,
            'metodo_pago': 'bancolombia',
            'local_id': 2,
            'fecha_gasto': datetime(2026, 9, 7, 14, 15)
        },
        {
            'usuario_id': vendedor_2.id,
            'tipo_gasto': 'Costo Indirecto',
            'categoria': 'Abono a Proveedor',
            'descripcion': 'Pago Factura Lote Protectores y Accesorios Celulares',
            'monto': 380000.0,
            'metodo_pago': 'bold',
            'local_id': 3,
            'fecha_gasto': datetime(2026, 9, 9, 16, 45)
        },
        {
            'usuario_id': vendedor_1.id,
            'tipo_gasto': 'Costo Indirecto',
            'categoria': 'Abono a Proveedor',
            'descripcion': 'Abono Proveedor Empaques y Bolsas Biodegradables D&L',
            'monto': 210000.0,
            'metodo_pago': 'nequi',
            'local_id': 1,
            'fecha_gasto': datetime(2026, 9, 11, 10, 20)
        },
        {
            'usuario_id': admin_user.id,
            'tipo_gasto': 'Costo Indirecto',
            'categoria': 'Abono a Proveedor',
            'descripcion': 'Abono Proveedor Calzado Deportivo y Gorras Urbanas',
            'monto': 550000.0,
            'metodo_pago': 'bancolombia',
            'local_id': 2,
            'fecha_gasto': datetime(2026, 9, 13, 15, 50)
        },
        {
            'usuario_id': admin_user.id,
            'tipo_gasto': 'Costo Indirecto',
            'categoria': 'Abono a Proveedor',
            'descripcion': 'Anticipo Proveedor Colección Fin de Año y Tendencias',
            'monto': 450000.0,
            'metodo_pago': 'addi',
            'local_id': 1,
            'fecha_gasto': datetime(2026, 9, 15, 12, 10)
        },
        {
            'usuario_id': vendedor_2.id,
            'tipo_gasto': 'Costo Indirecto',
            'categoria': 'Abono a Proveedor',
            'descripcion': 'Abono Factura Marquillas, Etiquetas y Accesorios',
            'monto': 140000.0,
            'metodo_pago': 'daviplata',
            'local_id': 3,
            'fecha_gasto': datetime(2026, 9, 16, 9, 40)
        },

        # --- 2. PAGOS A PUNTOS / LOCALES ALIADOS ---
        {
            'usuario_id': vendedor_1.id,
            'tipo_gasto': 'Gasto Diario',
            'categoria': 'Pago a Punto',
            'descripcion': 'Liquidación semanal de prendas prestadas Punto San Victorino #4',
            'monto': 320000.0,
            'metodo_pago': 'efectivo',
            'local_id': 1,
            'fecha_gasto': datetime(2026, 9, 3, 17, 30)
        },
        {
            'usuario_id': vendedor_2.id,
            'tipo_gasto': 'Gasto Diario',
            'categoria': 'Pago a Punto',
            'descripcion': 'Abono de saldo a Local San José - Accesorios',
            'monto': 240000.0,
            'metodo_pago': 'nequi',
            'local_id': 2,
            'fecha_gasto': datetime(2026, 9, 6, 11, 45)
        },
        {
            'usuario_id': vendedor_1.id,
            'tipo_gasto': 'Gasto Diario',
            'categoria': 'Pago a Punto',
            'descripcion': 'Pago a Punto Aliado Celulares & Más - Centro',
            'monto': 190000.0,
            'metodo_pago': 'daviplata',
            'local_id': 1,
            'fecha_gasto': datetime(2026, 9, 8, 16, 10)
        },
        {
            'usuario_id': vendedor_2.id,
            'tipo_gasto': 'Gasto Diario',
            'categoria': 'Pago a Punto',
            'descripcion': 'Abono de saldo Servicio Técnico Don Carlos',
            'monto': 160000.0,
            'metodo_pago': 'efectivo',
            'local_id': 3,
            'fecha_gasto': datetime(2026, 9, 10, 18, 00)
        },
        {
            'usuario_id': vendedor_2.id,
            'tipo_gasto': 'Gasto Diario',
            'categoria': 'Pago a Punto',
            'descripcion': 'Pago de comisión y traslado Punto San Victorino #4',
            'monto': 280000.0,
            'metodo_pago': 'nequi',
            'local_id': 2,
            'fecha_gasto': datetime(2026, 9, 12, 13, 20)
        },
        {
            'usuario_id': admin_user.id,
            'tipo_gasto': 'Gasto Diario',
            'categoria': 'Pago a Punto',
            'descripcion': 'Liquidación de inventario compartido Punto San José',
            'monto': 310000.0,
            'metodo_pago': 'bancolombia',
            'local_id': 1,
            'fecha_gasto': datetime(2026, 9, 14, 16, 30)
        },
        {
            'usuario_id': vendedor_2.id,
            'tipo_gasto': 'Gasto Diario',
            'categoria': 'Pago a Punto',
            'descripcion': 'Abono quincenal consolidado Celulares & Más',
            'monto': 220000.0,
            'metodo_pago': 'efectivo',
            'local_id': 3,
            'fecha_gasto': datetime(2026, 9, 16, 11, 15)
        },

        # --- 3. GASTOS OPERATIVOS ---
        {
            'usuario_id': admin_user.id,
            'tipo_gasto': 'Costo Indirecto',
            'categoria': 'Arriendo Local',
            'descripcion': 'Canon de arrendamiento Sede Central D&L 1 Mes Septiembre',
            'monto': 1200000.0,
            'metodo_pago': 'bancolombia',
            'local_id': 1,
            'fecha_gasto': datetime(2026, 9, 2, 9, 00)
        },
        {
            'usuario_id': vendedor_2.id,
            'tipo_gasto': 'Gasto Diario',
            'categoria': 'Servicios Públicos',
            'descripcion': 'Pago de factura de energía y acueducto Sede Norte',
            'monto': 245000.0,
            'metodo_pago': 'daviplata',
            'local_id': 2,
            'fecha_gasto': datetime(2026, 9, 5, 10, 30)
        },
        {
            'usuario_id': vendedor_2.id,
            'tipo_gasto': 'Gasto Diario',
            'categoria': 'Internet & Conectividad',
            'descripcion': 'Pago mensual Internet Fibra Óptica Claro y Red POS',
            'monto': 115000.0,
            'metodo_pago': 'nequi',
            'local_id': 3,
            'fecha_gasto': datetime(2026, 9, 6, 15, 40)
        },
        {
            'usuario_id': vendedor_1.id,
            'tipo_gasto': 'Gasto Diario',
            'categoria': 'Anticipo Nómina',
            'descripcion': 'Anticipo quincenal asesor comercial en caja',
            'monto': 350000.0,
            'metodo_pago': 'efectivo',
            'local_id': 1,
            'fecha_gasto': datetime(2026, 9, 8, 12, 00)
        },
        {
            'usuario_id': vendedor_2.id,
            'tipo_gasto': 'Gasto Diario',
            'categoria': 'Insumos y Cafetería',
            'descripcion': 'Compra café, agua, refrigerios y productos de aseo',
            'monto': 75000.0,
            'metodo_pago': 'efectivo',
            'local_id': 2,
            'fecha_gasto': datetime(2026, 9, 9, 11, 10)
        },
        {
            'usuario_id': vendedor_2.id,
            'tipo_gasto': 'Gasto Diario',
            'categoria': 'Mantenimiento & Reparaciones',
            'descripcion': 'Mantenimiento preventivo vitrinas e iluminación LED',
            'monto': 135000.0,
            'metodo_pago': 'efectivo',
            'local_id': 3,
            'fecha_gasto': datetime(2026, 9, 10, 16, 20)
        },
        {
            'usuario_id': admin_user.id,
            'tipo_gasto': 'Costo Indirecto',
            'categoria': 'Publicidad & Marketing',
            'descripcion': 'Campaña Meta Ads Instagram & Facebook D&L Colección',
            'monto': 180000.0,
            'metodo_pago': 'bold',
            'local_id': 1,
            'fecha_gasto': datetime(2026, 9, 11, 18, 30)
        },
        {
            'usuario_id': vendedor_1.id,
            'tipo_gasto': 'Gasto Diario',
            'categoria': 'Transportes & Fletes',
            'descripcion': 'Viáticos y transporte flete intermunicipal de reposición',
            'monto': 95000.0,
            'metodo_pago': 'efectivo',
            'local_id': 2,
            'fecha_gasto': datetime(2026, 9, 13, 14, 00)
        },
        {
            'usuario_id': vendedor_1.id,
            'tipo_gasto': 'Gasto Diario',
            'categoria': 'Papelería & Insumos POS',
            'descripcion': 'Rollos de papel térmico, bolsas y cinta embalaje',
            'monto': 60000.0,
            'metodo_pago': 'daviplata',
            'local_id': 1,
            'fecha_gasto': datetime(2026, 9, 14, 10, 45)
        },
        {
            'usuario_id': vendedor_2.id,
            'tipo_gasto': 'Gasto Diario',
            'categoria': 'Comisiones Bancarias',
            'descripcion': 'Comisión uso de datáfono Bold e intermediación financiera',
            'monto': 45000.0,
            'metodo_pago': 'bold',
            'local_id': 3,
            'fecha_gasto': datetime(2026, 9, 15, 17, 10)
        },
        {
            'usuario_id': vendedor_2.id,
            'tipo_gasto': 'Gasto Diario',
            'categoria': 'Gastos Varios',
            'descripcion': 'Reunión de coordinación comercial y refrigerios de equipo',
            'monto': 85000.0,
            'metodo_pago': 'nequi',
            'local_id': 2,
            'fecha_gasto': datetime(2026, 9, 16, 12, 30)
        }
    ]

    creados = 0
    for eg in egresos_ejemplo:
        nuevo_g = Expense(
            usuario_id=eg['usuario_id'],
            tipo_gasto=eg['tipo_gasto'],
            categoria=eg['categoria'],
            descripcion=eg['descripcion'],
            monto=eg['monto'],
            metodo_pago=eg['metodo_pago'],
            local_id=eg['local_id'],
            fecha_gasto=eg['fecha_gasto']
        )
        db.session.add(nuevo_g)
        creados += 1

    db.session.commit()
    print(f"¡Éxito! Se registraron {creados} nuevos egresos de ejemplo.")
