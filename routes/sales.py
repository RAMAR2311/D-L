from flask import Blueprint, request, jsonify, flash, redirect, render_template, abort, url_for
from flask_login import login_required, current_user
from models import db, Product, ProductVariant, Sale, SaleDetail, SalePayment, Expense, User, Punto, PuntoTransaction, obtener_hora_bogota
from decorators import admin_required
from decimal import Decimal
from datetime import datetime, timedelta
from sqlalchemy import or_
from sqlalchemy.orm import joinedload, selectinload

sales_bp = Blueprint('sales_bp', __name__)

@sales_bp.route('/nueva', methods=['GET', 'POST'])
@login_required
def procesar_venta():
    if request.method == 'GET':
        return redirect(url_for('sales_bp.caja_visual'))

    """
    Se espera que los datos vengan en el cuerpo de la petición (JSON)
    Ej: {'items': [{ 'product_id': 1, 'cantidad': 2, 'precio_final': 15.50}, ...], 'metodo_pago': 'transferencia'}
    """
    data = request.get_json()
    items = data.get('items', [])
    pagos_data = data.get('pagos', [])  # Nuevo: array de pagos mixtos
    metodo_pago_legacy = data.get('metodo_pago', 'efectivo')  # Retrocompatibilidad
    
    if not items:
        return jsonify({'error': 'No se enviaron productos para la venta'}), 400

    # Si no se envían pagos en el nuevo formato, crear uno único con el método legacy
    if not pagos_data:
        pagos_data = [{'metodo_pago': metodo_pago_legacy, 'monto': None}]  # monto=None se llenará con el total

    try:
        # Determinar el método de pago principal (para la columna legacy de retrocompatibilidad)
        if len(pagos_data) == 1:
            metodo_pago_principal = pagos_data[0].get('metodo_pago', 'efectivo')
        else:
            metodo_pago_principal = 'mixto'

        # Manejar Fecha de Venta para registros de fechas anteriores
        fecha_venta_str = data.get('fecha_venta')
        fecha_venta_obj = obtener_hora_bogota()
        if fecha_venta_str:
            try:
                fecha_seleccionada = datetime.strptime(fecha_venta_str, '%Y-%m-%d').date()
                if fecha_seleccionada != fecha_venta_obj.date():
                    fecha_venta_obj = datetime.combine(fecha_seleccionada, fecha_venta_obj.time())
            except ValueError:
                pass

        asesor_id_raw = data.get('asesor_id')
        asesor_id_val = None
        if asesor_id_raw:
            try:
                asesor_id_val = int(asesor_id_raw)
            except (ValueError, TypeError):
                asesor_id_val = None

        # Determinar Sede Venta según rol
        if current_user.rol != 'admin':
            local_id_venta = current_user.local_asignado or 1
        else:
            try:
                local_id_venta = int(data.get('local_id') or 1)
            except (ValueError, TypeError):
                local_id_venta = 1

        nueva_venta = Sale(
            vendedor_id=current_user.id,
            asesor_id=asesor_id_val,
            monto_total=Decimal('0.00'),
            metodo_pago=metodo_pago_principal,
            fecha_venta=fecha_venta_obj,
            local_id=local_id_venta
        )
        db.session.add(nueva_venta)
        db.session.flush()


        monto_total = Decimal('0.00')

        for item in items:
            product_id = item.get('product_id')
            variant_id = item.get('variant_id') # Posible variante
            cantidad_vendida = int(item.get('cantidad', 0))
            precio_venta_final = Decimal(str(item.get('precio_final', '0.00')))
            es_manual = item.get('es_manual', False)
            es_obsequio = item.get('es_obsequio', False)

            if cantidad_vendida <= 0:
                raise ValueError("La cantidad vendida debe ser mayor a 0.")

            if es_manual:
                # Producto manual / externo (Punto) — no descuenta stock de inventario propio
                nombre_manual = item.get('nombre_manual', 'Producto Externo')
                precio_costo_manual = Decimal(str(item.get('precio_costo', '0.00')))
                punto_id_item = item.get('punto_id')
                nombre_punto_item = item.get('nombre_punto', '').strip()

                punto_obj = None
                if punto_id_item:
                    punto_obj = Punto.query.get(int(punto_id_item))
                elif nombre_punto_item:
                    punto_obj = Punto.query.filter_by(nombre=nombre_punto_item).first()
                    if not punto_obj:
                        punto_obj = Punto(nombre=nombre_punto_item)
                        db.session.add(punto_obj)
                        db.session.flush()

                detalle = SaleDetail(
                    sale_id=nueva_venta.id,
                    product_id=None,
                    variant_id=None,
                    punto_id=punto_obj.id if punto_obj else None,
                    cantidad_vendida=cantidad_vendida,
                    precio_venta_final=precio_venta_final,
                    nombre_manual=nombre_manual,
                    precio_costo_manual=precio_costo_manual
                )
                db.session.add(detalle)
                monto_total += (precio_venta_final * cantidad_vendida)

                # Si está asociado a un Punto, registrar la deuda (Cargo) en su estado de cuenta
                if punto_obj and precio_costo_manual > 0:
                    cargo_punto = PuntoTransaction(
                        punto_id=punto_obj.id,
                        sale_id=nueva_venta.id,
                        usuario_id=current_user.id,
                        tipo_movimiento='cargo',
                        monto=(precio_costo_manual * cantidad_vendida),
                        local_id=local_id_venta,
                        descripcion=f"Venta POS D&L {local_id_venta}: {nombre_manual} ({cantidad_vendida} uds)"
                    )
                    db.session.add(cargo_punto)
                elif not punto_obj and precio_costo_manual > 0:
                    # Retrocompatibilidad si no se seleccionó punto
                    gasto_externo = Expense(
                        usuario_id=current_user.id,
                        tipo_gasto='Gasto Diario',
                        categoria='Pago Prod. Externo',
                        descripcion=f"Pago por producto manual prestado: {nombre_manual}",
                        monto=(precio_costo_manual * cantidad_vendida),
                        local_id=local_id_venta,
                        fecha_gasto=fecha_venta_obj
                    )
                    db.session.add(gasto_externo)
            else:
                # Producto del inventario propio
                producto = Product.query.with_for_update().get(product_id)
                
                if not producto:
                    raise ValueError(f"El producto con ID {product_id} no existe.")

                es_traslado = item.get('es_traslado', False)
                local_origen_id = item.get('local_origen_id')
                asesor_id_traslado = item.get('asesor_id_traslado')
                observacion_traslado = item.get('observacion_traslado', '')

                if variant_id:
                    variante = ProductVariant.query.with_for_update().get(variant_id)
                    if not variante:
                        raise ValueError(f"La variante con ID {variant_id} no existe.")
                    
                    # Manejo de Traslado previo si el item fue solicitado desde otra sede
                    if es_traslado and local_origen_id:
                        loc_origen_num = int(local_origen_id)
                        stock_origen = variante.get_stock_local(str(loc_origen_num))
                        if cantidad_vendida > stock_origen:
                            raise ValueError(f"Stock insuficiente en D&L {loc_origen_num} para trasladar '{variante.nombre_variante}' de '{producto.nombre}'. Disponible: {stock_origen}.")
                        
                        setattr(variante, f'stock_local_{loc_origen_num}', getattr(variante, f'stock_local_{loc_origen_num}') - cantidad_vendida)
                        setattr(variante, f'stock_local_{local_id_venta}', getattr(variante, f'stock_local_{local_id_venta}', 0) + cantidad_vendida)

                        from models import StockTransfer
                        nuevo_traslado = StockTransfer(
                            product_id=producto.id,
                            variant_id=variante.id,
                            local_origen_id=loc_origen_num,
                            local_destino_id=local_id_venta,
                            cantidad=cantidad_vendida,
                            usuario_id=current_user.id,
                            asesor_id=int(asesor_id_traslado) if asesor_id_traslado else asesor_id_val,
                            sale_id=nueva_venta.id,
                            es_facturado=True,
                            observacion=observacion_traslado if observacion_traslado else f"Traslado automático al facturar ticket",
                            fecha_transferencia=fecha_venta_obj
                        )
                        db.session.add(nuevo_traslado)

                    precio_limite_autorizado = variante.precio_costo if current_user.rol == 'admin' else variante.precio_minimo
                    debe_descontar = variante.descontar_inventario if (hasattr(variante, 'descontar_inventario') and variante.descontar_inventario) else producto.descontar_inventario

                    # Solo si el Toggle Switch del producto/variante está ENCENDIDO (ON) validamos y descontamos stock
                    if debe_descontar:
                        stock_disponible = variante.get_stock_local(str(local_id_venta))
                        if cantidad_vendida > stock_disponible:
                            raise ValueError(f"Stock insuficiente en Local {local_id_venta} para la variante '{variante.nombre_variante}' de '{producto.nombre}'. Solicitado: {cantidad_vendida}, Disponible: {stock_disponible}.")
                        
                        stock_anterior = variante.total_stock
                        if local_id_venta == 1:
                            variante.stock_local_1 -= cantidad_vendida
                        elif local_id_venta == 2:
                            variante.stock_local_2 -= cantidad_vendida
                        elif local_id_venta == 3:
                            variante.stock_local_3 -= cantidad_vendida

                        variante.cantidad_stock = variante.total_stock
                        producto.cantidad_stock = producto.total_stock
                        
                        from models import StockAdjustment
                        ajuste = StockAdjustment(
                            product_id=producto.id,
                            admin_id=current_user.id,
                            tipo_movimiento=f"Venta Local {local_id_venta} (Subcat: {variante.nombre_variante})",
                            stock_anterior=stock_anterior,
                            stock_nuevo=variante.total_stock
                        )
                        db.session.add(ajuste)
                else:
                    # Manejo de Traslado previo si el item fue solicitado desde otra sede
                    if es_traslado and local_origen_id:
                        loc_origen_num = int(local_origen_id)
                        stock_origen = producto.get_stock_local(str(loc_origen_num))
                        if cantidad_vendida > stock_origen:
                            raise ValueError(f"Stock insuficiente en D&L {loc_origen_num} para trasladar '{producto.nombre}'. Disponible: {stock_origen}.")
                        
                        setattr(producto, f'stock_local_{loc_origen_num}', getattr(producto, f'stock_local_{loc_origen_num}') - cantidad_vendida)
                        setattr(producto, f'stock_local_{local_id_venta}', getattr(producto, f'stock_local_{local_id_venta}', 0) + cantidad_vendida)

                        from models import StockTransfer
                        nuevo_traslado = StockTransfer(
                            product_id=producto.id,
                            variant_id=None,
                            local_origen_id=loc_origen_num,
                            local_destino_id=local_id_venta,
                            cantidad=cantidad_vendida,
                            usuario_id=current_user.id,
                            asesor_id=int(asesor_id_traslado) if asesor_id_traslado else asesor_id_val,
                            sale_id=nueva_venta.id,
                            es_facturado=True,
                            observacion=observacion_traslado if observacion_traslado else f"Traslado automático al facturar ticket",
                            fecha_transferencia=fecha_venta_obj
                        )
                        db.session.add(nuevo_traslado)

                    precio_limite_autorizado = producto.precio_costo if current_user.rol == 'admin' else producto.precio_minimo
                    debe_descontar = producto.descontar_inventario

                    # Solo si el Toggle Switch del producto está ENCENDIDO (ON) validamos y descontamos stock
                    if debe_descontar:
                        stock_disponible = producto.get_stock_local(str(local_id_venta))
                        if cantidad_vendida > stock_disponible:
                            raise ValueError(f"Stock insuficiente en Local {local_id_venta} para el producto '{producto.nombre}'. Solicitado: {cantidad_vendida}, Disponible: {stock_disponible}.")
                        
                        stock_anterior = producto.total_stock
                        if local_id_venta == 1:
                            producto.stock_local_1 -= cantidad_vendida
                        elif local_id_venta == 2:
                            producto.stock_local_2 -= cantidad_vendida
                        elif local_id_venta == 3:
                            producto.stock_local_3 -= cantidad_vendida

                        producto.cantidad_stock = producto.total_stock
                        
                        from models import StockAdjustment
                        ajuste = StockAdjustment(
                            product_id=producto.id,
                            admin_id=current_user.id,
                            tipo_movimiento=f"Venta Local {local_id_venta}",
                            stock_anterior=stock_anterior,
                            stock_nuevo=producto.total_stock
                        )
                        db.session.add(ajuste)

                if not es_obsequio and precio_venta_final < precio_limite_autorizado:
                    raise ValueError(f"No autorizado: El precio ({precio_venta_final}) del producto '{producto.nombre}' está por debajo del límite permitido ({precio_limite_autorizado}).")

                detalle = SaleDetail(
                    sale_id=nueva_venta.id,
                    product_id=producto.id,
                    variant_id=variant_id,
                    cantidad_vendida=cantidad_vendida,
                    precio_venta_final=precio_venta_final
                )
                db.session.add(detalle)
                db.session.flush() # Importante para tener el id de la venta si se quisiera, pero ya lo tenemos en nueva_venta.id
                
                # Para añadir el ID de la venta al tipo de movimiento ahora que la venta tiene ID asignado:
                if 'ajuste' in locals() and ajuste:
                    ajuste.tipo_movimiento = f"{ajuste.tipo_movimiento} #{nueva_venta.id}"
                
                monto_total += (precio_venta_final * cantidad_vendida)

        nueva_venta.monto_total = monto_total

        # Registrar los pagos mixtos en la tabla sale_payments
        total_pagos = Decimal('0.00')
        for pago_info in pagos_data:
            metodo = pago_info.get('metodo_pago', 'efectivo')
            monto_pago = pago_info.get('monto')
            
            if monto_pago is None:
                # Si solo hay un pago sin monto explícito, asignar el total completo
                monto_pago = monto_total
            else:
                monto_pago = Decimal(str(monto_pago))
            
            if monto_pago <= 0:
                raise ValueError(f"El monto del pago por '{metodo}' debe ser mayor a 0.")
            
            pago = SalePayment(
                sale_id=nueva_venta.id,
                metodo_pago=metodo,
                monto=monto_pago
            )
            db.session.add(pago)
            total_pagos += monto_pago

        # Validar que la suma de pagos cubra el total de la venta
        if total_pagos != monto_total:
            raise ValueError(f"La suma de los pagos (${total_pagos}) no coincide con el total de la venta (${monto_total}). Diferencia: ${monto_total - total_pagos}.")


        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Venta registrada e inventario descontado con éxito.',
            'sale_id': nueva_venta.id,
            'total': str(monto_total)
        }), 201

    except ValueError as val_err:
        db.session.rollback()
        return jsonify({'error': str(val_err)}), 400
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Ocurrió un error interno al procesar la venta.'}), 500

