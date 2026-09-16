"""
Script para registrar ventas realistas de mostrador en Septiembre 2026.
Garantiza un balance financiero saludable (Superávit) en todos los locales
y en todas las pasarelas (Efectivo, Nequi, Bancolombia, Daviplata, Bold, Addi).
"""

from app import create_app
from models import db, Sale, SaleDetail, SalePayment, User, Product
from datetime import datetime
from decimal import Decimal

app = create_app()

with app.app_context():
    print("Iniciando inyección de ventas para balancear flujo de caja en Superávit...")

    u_admin = User.query.filter_by(rol='admin').first() or User.query.first()
    v1 = User.query.filter_by(id=2).first() or u_admin
    v2 = User.query.filter_by(id=3).first() or u_admin

    ventas_nuevas = [
        # --- BANCOLOMBIA (Ventas de volumen y tecnología para dejarlo en positivo) ---
        {
            'fecha': datetime(2026, 9, 3, 11, 20),
            'local_id': 1,
            'vendedor_id': v1.id,
            'monto': 1450000.0,
            'metodo': 'bancolombia',
            'detalles': [
                {'nombre': 'Combo Smartwatch Pro + 3 Correas Deportivas', 'cant': 2, 'precio': 450000.0},
                {'nombre': 'Audífonos Cancelación de Ruido ANC High-End', 'cant': 1, 'precio': 550000.0}
            ]
        },
        {
            'fecha': datetime(2026, 9, 5, 15, 45),
            'local_id': 2,
            'vendedor_id': v2.id,
            'monto': 1850000.0,
            'metodo': 'bancolombia',
            'detalles': [
                {'nombre': 'Parlante Bluetooth JBL Charge 5 Original', 'cant': 2, 'precio': 680000.0},
                {'nombre': 'PowerBank Anker 20.000mAh Carga Rápida 65W', 'cant': 2, 'precio': 245000.0}
            ]
        },
        {
            'fecha': datetime(2026, 9, 8, 14, 10),
            'local_id': 1,
            'vendedor_id': v1.id,
            'monto': 2100000.0,
            'metodo': 'bancolombia',
            'detalles': [
                {'nombre': 'Combo Accesorios Mayorista (30 Fundas + 20 Vidrios)', 'cant': 1, 'precio': 2100000.0}
            ]
        },
        {
            'fecha': datetime(2026, 9, 11, 16, 30),
            'local_id': 3,
            'vendedor_id': u_admin.id,
            'monto': 1650000.0,
            'metodo': 'bancolombia',
            'detalles': [
                {'nombre': 'Cámara de Seguridad WiFi 360 Exterior (Pack x4)', 'cant': 2, 'precio': 525000.0},
                {'nombre': 'Gimbal Estabilizador Celular DJI OM 6', 'cant': 1, 'precio': 600000.0}
            ]
        },
        {
            'fecha': datetime(2026, 9, 14, 17, 00),
            'local_id': 2,
            'vendedor_id': v2.id,
            'monto': 1950000.0,
            'metodo': 'bancolombia',
            'detalles': [
                {'nombre': 'Lote 15 Cargadores MagSafe Originales Apple', 'cant': 1, 'precio': 1950000.0}
            ]
        },

        # --- EFECTIVO (Ventas de mostrador diarias) ---
        {
            'fecha': datetime(2026, 9, 4, 10, 15),
            'local_id': 1,
            'vendedor_id': v1.id,
            'monto': 420000.0,
            'metodo': 'efectivo',
            'detalles': [
                {'nombre': 'Funda Silicona Antigolpes iPhone 15 Pro', 'cant': 4, 'precio': 45000.0},
                {'nombre': 'Vidrio Cerámica Mate Privacidad', 'cant': 4, 'precio': 35000.0},
                {'nombre': 'Cable USB-C Carga Rápida 2 Metros', 'cant': 2, 'precio': 50000.0}
            ]
        },
        {
            'fecha': datetime(2026, 9, 7, 12, 30),
            'local_id': 2,
            'vendedor_id': v2.id,
            'monto': 560000.0,
            'metodo': 'efectivo',
            'detalles': [
                {'nombre': 'Soporte Magnético Auto Carga Inalámbrica', 'cant': 4, 'precio': 75000.0},
                {'nombre': 'Adaptador Carga Rápida 35W Dual Port', 'cant': 2, 'precio': 85000.0},
                {'nombre': 'Audífonos In-Ear Cable Tipo-C', 'cant': 3, 'precio': 30000.0}
            ]
        },
        {
            'fecha': datetime(2026, 9, 9, 15, 00),
            'local_id': 3,
            'vendedor_id': u_admin.id,
            'monto': 680000.0,
            'metodo': 'efectivo',
            'detalles': [
                {'nombre': 'Ring Light Aro de Luz LED 12 Pulgadas', 'cant': 4, 'precio': 85000.0},
                {'nombre': 'Micrófono Inalámbrico Solapa K9 Dual', 'cant': 2, 'precio': 120000.0},
                {'nombre': 'Vidrio Cámara Posterior iPhone 14/15', 'cant': 5, 'precio': 20000.0}
            ]
        },
        {
            'fecha': datetime(2026, 9, 12, 11, 40),
            'local_id': 1,
            'vendedor_id': v1.id,
            'monto': 750000.0,
            'metodo': 'efectivo',
            'detalles': [
                {'nombre': 'Kit Gamer Teclado + Mouse RGB + Pad', 'cant': 3, 'precio': 150000.0},
                {'nombre': 'Diadema Gamer con Micrófono 7.1', 'cant': 2, 'precio': 150000.0}
            ]
        },
        {
            'fecha': datetime(2026, 9, 15, 14, 20),
            'local_id': 2,
            'vendedor_id': v2.id,
            'monto': 890000.0,
            'metodo': 'efectivo',
            'detalles': [
                {'nombre': 'Mochila Antirrobo Impermeable con Puerto USB', 'cant': 4, 'precio': 120000.0},
                {'nombre': 'Batería Portátil MagSafe 10.000mAh', 'cant': 3, 'precio': 110000.0},
                {'nombre': 'Correas Smartwatch Ultra Titanium', 'cant': 2, 'precio': 40000.0}
            ]
        },

        # --- NEQUI ---
        {
            'fecha': datetime(2026, 9, 4, 16, 20),
            'local_id': 1,
            'vendedor_id': v1.id,
            'monto': 620000.0,
            'metodo': 'nequi',
            'detalles': [
                {'nombre': 'AirPods Pro 2da Gen Réplica Premium 1:1', 'cant': 2, 'precio': 180000.0},
                {'nombre': 'Cargador Trío 3 en 1 Plegable Inalámbrico', 'cant': 2, 'precio': 130000.0}
            ]
        },
        {
            'fecha': datetime(2026, 9, 7, 17, 10),
            'local_id': 2,
            'vendedor_id': v2.id,
            'monto': 780000.0,
            'metodo': 'nequi',
            'detalles': [
                {'nombre': 'Smartwatch Serie 9 Full Pantalla AMOLED', 'cant': 3, 'precio': 210000.0},
                {'nombre': 'Funda Transparente Espacio Airbag x3', 'cant': 3, 'precio': 50000.0}
            ]
        },
        {
            'fecha': datetime(2026, 9, 10, 13, 00),
            'local_id': 3,
            'vendedor_id': u_admin.id,
            'monto': 850000.0,
            'metodo': 'nequi',
            'detalles': [
                {'nombre': 'Combo Parlante Karaoke Portátil con Micrófono', 'cant': 2, 'precio': 280000.0},
                {'nombre': 'Consola Retro GameStick 4K 20.000 Juegos', 'cant': 2, 'precio': 145000.0}
            ]
        },
        {
            'fecha': datetime(2026, 9, 13, 16, 40),
            'local_id': 1,
            'vendedor_id': v1.id,
            'monto': 920000.0,
            'metodo': 'nequi',
            'detalles': [
                {'nombre': 'Impresora Térmica Portátil Bluetooth 58mm', 'cant': 2, 'precio': 220000.0},
                {'nombre': 'Lector de Código de Barras Láser USB', 'cant': 2, 'precio': 160000.0},
                {'nombre': 'Rollos de Papel Térmico x50', 'cant': 1, 'precio': 160000.0}
            ]
        },

        # --- DAVIPLATA ---
        {
            'fecha': datetime(2026, 9, 5, 11, 00),
            'local_id': 2,
            'vendedor_id': v2.id,
            'monto': 490000.0,
            'metodo': 'daviplata',
            'detalles': [
                {'nombre': 'Audífonos Deportivos Conducción Ósea', 'cant': 2, 'precio': 165000.0},
                {'nombre': 'SmartBand Pulsera Inteligente M8', 'cant': 2, 'precio': 80000.0}
            ]
        },
        {
            'fecha': datetime(2026, 9, 9, 14, 50),
            'local_id': 1,
            'vendedor_id': v1.id,
            'monto': 580000.0,
            'metodo': 'daviplata',
            'detalles': [
                {'nombre': 'Funda Sumergible Celular Acuática x6', 'cant': 6, 'precio': 35000.0},
                {'nombre': 'PowerBank Solar 30.000mAh para Camping', 'cant': 2, 'precio': 185000.0}
            ]
        },
        {
            'fecha': datetime(2026, 9, 14, 15, 15),
            'local_id': 3,
            'vendedor_id': u_admin.id,
            'monto': 650000.0,
            'metodo': 'daviplata',
            'detalles': [
                {'nombre': 'Kit Limpieza Celular 8 en 1 Multifunción x5', 'cant': 5, 'precio': 45000.0},
                {'nombre': 'Hub USB-C 7 en 1 HDMI 4K + SD + PD 100W', 'cant': 2, 'precio': 212500.0}
            ]
        },

        # --- BOLD (Datáfono) ---
        {
            'fecha': datetime(2026, 9, 6, 17, 30),
            'local_id': 1,
            'vendedor_id': v1.id,
            'monto': 880000.0,
            'metodo': 'bold',
            'detalles': [
                {'nombre': 'Smartwatch Hello Watch 3 Plus AMOLED 4GB', 'cant': 2, 'precio': 320000.0},
                {'nombre': 'Correa de Acero Inoxidable Milanesa', 'cant': 4, 'precio': 60000.0}
            ]
        },
        {
            'fecha': datetime(2026, 9, 11, 15, 00),
            'local_id': 2,
            'vendedor_id': v2.id,
            'monto': 1150000.0,
            'metodo': 'bold',
            'detalles': [
                {'nombre': 'Tablet Infantil Educativa 10 Pulgadas con Estuche', 'cant': 2, 'precio': 420000.0},
                {'nombre': 'Teclado Bluetooth Plegable Touchpad', 'cant': 2, 'precio': 155000.0}
            ]
        },
        {
            'fecha': datetime(2026, 9, 15, 16, 10),
            'local_id': 3,
            'vendedor_id': u_admin.id,
            'monto': 960000.0,
            'metodo': 'bold',
            'detalles': [
                {'nombre': 'Proyector Portátil Android Full HD Smart TV', 'cant': 1, 'precio': 720000.0},
                {'nombre': 'Trípode Profesional Reforzado 2.1m', 'cant': 2, 'precio': 120000.0}
            ]
        },

        # --- ADDI (Crédito) ---
        {
            'fecha': datetime(2026, 9, 8, 16, 00),
            'local_id': 1,
            'vendedor_id': v1.id,
            'monto': 1200000.0,
            'metodo': 'addi',
            'detalles': [
                {'nombre': 'Combo Tech Completo: Reloj + Diadema + Parlante', 'cant': 2, 'precio': 600000.0}
            ]
        },
        {
            'fecha': datetime(2026, 9, 12, 17, 45),
            'local_id': 2,
            'vendedor_id': v2.id,
            'monto': 1450000.0,
            'metodo': 'addi',
            'detalles': [
                {'nombre': 'Dron 4K Profesional con Cámara Dual y GPS', 'cant': 1, 'precio': 1100000.0},
                {'nombre': 'Batería Extra Dron y Hélices de Repuesto', 'cant': 1, 'precio': 350000.0}
            ]
        }
    ]

    ventas_creadas = 0
    for v_data in ventas_nuevas:
        sale = Sale(
            vendedor_id=v_data['vendedor_id'],
            local_id=v_data['local_id'],
            monto_total=Decimal(str(v_data['monto'])),
            metodo_pago=v_data['metodo'],
            fecha_venta=v_data['fecha']
        )
        db.session.add(sale)
        db.session.flush()

        # Registro de Pago
        sp = SalePayment(
            sale_id=sale.id,
            metodo_pago=v_data['metodo'],
            monto=Decimal(str(v_data['monto']))
        )
        db.session.add(sp)

        # Detalles
        for d in v_data['detalles']:
            det = SaleDetail(
                sale_id=sale.id,
                product_id=None,
                nombre_manual=d['nombre'],
                cantidad_vendida=d['cant'],
                precio_venta_final=Decimal(str(d['precio']))
            )
            db.session.add(det)

        ventas_creadas += 1

    db.session.commit()
    print(f"¡Éxito! Se registraron {ventas_creadas} nuevas ventas pos.")
