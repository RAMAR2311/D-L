from datetime import datetime, timedelta
from decimal import Decimal
from app import create_app
from models import db, Sale, SaleDetail, SalePayment, User, obtener_hora_bogota

app = create_app()

with app.app_context():
    v1 = User.query.filter_by(email='vendedor1@dl.com').first()
    v2 = User.query.filter_by(email='vendedor2@dl.com').first()
    
    if not v1 or not v2:
        print("Vendedores no encontrados. Creando/verificando...")
        # Si no existen, los creamos
        from werkzeug.security import generate_password_hash
        if not v1:
            v1 = User(nombre="Vendedor Local Centro", email="vendedor1@dl.com", password_hash=generate_password_hash("Admin123"), rol="vendedor", local_asignado=1)
            db.session.add(v1)
        if not v2:
            v2 = User(nombre="Vendedor Local Norte", email="vendedor2@dl.com", password_hash=generate_password_hash("Admin123"), rol="vendedor", local_asignado=2)
            db.session.add(v2)
        db.session.commit()

    hoy = obtener_hora_bogota()
    
    sample_sales = [
        # Local 1 (vendedor1) - Ayer
        {
            "vendedor": v1,
            "local_id": 1,
            "dias_atras": 1,
            "items": [
                {"nombre_manual": "Funda Silicona iPhone 14 Pro", "cantidad": 2, "precio": 25000},
                {"nombre_manual": "Vidrio Templado 9D", "cantidad": 1, "precio": 15000}
            ],
            "metodos_pago": [("efectivo", 65000)]
        },
        {
            "vendedor": v1,
            "local_id": 1,
            "dias_atras": 1,
            "items": [
                {"nombre_manual": "Cargador Rápido 20W USB-C", "cantidad": 1, "precio": 45000}
            ],
            "metodos_pago": [("nequi", 45000)]
        },
        # Local 1 (vendedor1) - Hace 2 días
        {
            "vendedor": v1,
            "local_id": 1,
            "dias_atras": 2,
            "items": [
                {"nombre_manual": "Audífonos Bluetooth ProMax", "cantidad": 1, "precio": 85000},
                {"nombre_manual": "Cable Carga Rápida 2m", "cantidad": 1, "precio": 0} # Regalo
            ],
            "metodos_pago": [("efectivo", 35000), ("bancolombia", 50000)] # Pago mixto
        },
        # Local 1 (vendedor1) - Hace 4 días
        {
            "vendedor": v1,
            "local_id": 1,
            "dias_atras": 4,
            "items": [
                {"nombre_manual": "Soporte Celular Auto MagSafe", "cantidad": 1, "precio": 38000}
            ],
            "metodos_pago": [("daviplata", 38000)]
        },
        # Local 2 (vendedor2) - Ayer
        {
            "vendedor": v2,
            "local_id": 2,
            "dias_atras": 1,
            "items": [
                {"nombre_manual": "Powerbank 10.000 mAh Slim", "cantidad": 1, "precio": 70000},
                {"nombre_manual": "Cable USB-C 1m Trenzado", "cantidad": 1, "precio": 15000}
            ],
            "metodos_pago": [("efectivo", 85000)]
        },
        # Local 2 (vendedor2) - Hace 3 días
        {
            "vendedor": v2,
            "local_id": 2,
            "dias_atras": 3,
            "items": [
                {"nombre_manual": "Anillo de Luz LED Selfie", "cantidad": 2, "precio": 30000}
            ],
            "metodos_pago": [("bold", 60000)]
        },
        # Local 2 (vendedor2) - Hace 5 días
        {
            "vendedor": v2,
            "local_id": 2,
            "dias_atras": 5,
            "items": [
                {"nombre_manual": "Funda Uso Rudo Samsung S23", "cantidad": 1, "precio": 32000},
                {"nombre_manual": "Vidrio Cámara Trasera", "cantidad": 1, "precio": 12000}
            ],
            "metodos_pago": [("addi", 44000)]
        }
    ]
    
    ventas_creadas = 0
    for s_data in sample_sales:
        fecha = hoy - timedelta(days=s_data["dias_atras"])
        monto_total = sum(Decimal(str(item["cantidad"] * item["precio"])) for item in s_data["items"])
        
        metodo_principal = s_data["metodos_pago"][0][0] if len(s_data["metodos_pago"]) == 1 else "mixto"
        
        venta = Sale(
            vendedor_id=s_data["vendedor"].id,
            local_id=s_data["local_id"],
            fecha_venta=fecha,
            monto_total=monto_total,
            metodo_pago=metodo_principal
        )
        db.session.add(venta)
        db.session.flush()
        
        for item in s_data["items"]:
            det = SaleDetail(
                sale_id=venta.id,
                cantidad_vendida=item["cantidad"],
                precio_venta_final=Decimal(str(item["precio"])),
                nombre_manual=item["nombre_manual"]
            )
            db.session.add(det)
            
        for metodo, monto in s_data["metodos_pago"]:
            pago = SalePayment(
                sale_id=venta.id,
                metodo_pago=metodo,
                monto=Decimal(str(monto))
            )
            db.session.add(pago)
            
        ventas_creadas += 1
        
    db.session.commit()
    print(f"Se crearon exitosamente {ventas_creadas} ventas de ejemplo para dias pasados (Local 1 y Local 2).")