@sales_bp.route('/api/search_products')
@login_required
def api_search_products():
    query = request.args.get('q', '').strip()
    
    if len(query) < 2:
        return jsonify([])

    if current_user.rol == 'admin':
        local_code = str(request.args.get('local_id') or '1')
    else:
        local_code = str(current_user.local_asignado or '1')
    
    productos = Product.query.filter_by(tipo_inventario='tienda').filter(
        or_(
            Product.sku.ilike(f'%{query}%'),
            Product.nombre.ilike(f'%{query}%')
        )
    ).limit(15).all()
    
    results = []
    for p in productos:
        variantes_data = []
        if p.variantes:
            for v in p.variantes:
                variantes_data.append({
                    'id': v.id,
                    'nombre': v.nombre_variante,
                    'stock': v.get_stock_local(local_code),
                    'descontar_inventario': v.descontar_inventario if (hasattr(v, 'descontar_inventario') and v.descontar_inventario) else p.descontar_inventario,
                    'precio_costo': float(v.precio_costo) if v.precio_costo else None,
                    'precio_minimo': float(v.precio_minimo) if v.precio_minimo else None,
                    'precio_sugerido': float(v.precio_sugerido) if v.precio_sugerido else None
                })
        
        results.append({
            'id': p.id,
            'nombre': p.nombre,
            'sku': p.sku,
            'tipo_inventario': p.tipo_inventario,
            'cantidad_stock': p.get_stock_local(local_code),
            'descontar_inventario': p.descontar_inventario,
            'precio_minimo': float(p.precio_minimo),
            'precio_sugerido': float(p.precio_sugerido),
            'precio_costo': float(p.precio_costo),
            'variantes': variantes_data
        })
    
    return jsonify(results)

