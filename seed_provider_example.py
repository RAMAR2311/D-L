from app import create_app
from models import db, Provider, ProviderInvoice, ProviderPayment, obtener_hora_bogota
from decimal import Decimal

app = create_app()

with app.app_context():
    print("Creando datos de ejemplo para el Módulo de Proveedores...")
    
    prov_existente = Provider.query.filter_by(nombre='Distribuidora Mayorista Celulares S.A.S.').first()
    if not prov_existente:
        prov = Provider(
            nombre='Distribuidora Mayorista Celulares S.A.S.',
            empresa='Mayorista Tech Colombia',
            telefono='+57 315 8887766',
            fecha_creacion=obtener_hora_bogota()
        )
        db.session.add(prov)
        db.session.commit()
        print(f"Proveedor creado: {prov.nombre} (ID: {prov.id})")

        # 2 Facturas de Ejemplo
        f1 = ProviderInvoice(
            provider_id=prov.id,
            monto_total=Decimal('2500000.00'),
            numero_factura='FAC-98401',
            descripcion='Compra de 30 Protectores de Pantalla y 20 Cargadores Carga Rápida',
            fecha_factura=obtener_hora_bogota()
        )
        f2 = ProviderInvoice(
            provider_id=prov.id,
            monto_total=Decimal('1200000.00'),
            numero_factura='FAC-98455',
            descripcion='Lote de Fundas Silicone Case y Cables Tipo-C',
            fecha_factura=obtener_hora_bogota()
        )
        db.session.add_all([f1, f2])

        # 1 Abono de Ejemplo
        a1 = ProviderPayment(
            provider_id=prov.id,
            monto_abonado=Decimal('1500000.00'),
            observacion='Abono inicial 50% por transferencia Bancolombia',
            fecha_pago=obtener_hora_bogota()
        )
        db.session.add(a1)
        db.session.commit()
        print("¡Facturas y abono de ejemplo guardados exitosamente!")
    else:
        print("El proveedor de ejemplo ya existía en la base de datos.")
