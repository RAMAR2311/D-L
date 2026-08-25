import os
import random
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash
from app import create_app
from models import (
    db, User, Product, ProductVariant, StockAdjustment, StockTransfer,
    Sale, SaleDetail, SalePayment, Punto, PuntoTransaction, ArqueoCaja,
    Maneo, Expense, Cliente, FacturaBodega, FacturaBodegaDetalle, AbonoBodega,
    LocalConfig, Provider, ProviderInvoice, ProviderPayment, Asesor
)

def seed_all():
    app = create_app()
    with app.app_context():
        print("[INICIO] Generando datos de ejemplo para TODOS los modulos...")
        db.create_all()

        # ----------------------------------------------------
        # 1. CONFIGURACIÓN DE LOCALES
        # ----------------------------------------------------
        for loc_id in [1, 2, 3]:
            cfg = LocalConfig.query.filter_by(local_id=loc_id).first()
            if not cfg:
                db.session.add(LocalConfig(local_id=loc_id, descontar_inventario=True))
        db.session.commit()
        print("[1/12] Configuraciones de Locales listas.")

        # ----------------------------------------------------
        # 2. USUARIOS Y ROLES
        # ----------------------------------------------------
        users_data = [
            {"nombre": "Administrador Principal", "email": "admin@dl.com", "rol": "admin", "local": 1},
            {"nombre": "Vendedor Local Centro", "email": "vendedor1@dl.com", "rol": "vendedor", "local": 1},
            {"nombre": "Vendedor Local Norte", "email": "vendedor2@dl.com", "rol": "vendedor", "local": 2},
            {"nombre": "Encargado Bodega Central", "email": "bodega@dl.com", "rol": "bodega", "local": 1},
        ]
        
        users_dict = {}
        for ud in users_data:
            u = User.query.filter_by(email=ud["email"]).first()
            if not u:
                u = User(
                    nombre=ud["nombre"],
                    email=ud["email"],
                    password_hash=generate_password_hash("Admin123"),
                    rol=ud["rol"],
                    local_asignado=ud["local"],
                    telefono="3001234567"
                )
                db.session.add(u)
                db.session.flush()
            users_dict[ud["email"]] = u
        db.session.commit()
        print("[2/12] Usuarios y Roles listos (admin@dl.com, vendedor1@dl.com, bodega@dl.com).")

        admin_user = users_dict["admin@dl.com"]
        vendedor_user = users_dict["vendedor1@dl.com"]
        bodega_user = users_dict["bodega@dl.com"]

        # ----------------------------------------------------
        # 3. ASESORES COMERCIALES
        # ----------------------------------------------------
        asesores_data = [
            {"nombre": "Carlos Mendoza", "local_id": 1},
            {"nombre": "Laura Gomez", "local_id": 2},
            {"nombre": "Andres Rocha", "local_id": 1},
        ]
        asesores_list = []
        for ad in asesores_data:
            a = Asesor.query.filter_by(nombre=ad["nombre"]).first()
            if not a:
                a = Asesor(nombre=ad["nombre"], local_id=ad["local_id"], estado="Activo")
                db.session.add(a)
                db.session.flush()
            asesores_list.append(a)
        db.session.commit()
        print("[3/12] Asesores Comerciales listos.")

        # ----------------------------------------------------
        # 4. PRODUCTOS Y VARIANTES (INVENTARIO)
        # ----------------------------------------------------
        products_seed = [
            {
                "sku": "AUD-BT-001",
                "nombre": "Auriculares Bluetooth Pro Max",
                "tipo_inventario": "tienda",
                "precio_costo": 25000,
                "precio_minimo": 45000,
                "precio_sugerido": 60000,
                "stock1": 20, "stock2": 15, "stock3": 10,
                "variantes": [
                    {"nombre": "Negro Mate", "s1": 10, "s2": 8, "s3": 5, "costo": 25000, "min": 45000, "sug": 60000},
                    {"nombre": "Blanco Perla", "s1": 10, "s2": 7, "s3": 5, "costo": 25000, "min": 45000, "sug": 60000},
                ]
            },
            {
                "sku": "CARG-20W-002",
                "nombre": "Cargador Carga Rapida 20W USB-C",
                "tipo_inventario": "tienda",
                "precio_costo": 12000,
                "precio_minimo": 25000,
                "precio_sugerido": 35000,
                "stock1": 30, "stock2": 25, "stock3": 15,
                "variantes": []
            },
            {
                "sku": "CASE-IPH-003",
                "nombre": "Funda Silicona Magnetica iPhone",
                "tipo_inventario": "tienda",
                "precio_costo": 8000,
                "precio_minimo": 18000,
                "precio_sugerido": 25000,
                "stock1": 50, "stock2": 40, "stock3": 30,
                "variantes": [
                    {"nombre": "iPhone 13 - Transparente", "s1": 20, "s2": 15, "s3": 10, "costo": 8000, "min": 18000, "sug": 25000},
                    {"nombre": "iPhone 14 - Negro", "s1": 15, "s2": 15, "s3": 10, "costo": 8000, "min": 18000, "sug": 25000},
                    {"nombre": "iPhone 15 - Azul Noche", "s1": 15, "s2": 10, "s3": 10, "costo": 8000, "min": 18000, "sug": 25000},
                ]
            },
            {
                "sku": "PAN-SAM-004",
                "nombre": "Pantalla Modulo AMOLED Samsung S21",
                "tipo_inventario": "bodega",
                "precio_costo": 180000,
                "precio_minimo": 260000,
                "precio_sugerido": 320000,
                "stock1": 10, "stock2": 5, "stock3": 0,
                "variantes": []
            }
        ]

        products_list = []
        for ps in products_seed:
            p = Product.query.filter_by(sku=ps["sku"]).first()
            if not p:
                p = Product(
                    sku=ps["sku"],
                    nombre=ps["nombre"],
                    tipo_inventario=ps["tipo_inventario"],
                    precio_costo=ps["precio_costo"],
                    precio_minimo=ps["precio_minimo"],
                    precio_sugerido=ps["precio_sugerido"],
                    stock_local_1=ps["stock1"],
                    stock_local_2=ps["stock2"],
                    stock_local_3=ps["stock3"],
                    observacion="Producto de prueba generado para demostracion."
                )
                db.session.add(p)
                db.session.flush()

                # Registrar ajuste inicial
                db.session.add(StockAdjustment(
                    product_id=p.id,
                    admin_id=admin_user.id,
                    tipo_movimiento="Creacion Inicial Demo",
                    stock_anterior=0,
                    stock_nuevo=ps["stock1"] + ps["stock2"] + ps["stock3"]
                ))

                # Variantes
                for var_data in ps["variantes"]:
                    v = ProductVariant(
                        product_id=p.id,
                        nombre_variante=var_data["nombre"],
                        stock_local_1=var_data["s1"],
                        stock_local_2=var_data["s2"],
                        stock_local_3=var_data["s3"],
                        precio_costo=var_data["costo"],
                        precio_minimo=var_data["min"],
                        precio_sugerido=var_data["sug"]
                    )
                    db.session.add(v)
            products_list.append(p)
        db.session.commit()
        print("[4/12] Productos, Variantes y Ajustes de Stock listos.")

        # ----------------------------------------------------
        # 5. PROVEEDORES (FACTURAS Y PAGOS A PROVEEDOR)
        # ----------------------------------------------------
        prov = Provider.query.filter_by(nombre="Tech Import Colombia S.A.S.").first()
        if not prov:
            prov = Provider(
                nombre="Tech Import Colombia S.A.S.",
                empresa="Tech Import Latam",
                telefono="6015551234"
            )
            db.session.add(prov)
            db.session.flush()

            inv1 = ProviderInvoice(
                provider_id=prov.id,
                monto_total=1200000,
                numero_factura="FAC-PROV-9081",
                descripcion="Compra lote auriculares y cargadores"
            )
            db.session.add(inv1)
            db.session.flush()

            pay1 = ProviderPayment(
                provider_id=prov.id,
                monto_abonado=500000,
                observacion="Primer abono parcial transferencia Bancolombia"
            )
            db.session.add(pay1)
        db.session.commit()
        print("[5/12] Modulo Proveedores listo.")

        # ----------------------------------------------------
        # 6. CLIENTES Y FACTURACIÓN BODEGA
        # ----------------------------------------------------
        cli = Cliente.query.filter_by(documento_o_nit="901234567-1").first()
        if not cli:
            cli = Cliente(
                nombre_o_razon_social="Distribuidora Celular del Sur S.A.S.",
                documento_o_nit="901234567-1",
                telefono="3158889900",
                email="compras@delsur.com",
                direccion="Calle 13 # 20-45, Bogota",
                creado_por_id=bodega_user.id
            )
            db.session.add(cli)
            db.session.flush()

            fb = FacturaBodega(
                cliente_id=cli.id,
                usuario_id=bodega_user.id,
                numero_factura="BOD-2026-001",
                monto_total=640000,
                modalidad="credito",
                estado="Parcial"
            )
            db.session.add(fb)
            db.session.flush()

            det_fb = FacturaBodegaDetalle(
                factura_id=fb.id,
                producto_id=products_list[3].id, # Módulo Samsung
                cantidad=2,
                precio_venta=320000
            )
            db.session.add(det_fb)

            abono_b = AbonoBodega(
                cliente_id=cli.id,
                factura_id=fb.id,
                usuario_id=bodega_user.id,
                monto=200000,
                metodo_pago="nequi",
                observacion="Abono a credito inicial por Nequi"
            )
            db.session.add(abono_b)
        db.session.commit()
        print("[6/12] Modulo Clientes y Facturacion Bodega listo.")

        # ----------------------------------------------------
        # 7. PUNTOS Y TRANSACCIONES
        # ----------------------------------------------------
        punto1 = Punto.query.filter_by(nombre="Punto San Victorino #4").first()
        if not punto1:
            punto1 = Punto(
                nombre="Punto San Victorino #4",
                telefono="3124445566",
                direccion="CC San Victorino Local 104",
                observaciones="Punto aliado para prestamos y transferencias de mercancia"
            )
            db.session.add(punto1)
            db.session.flush()

            db.session.add(PuntoTransaction(
                punto_id=punto1.id,
                usuario_id=vendedor_user.id,
                tipo_movimiento="cargo",
                monto=150000,
                metodo_pago="efectivo",
                descripcion="Cargo por mercancia despachada en punto aliado",
                local_id=1
            ))
            db.session.add(PuntoTransaction(
                punto_id=punto1.id,
                usuario_id=vendedor_user.id,
                tipo_movimiento="abono",
                monto=50000,
                metodo_pago="efectivo",
                descripcion="Abono parcial en caja",
                local_id=1
            ))
        db.session.commit()
        print("[7/12] Modulo Puntos y Cuentas por Cobrar listo.")

        # ----------------------------------------------------
        # 8. TRASLADOS DE INVENTARIO
        # ----------------------------------------------------
        if StockTransfer.query.count() == 0:
            st = StockTransfer(
                product_id=products_list[1].id, # Cargador 20W
                local_origen_id=1,
                local_destino_id=2,
                cantidad=5,
                usuario_id=vendedor_user.id,
                asesor_id=asesores_list[0].id,
                es_facturado=False,
                observacion="Traslado por escasez en Local Norte"
            )
            db.session.add(st)
        db.session.commit()
        print("[8/12] Modulo Traslados de Inventario listo.")

        # ----------------------------------------------------
        # 9. MANEOS (PRÉSTAMOS ENTRE LOCALES VECINOS)
        # ----------------------------------------------------
        if Maneo.query.count() == 0:
            m = Maneo(
                product_id=products_list[0].id,
                local_vecino="Local Celular San Andresito 102",
                cantidad=2,
                valor_unidad=25000,
                estado="PENDIENTE",
                fecha_prestamo=datetime.now()
            )
            db.session.add(m)
        db.session.commit()
        print("[9/12] Modulo Maneos (Prestamos entre vecinos) listo.")

        # ----------------------------------------------------
        # 10. GASTOS
        # ----------------------------------------------------
        if Expense.query.count() == 0:
            db.session.add(Expense(
                usuario_id=vendedor_user.id,
                tipo_gasto="Gasto Diario",
                categoria="Transporte",
                descripcion="Domicilio entrega rapida cargadores",
                monto=15000,
                metodo_pago="efectivo",
                local_id=1
            ))
            db.session.add(Expense(
                usuario_id=admin_user.id,
                tipo_gasto="Costo Indirecto",
                categoria="Servicios",
                descripcion="Pago mensualidad internet Local 1",
                monto=85000,
                metodo_pago="bancolombia",
                local_id=1
            ))
        db.session.commit()
        print("[10/12] Modulo Gastos listo.")

        # ----------------------------------------------------
        # 11. VENTAS Y PAGOS MIXTOS
        # ----------------------------------------------------
        if Sale.query.count() == 0:
            # Venta 1: Pago Mixto (Efectivo + Nequi)
            s1 = Sale(
                vendedor_id=vendedor_user.id,
                asesor_id=asesores_list[0].id,
                local_id=1,
                monto_total=95000,
                metodo_pago="mixto"
            )
            db.session.add(s1)
            db.session.flush()

            db.session.add(SaleDetail(
                sale_id=s1.id,
                product_id=products_list[0].id, # Auriculares
                cantidad_vendida=1,
                precio_venta_final=60000
            ))
            db.session.add(SaleDetail(
                sale_id=s1.id,
                product_id=products_list[1].id, # Cargador
                cantidad_vendida=1,
                precio_venta_final=35000
            ))

            db.session.add(SalePayment(sale_id=s1.id, metodo_pago="efectivo", monto=50000))
            db.session.add(SalePayment(sale_id=s1.id, metodo_pago="nequi", monto=45000))

        db.session.commit()
        print("[11/12] Modulo Ventas y Pagos Mixtos listo.")

        # ----------------------------------------------------
        # 12. ARQUEO DE CAJA
        # ----------------------------------------------------
        if ArqueoCaja.query.count() == 0:
            db.session.add(ArqueoCaja(
                vendedor_id=vendedor_user.id,
                fecha_arqueo=datetime.now().date(),
                base_inicial=100000,
                gastos_del_dia=15000,
                observaciones_gastos="Gasto domicilio cargadores",
                total_efectivo_sistema=50000,
                total_transferencia_sistema=45000,
                total_unidades_ch=0,
                local_id=1
            ))
        db.session.commit()
        print("[12/12] Modulo Arqueo de Caja listo.")

        print("[EXITO] Se crearon ejemplos en TODOS los modulos de la aplicacion!")

if __name__ == "__main__":
    seed_all()