# Endpoint API asíncrono para el escáner del Punto de Venta
@sales_bp.route('/api/producto/<path:sku>', methods=['GET'])
@login_required
def api_buscar_producto(sku):
    producto = Product.query.filter(Product.sku == sku, Product.tipo_inventario == 'tienda').first()
    auto_select_variant = None
    
    if not producto:
        return jsonify({'error': 'Código SKU no encontrado en el sistema'}), 404
        
    return jsonify({
        'id': producto.id,
        'nombre': producto.nombre,
        'sku': producto.sku,
        'tipo_inventario': producto.tipo_inventario,
        'cantidad_stock': producto.total_stock,
        'precio_minimo': float(producto.precio_minimo),
        'precio_limite': float(producto.precio_costo) if current_user.rol == 'admin' else float(producto.precio_minimo),
        'precio_sugerido': float(producto.precio_sugerido),
        'variantes': [{"id": v.id, "nombre": v.nombre_variante, "stock": v.cantidad_stock, "precio_minimo": float(v.precio_minimo or producto.precio_minimo), "precio_limite": float(v.precio_costo or producto.precio_costo) if current_user.rol == 'admin' else float(v.precio_minimo or producto.precio_minimo), "precio_sugerido": float(v.precio_sugerido or producto.precio_sugerido)} for v in producto.variantes],
        'auto_select_variant': auto_select_variant
    })

