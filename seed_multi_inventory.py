from dotenv import load_dotenv
load_dotenv()

from app import create_app
from models import db, Product, ProductVariant, StockAdjustment, User

def seed_locales():
    app = create_app()
    with app.app_context():
        admin = User.query.filter_by(rol='admin').first() or User.query.first()
        admin_id = admin.id if admin else 1

        print("Generando productos de ejemplo para todos los inventarios (Local 1, Local 2, Local 3)...")

        productos_ejemplo = [
            {
                "sku": "AUD-PRO-MAX",
                "nombre": "Audífonos Inalámbricos ProMax ANC",
                "precio_costo": 45000,
                "precio_minimo": 75000,
                "precio_sugerido": 95000,
                "observacion": "Audífonos con Cancelación de Ruido y Bluetooth 5.3",
                "variantes": [
                    ("Negro Mate", 15, 10, 5),
                    ("Blanco Perla", 8, 20, 12),
                    ("Azul Medianoche", 5, 15, 18),
                ]
            },
            {
                "sku": "CASE-MAGSAFE-15PRO",
                "nombre": "Funda Silicona MagSafe iPhone 15 Pro",
                "precio_costo": 12000,
                "precio_minimo": 25000,
                "precio_sugerido": 35000,
                "observacion": "Funda suave al tacto con imanes para carga inalámbrica MagSafe",
                "variantes": [
                    ("Transparente Anti-Amarilleo", 30, 25, 20),
                    ("Negro Azabache", 20, 15, 10),
                    ("Rosa Pastel", 15, 10, 25),
                ]
            },
            {
                "sku": "CHG-25W-L1",
                "nombre": "Cargador Carga Rápida 25W USB-C (Local 1)",
                "precio_costo": 15000,
                "precio_minimo": 28000,
                "precio_sugerido": 40000,
                "observacion": "Cargador exclusivo en inventario del Local 1",
                "stock_l1": 45,
                "stock_l2": 0,
                "stock_l3": 0,
            },
            {
                "sku": "PWR-MAGSAFE-L2",
                "nombre": "Batería Portátil MagSafe 10,000 mAh (Local 2)",
                "precio_costo": 38000,
                "precio_minimo": 60000,
                "precio_sugerido": 85000,
                "observacion": "Powerbank magnética inalámbrica en inventario del Local 2",
                "stock_l1": 0,
                "stock_l2": 50,
                "stock_l3": 0,
            },
            {
                "sku": "HOLD-AUTO-L3",
                "nombre": "Soporte Magnético Automóvil para Rejilla (Local 3)",
                "precio_costo": 8000,
                "precio_minimo": 15000,
                "precio_sugerido": 25000,
                "observacion": "Soporte de auto de alta sujeción exclusivo del Local 3",
                "stock_l1": 0,
                "stock_l2": 0,
                "stock_l3": 60,
            },
            {
                "sku": "GLASS-TEMPERED-ALL",
                "nombre": "Cristal Templado de Pantalla 9H Privacidad",
                "precio_costo": 4000,
                "precio_minimo": 10000,
                "precio_sugerido": 18000,
                "observacion": "Protector de pantalla anti-espía distribuido en los 3 locales",
                "stock_l1": 100,
                "stock_l2": 80,
                "stock_l3": 75,
            }
        ]

        creados = 0
        for pdata in productos_ejemplo:
            existing = Product.query.filter_by(sku=pdata["sku"]).first()
            if existing:
                continue

            has_vars = "variantes" in pdata
            s1 = 0 if has_vars else pdata.get("stock_l1", 0)
            s2 = 0 if has_vars else pdata.get("stock_l2", 0)
            s3 = 0 if has_vars else pdata.get("stock_l3", 0)
            stot = s1 + s2 + s3

            prod = Product(
                sku=pdata["sku"],
                nombre=pdata["nombre"],
                tipo_inventario="tienda",
                stock_local_1=s1,
                stock_local_2=s2,
                stock_local_3=s3,
                cantidad_stock=stot,
                precio_costo=pdata["precio_costo"],
                precio_minimo=pdata["precio_minimo"],
                precio_sugerido=pdata["precio_sugerido"],
                observacion=pdata["observacion"]
            )
            db.session.add(prod)
            db.session.flush()

            if has_vars:
                for vnombre, vs1, vs2, vs3 in pdata["variantes"]:
                    vtot = vs1 + vs2 + vs3
                    v = ProductVariant(
                        product_id=prod.id,
                        nombre_variante=vnombre,
                        stock_local_1=vs1,
                        stock_local_2=vs2,
                        stock_local_3=vs3,
                        cantidad_stock=vtot,
                        precio_costo=pdata["precio_costo"],
                        precio_minimo=pdata["precio_minimo"],
                        precio_sugerido=pdata["precio_sugerido"]
                    )
                    db.session.add(v)

            ajuste = StockAdjustment(
                product_id=prod.id,
                admin_id=admin_id,
                tipo_movimiento="Creación Inicial (Productos de Ejemplo Multisede)",
                stock_anterior=0,
                stock_nuevo=prod.total_stock
            )
            db.session.add(ajuste)
            creados += 1

        db.session.commit()
        print(f"Se crearon exitosamente {creados} productos de ejemplo en todos los inventarios.")

if __name__ == "__main__":
    seed_locales()