# Ruta para la Impresión del formato Térmico (Ticket)
@sales_bp.route('/recibo/<int:sale_id>', methods=['GET'])
@login_required # Proteger confidencialidad del cajero
def imprimir_ticket(sale_id):
    # Regla: Retorna 404 si alguien ingresa un ID falso
    venta = Sale.query.get_or_404(sale_id)
    return render_template('sales/ticket.html', venta=venta)

# Endpoint Historial de Ventas (Administradores)
@sales_bp.route('/historial', methods=['GET'])
@login_required
@admin_required
def historial():
    # Calcular el valor exacto de 'HOY' en Bogotá
    hoy_bogota = obtener_hora_bogota().strftime('%Y-%m-%d')
    
    # Si existen los args, los usa, de lo contrario colapsa a HOY por defecto
    fecha_inicio = request.args.get('fecha_inicio', hoy_bogota)
    fecha_fin = request.args.get('fecha_fin', hoy_bogota)
    active_local = request.args.get('local', 'central').lower()
    if active_local not in ['central', '1', '2', '3']:
        active_local = 'central'
    
    # Optimización: eager loading (evita N+1 con joinedload y selectinload)
    query = Sale.query.options(
        joinedload(Sale.vendedor),
        selectinload(Sale.detalles).selectinload(SaleDetail.producto),
        selectinload(Sale.detalles).selectinload(SaleDetail.variante),
        selectinload(Sale.pagos)
    )
    if active_local != 'central':
        local_num = int(active_local)
        query = query.filter(Sale.local_id == local_num)
    
    # Motor de búsqueda por Rango Restricto
    if fecha_inicio:
        inicio_dt = datetime.strptime(fecha_inicio, '%Y-%m-%d')
        query = query.filter(Sale.fecha_venta >= inicio_dt)
        
    if fecha_fin:
        fin_dt = datetime.strptime(fecha_fin, '%Y-%m-%d')
        # Sumar 1 día matemáticamente para incluir los registros hasta las 23:59:59 del último día
        query = query.filter(Sale.fecha_venta < fin_dt + timedelta(days=1))
        
    ventas = query.order_by(Sale.fecha_venta.desc()).all()
    
    # Auditar y cruzar sumatorios de métricas de pago
    # Sistema híbrido: usa SalePayment si existe, caso contrario cae al metodo_pago legacy
    total_efectivo = Decimal('0')
    total_nequi = Decimal('0')
    total_bancolombia = Decimal('0')
    total_daviplata = Decimal('0')
    total_bold = Decimal('0')
    total_addi = Decimal('0')
    total_transferencia_legacy = Decimal('0')
    total_mixto = 0  # Contador de ventas con pago mixto

    for v in ventas:
        if v.pagos:  # Pagos nuevos con tabla sale_payments
            for pago in v.pagos:
                if pago.metodo_pago == 'efectivo':
                    total_efectivo += pago.monto
                elif pago.metodo_pago == 'nequi':
                    total_nequi += pago.monto
                elif pago.metodo_pago == 'bancolombia':
                    total_bancolombia += pago.monto
                elif pago.metodo_pago == 'daviplata':
                    total_daviplata += pago.monto
                elif pago.metodo_pago == 'bold':
                    total_bold += pago.monto
                elif pago.metodo_pago == 'addi':
                    total_addi += pago.monto
                elif pago.metodo_pago == 'transferencia':
                    total_transferencia_legacy += pago.monto
            if len(v.pagos) > 1:
                total_mixto += 1
        else:  # Retrocompatibilidad con ventas antiguas sin SalePayment
            if v.metodo_pago == 'efectivo':
                total_efectivo += v.monto_total
            elif v.metodo_pago == 'nequi':
                total_nequi += v.monto_total
            elif v.metodo_pago == 'bancolombia':
                total_bancolombia += v.monto_total
            elif v.metodo_pago == 'daviplata':
                total_daviplata += v.monto_total
            elif v.metodo_pago == 'bold':
                total_bold += v.monto_total
            elif v.metodo_pago == 'addi':
                total_addi += v.monto_total
            elif v.metodo_pago == 'transferencia':
                total_transferencia_legacy += v.monto_total

    # Envío al Engine de HTML
    return render_template('sales/historial.html', 
                           ventas=ventas, 
                           total_efectivo=total_efectivo,
                           total_nequi=total_nequi,
                           total_bancolombia=total_bancolombia,
                           total_daviplata=total_daviplata,
                           total_bold=total_bold,
                           total_addi=total_addi,
                           total_transferencia_legacy=total_transferencia_legacy,
                           total_mixto=total_mixto,
                           fecha_inicio=fecha_inicio,
                           fecha_fin=fecha_fin,
                           active_local=active_local)


# Endpoint Visor de Ventas del Día para Cajeros (Solo lectura, se resetea cada día)
@sales_bp.route('/ventas_hoy', methods=['GET'])
@login_required
def ventas_hoy():
    # Obtener la fecha de hoy
    hoy_bogota = obtener_hora_bogota().date()
    # Para la consulta requerimos abarcar desde las 00:00:00 hasta las 23:59:59
    inicio_dt = datetime.combine(hoy_bogota, datetime.min.time())
    fin_dt = datetime.combine(hoy_bogota, datetime.max.time())
    
    # Filtrar ventas de este día para el local asignado al usuario
    local_id_cajero = current_user.local_asignado or 1
    
    ventas = Sale.query.options(joinedload(Sale.vendedor)).filter(
        Sale.fecha_venta >= inicio_dt,
        Sale.fecha_venta <= fin_dt,
        Sale.local_id == local_id_cajero
    ).order_by(Sale.fecha_venta.desc()).all()
    
    # Acumuladores de las ventas de hoy
    total_efectivo = Decimal('0')
    total_transferencias = Decimal('0')
    total_mixto = 0
    
    for v in ventas:
        if v.pagos:
            for pago in v.pagos:
                if pago.metodo_pago == 'efectivo':
                    total_efectivo += pago.monto
                else: 
                    total_transferencias += pago.monto
            if len(v.pagos) > 1:
                total_mixto += 1
        else:
            if v.metodo_pago == 'efectivo':
                total_efectivo += v.monto_total
            else:
                total_transferencias += v.monto_total
                
    return render_template('sales/ventas_hoy.html',
                           ventas=ventas,
                           total_efectivo=total_efectivo,
                           total_transferencias=total_transferencias,
                           total_mixto=total_mixto,
                           hoy=hoy_bogota.strftime('%Y-%m-%d'))


# Endpoint para Anular/Eliminar Venta Histórica
@sales_bp.route('/eliminar/<int:sale_id>', methods=['POST'])
@login_required
@admin_required
def eliminar_venta(sale_id):
    venta = Sale.query.get_or_404(sale_id)
    
    try:
        # Revertir Stock
        from models import StockAdjustment
        for detalle in venta.detalles:
            if detalle.variant_id:
                variante = ProductVariant.query.with_for_update().get(detalle.variant_id)
                if variante:
                    stock_anterior = variante.cantidad_stock
                    variante.cantidad_stock += detalle.cantidad_vendida
                    
                    ajuste = StockAdjustment(
                        product_id=detalle.product_id,
                        admin_id=current_user.id,
                        tipo_movimiento=f"Anulación Venta #{venta.id} (Subcat: {variante.nombre_variante})",
                        stock_anterior=stock_anterior,
                        stock_nuevo=variante.cantidad_stock
                    )
                    db.session.add(ajuste)
                    
                producto = Product.query.with_for_update().get(detalle.product_id)
                if producto:
                    producto.cantidad_stock += detalle.cantidad_vendida
            elif detalle.product_id:
                producto = Product.query.with_for_update().get(detalle.product_id)
                if producto:
                    stock_anterior = producto.cantidad_stock
                    producto.cantidad_stock += detalle.cantidad_vendida
                    
                    ajuste = StockAdjustment(
                        product_id=producto.id,
                        admin_id=current_user.id,
                        tipo_movimiento=f"Anulación Venta #{venta.id}",
                        stock_anterior=stock_anterior,
                        stock_nuevo=producto.cantidad_stock
                    )
                    db.session.add(ajuste)
                    
        # Eliminar Venta y Detalles (Cascada)
        db.session.delete(venta)
        db.session.commit()
        flash('Venta anulada y stock devuelto exitosamente.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash('Ocurrió un error al anular la venta.', 'danger')
        
    return redirect(url_for('sales_bp.historial'))

# Endpoint Catálogo Estricto de solo vista para Operarios (Vista Global Multisede)
@sales_bp.route('/catalogo', methods=['GET'])
@login_required 
def catalogo():
    query_str = request.args.get('q', '').strip()
    
    if query_str:
        search_term = f"%{query_str}%"
        productos = Product.query.filter(Product.tipo_inventario == 'tienda').filter(
            or_(
                Product.sku.ilike(search_term), 
                Product.nombre.ilike(search_term)
            )
        ).order_by(Product.nombre.asc()).all()
    else:
        productos = Product.query.filter(Product.tipo_inventario == 'tienda').order_by(Product.nombre.asc()).all()
        
    return render_template('sales/catalogo.html', productos=productos, q=query_str)

@sales_bp.route('/caja_visual', methods=['GET'])
@login_required
def caja_visual():
    from models import Asesor, obtener_hora_bogota
    hoy_bogota = obtener_hora_bogota()
    
    is_admin = (current_user.rol == 'admin')
    if is_admin:
        active_local = str(request.args.get('local', '1')).strip()
        if active_local not in ['1', '2', '3']:
            active_local = '1'
    else:
        active_local = str(getattr(current_user, 'local_asignado', 1) or '1')

    asesores = Asesor.query.filter_by(estado='Activo').order_by(Asesor.nombre.asc()).all()

    productos = Product.query.filter(Product.tipo_inventario == 'tienda').order_by(Product.nombre.asc()).all()
    puntos = Punto.query.order_by(Punto.nombre.asc()).all()

    return render_template(
        'sales/caja_visual.html', 
        productos=productos, 
        hoy=hoy_bogota.strftime('%Y-%m-%d'),
        active_local=active_local,
        is_admin=is_admin,
        asesores=asesores,
        puntos=puntos
    )

