from flask import Blueprint, render_template, abort, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, Product, ProductVariant, Sale, User, Maneo, SaleDetail, SalePayment, StockAdjustment, Expense, ArqueoCaja, obtener_hora_bogota
from sqlalchemy.sql import func
from sqlalchemy import or_
from werkzeug.security import generate_password_hash
from decorators import admin_required
from decimal import Decimal

admin_bp = Blueprint('admin_bp', __name__)

@admin_bp.route('/vendedores', methods=['GET', 'POST'])
@login_required
@admin_required
def vendedores():
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        email = request.form.get('email')
        telefono = request.form.get('telefono')
        password = request.form.get('password')
        rol = request.form.get('rol', 'vendedor')
        try:
            local_asignado = int(request.form.get('local_asignado') or 1)
        except (ValueError, TypeError):
            local_asignado = 1
        
        # Se previene registrar vendedores con un mismo email para preservar la unicidad de las credenciales de acceso
        if User.query.filter_by(email=email).first():
            flash('Acción Denegada: Ese correo ya le pertenece a otro usuario.', 'danger')
        else:
            try:
                # Se aplica un hash a la contraseña para evitar guardar texto plano, previniendo exposición en caso de brechas
                nuevo_usuario = User(
                    nombre=nombre.strip(),
                    email=email.strip(),
                    telefono=telefono.strip() if telefono else None,
                    password_hash=generate_password_hash(password),
                    rol=rol,
                    local_asignado=local_asignado
                )
                db.session.add(nuevo_usuario)
                db.session.commit()
                flash(f"¡Usuario '{nombre}' registrado con rol '{rol}' asignado a Local {local_asignado} exitosamente!", "success")
            except Exception as e:
                db.session.rollback()
                flash('Ocurrió un error en la base de datos al intentar registrar al usuario.', 'danger')
            
        return redirect(url_for('admin_bp.vendedores'))
        
    # Se pasa la lista para poblar la tabla HTML de gestión de personal
    lista_vendedores = User.query.filter(User.rol != 'eliminado').order_by(User.nombre).all()
    return render_template('admin/vendedores.html', vendedores=lista_vendedores)

@admin_bp.route('/vendedores/<int:id>/editar', methods=['POST'])
@login_required
@admin_required
def editar_vendedor(id):
    usuario = User.query.get_or_404(id)
    if usuario.rol == 'admin':
        flash("No se puede editar al administrador principal desde aquí.", "danger")
        return redirect(url_for('admin_bp.vendedores'))

    nombre = request.form.get('nombre')
    email = request.form.get('email')
    telefono = request.form.get('telefono')
    password = request.form.get('password')
    rol = request.form.get('rol', 'vendedor')
    try:
        local_asignado = int(request.form.get('local_asignado') or 1)
    except (ValueError, TypeError):
        local_asignado = 1

    try:
        usuario.nombre = nombre.strip() if nombre else usuario.nombre
        usuario.email = email.strip() if email else usuario.email
        usuario.telefono = telefono.strip() if telefono else None
        usuario.rol = rol
        usuario.local_asignado = local_asignado
        if password and password.strip():
            usuario.password_hash = generate_password_hash(password.strip())
            
        db.session.commit()
        flash(f"¡Usuario '{usuario.nombre}' actualizado correctamente (Asignado a Local {local_asignado})!", "success")
    except Exception as e:
        db.session.rollback()
        flash("Ocurrió un error al actualizar los datos del usuario.", "danger")

    return redirect(url_for('admin_bp.vendedores'))

@admin_bp.route('/vendedores/<int:id>/eliminar', methods=['POST'])
@login_required
@admin_required
def eliminar_vendedor(id):
    usuario = User.query.get_or_404(id)
    if usuario.rol == 'admin':
        flash("No puedes eliminar al administrador.", "danger")
        return redirect(url_for('admin_bp.vendedores'))
        
    try:
        # En lugar de hacer un delete() duro que rompe las llaves foráneas (ventas, facturas), hacemos un soft delete
        usuario.rol = 'eliminado'
        usuario.email = f"eliminado_{usuario.id}_{usuario.email}"
        db.session.commit()
        flash(f"¡Usuario '{usuario.nombre}' eliminado exitosamente!", "success")
    except Exception as e:
        db.session.rollback()
        flash("Ocurrió un error al intentar eliminar el usuario.", "danger")
        
    return redirect(url_for('admin_bp.vendedores'))

@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    active_local = request.args.get('local', 'central').lower()
    if active_local not in ['central', '1', '2', '3']:
        active_local = 'central'

    hoy = obtener_hora_bogota()
    if hoy.day <= 15:
        inicio_quincena = hoy.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        inicio_quincena = hoy.replace(day=16, hour=0, minute=0, second=0, microsecond=0)

    # 1. Métrica Caja POS (Ventas por Local o General)
    query_sales = Sale.query.filter(Sale.fecha_venta >= inicio_quincena)
    if active_local != 'central':
        local_num = int(active_local)
        query_sales = query_sales.filter(Sale.local_id == local_num)
    
    ventas_list = query_sales.all()
    total_ventas = sum(v.monto_total for v in ventas_list) if ventas_list else 0.0
    conteo_ventas = len(ventas_list)

    # 2. Métrica Gastos por Local o General
    query_expenses = Expense.query.filter(Expense.fecha_gasto >= inicio_quincena)
    if active_local != 'central':
        local_num = int(active_local)
        query_expenses = query_expenses.filter(or_(Expense.local_id == local_num, User.local_asignado == local_num)).outerjoin(User, Expense.usuario_id == User.id)

    gastos_list = query_expenses.all()
    total_gastos = sum(g.monto for g in gastos_list) if gastos_list else 0.0
    conteo_gastos = len(gastos_list)

    # 3. Métrica Proveedores y Cuentas por Pagar
    from models import Provider, ProviderInvoice, ProviderPayment
    total_proveedores = Provider.query.count()
    invoices_all = ProviderInvoice.query.all()
    payments_all = ProviderPayment.query.all()
    total_facturado_prov = sum((i.monto_total for i in invoices_all), Decimal('0.00'))
    total_abonos_prov = sum((p.monto_abonado for p in payments_all), Decimal('0.00'))
    deuda_proveedores = total_facturado_prov - total_abonos_prov

    # 4. Métrica Arqueo de Caja por Local o General
    query_arqueos = ArqueoCaja.query
    if active_local != 'central':
        query_arqueos = query_arqueos.join(User, ArqueoCaja.vendedor_id == User.id).filter(User.local_asignado == int(active_local))
    total_arqueos = query_arqueos.count()
    ultimo_arqueo = query_arqueos.order_by(ArqueoCaja.fecha_creacion.desc()).first()

    # Métricas Informativas de Inventario
    todos_prods = Product.query.filter_by(tipo_inventario='tienda').all()
    total_productos = len(todos_prods)
    productos_bajo_stock = sum(1 for p in todos_prods if p.get_stock_local(active_local) <= 3)
    maneos_activos = Maneo.query.filter_by(estado='PENDIENTE').count()

    return render_template(
        'admin/dashboard.html',
        active_local=active_local,
        total_ventas=total_ventas,
        conteo_ventas=conteo_ventas,
        total_gastos=total_gastos,
        conteo_gastos=conteo_gastos,
        total_proveedores=total_proveedores,
        deuda_proveedores=deuda_proveedores,
        total_arqueos=total_arqueos,
        ultimo_arqueo=ultimo_arqueo,
        total_productos=total_productos,
        productos_bajo_stock=productos_bajo_stock,
        maneos_activos=maneos_activos
    )

@admin_bp.route('/maneos')
@login_required
def maneos():
    lista_maneos = Maneo.query.order_by(Maneo.fecha_prestamo.desc()).all()
    # Priorizar PENDIENTE temporalmente
    lista_maneos.sort(key=lambda m: 0 if m.estado == 'PENDIENTE' else 1)
    
    productos = Product.query.order_by(Product.nombre).all()
    return render_template('admin/maneos.html', maneos=lista_maneos, productos=productos)

@admin_bp.route('/maneos/prestar', methods=['POST'])
@login_required
def maneos_prestar():
    sku = request.form.get('sku')
    cantidad = int(request.form.get('cantidad', 0))
    local_vecino = request.form.get('local_vecino')
    variant_id_str = request.form.get('variant_id')
    valor_unidad_str = request.form.get('valor_unidad', '0')
    try:
        valor_unidad = float(valor_unidad_str.replace(',', '').strip()) if valor_unidad_str else 0
    except (ValueError, AttributeError):
        valor_unidad = 0

    if not sku:
        flash('Asegúrate de escanear o ingresar un SKU válido.', 'danger')
        return redirect(url_for('admin_bp.maneos'))

    producto = Product.query.filter_by(sku=sku.strip()).first()
    if not producto:
        flash(f'Error: El producto con SKU "{sku}" no existe en el catálogo.', 'danger')
        return redirect(url_for('admin_bp.maneos'))

    # Determinar si se seleccionó una variante
    variante = None
    if variant_id_str and variant_id_str.strip():
        variante = ProductVariant.query.get(int(variant_id_str))
        if not variante or variante.product_id != producto.id:
            flash('La subcategoría seleccionada no pertenece a este producto.', 'danger')
            return redirect(url_for('admin_bp.maneos'))
        
        if variante.cantidad_stock < cantidad:
            flash(f'Stock insuficiente en la subcategoría "{variante.nombre_variante}" para prestar {cantidad} uds. (Stock actual: {variante.cantidad_stock}).', 'danger')
            return redirect(url_for('admin_bp.maneos'))
    else:
        if producto.cantidad_stock < cantidad:
            flash(f'Stock insuficiente para prestar {cantidad} unids. (Stock actual: {producto.cantidad_stock}).', 'danger')
            return redirect(url_for('admin_bp.maneos'))

    try:
        # Descontar stock de la variante o del producto base
        if variante:
            stock_anterior = variante.cantidad_stock
            variante.cantidad_stock -= cantidad
        else:
            stock_anterior = producto.cantidad_stock
            producto.cantidad_stock -= cantidad

        nuevo_maneo = Maneo(
            product_id=producto.id,
            variant_id=variante.id if variante else None,
            local_vecino=local_vecino.strip(),
            cantidad=cantidad,
            valor_unidad=valor_unidad,
            estado='PENDIENTE'
        )
        db.session.add(nuevo_maneo)

        # Registro en el Kardex
        ajuste = StockAdjustment(
            product_id=producto.id,
            admin_id=current_user.id,
            tipo_movimiento=f'Préstamo (Maneo) a {local_vecino}' + (f' [{variante.nombre_variante}]' if variante else ''),
            stock_anterior=stock_anterior,
            stock_nuevo=variante.cantidad_stock if variante else producto.cantidad_stock
        )
        db.session.add(ajuste)

        db.session.commit()
        flash('Maneo registrado y stock descontado exitosamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error al registrar el maneo. Transacción revertida.', 'danger')

    return redirect(url_for('admin_bp.maneos'))

@admin_bp.route('/maneos/facturar/<int:id>', methods=['POST'])
@login_required
def maneos_facturar(id):
    maneo = Maneo.query.get_or_404(id)
    if maneo.estado != 'PENDIENTE':
        flash('Este maneo ya fue resuelto.', 'warning')
        return redirect(url_for('admin_bp.maneos'))
    
    # Determinar precios según variante o producto base
    if maneo.variante:
        precio_sugerido_ref = float(maneo.variante.precio_sugerido or maneo.producto.precio_sugerido)
        precio_costo_ref = float(maneo.variante.precio_costo or maneo.producto.precio_costo)
        precio_minimo_ref = float(maneo.variante.precio_minimo or maneo.producto.precio_minimo)
    else:
        precio_sugerido_ref = float(maneo.producto.precio_sugerido)
        precio_costo_ref = float(maneo.producto.precio_costo)
        precio_minimo_ref = float(maneo.producto.precio_minimo)

    precio_venta = float(request.form.get('precio_venta', precio_sugerido_ref))
    cantidad_vendida = int(request.form.get('cantidad_vendida', maneo.cantidad))

    if cantidad_vendida <= 0 or cantidad_vendida > maneo.cantidad:
        flash(f'Operación rechazada: La cantidad vendida ({cantidad_vendida}) es inválida.', 'danger')
        return redirect(url_for('admin_bp.maneos'))

    precio_limite = precio_costo_ref if current_user.rol == 'admin' else precio_minimo_ref

    if float(precio_venta) < float(precio_limite):
        flash(f'Operación rechazada: El precio ingresado (${precio_venta}) es menor al límite autorizado para tu perfil de usuario (${precio_limite}).', 'danger')
        return redirect(url_for('admin_bp.maneos'))

    try:
        cantidad_no_vendida = maneo.cantidad - cantidad_vendida

        maneo.estado = 'FACTURADO'
        maneo.fecha_resolucion = obtener_hora_bogota()

        # Si hubo un cobro parcial, las unidades restantes vuelven al inventario
        if cantidad_no_vendida > 0:
            if maneo.variante:
                stock_anterior = maneo.variante.cantidad_stock
                maneo.variante.cantidad_stock += cantidad_no_vendida
                stock_nuevo = maneo.variante.cantidad_stock
            else:
                stock_anterior = maneo.producto.cantidad_stock
                maneo.producto.cantidad_stock += cantidad_no_vendida
                stock_nuevo = maneo.producto.cantidad_stock

            variante_label = f' [{maneo.variante.nombre_variante}]' if maneo.variante else ''
            ajuste_retorno = StockAdjustment(
                product_id=maneo.product_id,
                admin_id=current_user.id,
                tipo_movimiento=f'Dev. Parcial de Maneo ({maneo.local_vecino}){variante_label}',
                stock_anterior=stock_anterior,
                stock_nuevo=stock_nuevo
            )
            db.session.add(ajuste_retorno)
            
            # Actualizamos la cantidad del maneo a la realmente facturada para que el historial sea claro
            maneo.cantidad = cantidad_vendida

        metodo_pago_seleccionado = request.form.get('metodo_pago', 'efectivo')
        
        # Registrar la venta real del Maneo
        nueva_venta = Sale(
            vendedor_id=current_user.id,
            monto_total=(precio_venta * cantidad_vendida),
            metodo_pago=metodo_pago_seleccionado
        )
        db.session.add(nueva_venta)
        db.session.flush() # forzar DB a darnos un ID para nueva_venta
        
        detalle = SaleDetail(
            sale_id=nueva_venta.id,
            product_id=maneo.product_id,
            variant_id=maneo.variant_id,
            cantidad_vendida=cantidad_vendida,
            precio_venta_final=precio_venta
        )
        db.session.add(detalle)

        # Registrar el pago en SalePayment para consistencia con pagos mixtos
        pago = SalePayment(
            sale_id=nueva_venta.id,
            metodo_pago=metodo_pago_seleccionado,
            monto=(precio_venta * cantidad_vendida)
        )
        db.session.add(pago)
        
        db.session.commit()

        if cantidad_no_vendida > 0:
            flash(f'Maneo facturado parcialmente. Se registró la venta de ${precio_venta * cantidad_vendida} y se devolvieron {cantidad_no_vendida} uds al inventario.', 'success')
        else:
            flash(f'Maneo facturado totalmente. Se registró la venta de ${precio_venta * cantidad_vendida} en la caja.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error al facturar el maneo.', 'danger')

    return redirect(url_for('admin_bp.maneos'))

@admin_bp.route('/maneos/devolver/<int:id>', methods=['POST'])
@login_required
def maneos_devolver(id):
    maneo = Maneo.query.get_or_404(id)
    if maneo.estado != 'PENDIENTE':
        flash('Este maneo ya fue resuelto.', 'warning')
        return redirect(url_for('admin_bp.maneos'))

    cantidad_devuelta = int(request.form.get('cantidad_devuelta', maneo.cantidad))

    if cantidad_devuelta <= 0:
        flash('La cantidad a devolver debe ser mayor a 0.', 'danger')
        return redirect(url_for('admin_bp.maneos'))

    if cantidad_devuelta > maneo.cantidad:
        flash(f'No puedes devolver más de {maneo.cantidad} unidades (las que están prestadas).', 'danger')
        return redirect(url_for('admin_bp.maneos'))

    try:
        # Devolver stock a la variante o al producto base
        if maneo.variante:
            stock_anterior = maneo.variante.cantidad_stock
            maneo.variante.cantidad_stock += cantidad_devuelta
            stock_nuevo = maneo.variante.cantidad_stock
        else:
            stock_anterior = maneo.producto.cantidad_stock
            maneo.producto.cantidad_stock += cantidad_devuelta
            stock_nuevo = maneo.producto.cantidad_stock

        variante_label = f' [{maneo.variante.nombre_variante}]' if maneo.variante else ''

        # Registro en el Kardex del retorno
        ajuste = StockAdjustment(
            product_id=maneo.product_id,
            admin_id=current_user.id,
            tipo_movimiento=f'Devolución de Maneo ({maneo.local_vecino}){variante_label}',
            stock_anterior=stock_anterior,
            stock_nuevo=stock_nuevo
        )
        db.session.add(ajuste)

        # Determinar si es devolución total o parcial
        if cantidad_devuelta >= maneo.cantidad:
            # Devolución total: se cierra el maneo
            maneo.estado = 'DEVUELTO'
            maneo.fecha_resolucion = obtener_hora_bogota()
            db.session.commit()
            flash(f'Maneo cerrado. Se devolvieron {cantidad_devuelta} unidades al inventario.', 'success')
        else:
            # Devolución parcial: se reduce la cantidad y el maneo sigue PENDIENTE
            unidades_restantes = maneo.cantidad - cantidad_devuelta
            maneo.cantidad = unidades_restantes
            db.session.commit()
            flash(f'Devolución parcial registrada. Se devolvieron {cantidad_devuelta} uds al inventario. Quedan {unidades_restantes} uds pendientes de cobrar.', 'info')

    except Exception as e:
        db.session.rollback()
        flash('Error al procesar la devolución.', 'danger')

    return redirect(url_for('admin_bp.maneos'))

@admin_bp.route('/balance-financiero', methods=['GET', 'POST'])
@login_required
@admin_required
def balance_financiero():
    if request.method == 'POST':
        fecha_inicio_str = request.form.get('fecha_inicio')
        fecha_fin_str = request.form.get('fecha_fin')
        active_local = request.form.get('local', 'central').lower()
    else:
        fecha_inicio_str = request.args.get('fecha_inicio')
        fecha_fin_str = request.args.get('fecha_fin')
        active_local = request.args.get('local', 'central').lower()

    if active_local not in ['central', '1', '2', '3']:
        active_local = 'central'

    local_nombres = {
        'central': 'Central (Consolidado General)',
        '1': 'Local 1',
        '2': 'Local 2',
        '3': 'Local 3'
    }
    nombre_sede = local_nombres.get(active_local, 'Central (Consolidado General)')

    hoy = obtener_hora_bogota()
    import calendar
    if not fecha_inicio_str or not fecha_fin_str:
        # Por defecto, el mes actual
        primer_dia = hoy.replace(day=1)
        ultimo_dia_mes = calendar.monthrange(hoy.year, hoy.month)[1]
        ultimo_dia = hoy.replace(day=ultimo_dia_mes)
        
        fecha_inicio_str = primer_dia.strftime('%Y-%m-%d')
        fecha_fin_str = ultimo_dia.strftime('%Y-%m-%d')

    from datetime import datetime, timedelta
    try:
        inicio_dt = datetime.strptime(fecha_inicio_str, '%Y-%m-%d')
        fin_dt = datetime.strptime(fecha_fin_str, '%Y-%m-%d')
        # Avanzamos límite al inicio del siguiente día matemáticamente
        fin_dt_query = fin_dt + timedelta(days=1)
    except ValueError:
        flash("Formato de fecha inválido.", "danger")
        return redirect(url_for('admin_bp.dashboard'))

    # 1. Ventas Totales por Local o General
    query_sales = Sale.query.filter(Sale.fecha_venta >= inicio_dt, Sale.fecha_venta < fin_dt_query)
    if active_local != 'central':
        local_num = int(active_local)
        query_sales = query_sales.join(User, Sale.vendedor_id == User.id).filter(User.local_asignado == local_num)
    
    ventas_query = query_sales.all()
    ventas_efectivo = sum(v.monto_total for v in ventas_query if v.metodo_pago == 'efectivo')
    ventas_transferencia = sum(v.monto_total for v in ventas_query if v.metodo_pago in ['transferencia', 'nequi', 'bancolombia', 'daviplata'])
    total_ingresos = ventas_efectivo + ventas_transferencia

    # 2. Costo de Mercancía Vendida (COGS) por Local o General
    from decimal import Decimal
    query_detalles = SaleDetail.query.join(Sale).filter(
        Sale.fecha_venta >= inicio_dt,
        Sale.fecha_venta < fin_dt_query
    )
    if active_local != 'central':
        local_num = int(active_local)
        query_detalles = query_detalles.join(User, Sale.vendedor_id == User.id).filter(User.local_asignado == local_num)
        
    detalles_query = query_detalles.all()
    costos_directos = Decimal('0.00')
    for d in detalles_query:
        if d.nombre_manual:
            # Producto manual prestado
            costos_directos += (d.precio_costo_manual or 0) * d.cantidad_vendida
        elif d.variant_id:
            # Producto con variante: Priorizar costo de variante, luego producto
            v = d.variante
            p = d.producto
            if v and p:
                costo_u = v.precio_costo if v.precio_costo is not None else (p.precio_costo or 0)
                costos_directos += Decimal(str(costo_u)) * d.cantidad_vendida
        elif d.product_id:
            # Producto base sin variante
            p = d.producto
            if p:
                costos_directos += (p.precio_costo or 0) * d.cantidad_vendida

    # 3. Costos Indirectos y Gastos Operativos por Local o General
    from sqlalchemy import or_
    query_expenses = Expense.query.filter(Expense.fecha_gasto >= inicio_dt, Expense.fecha_gasto < fin_dt_query)
    if active_local != 'central':
        local_num = int(active_local)
        query_expenses = query_expenses.outerjoin(User, Expense.usuario_id == User.id).filter(
            or_(Expense.local_id == local_num, User.local_asignado == local_num)
        )
        
    gastos_query = query_expenses.all()
    costos_indirectos = sum(g.monto for g in gastos_query if g.tipo_gasto == 'Costo Indirecto')
    gastos_operacionales = sum(g.monto for g in gastos_query if g.tipo_gasto == 'Gasto Diario')
    
    total_salidas = float(costos_directos) + float(costos_indirectos) + float(gastos_operacionales)
    balance_neto = float(total_ingresos) - total_salidas

    datos_financieros = {
        'ventas_efectivo': float(ventas_efectivo),
        'ventas_transferencia': float(ventas_transferencia),
        'total_ingresos': float(total_ingresos),
        'costos_directos': float(costos_directos),
        'costos_indirectos': float(costos_indirectos),
        'gastos_operacionales': float(gastos_operacionales),
        'total_salidas': total_salidas,
        'balance_neto': balance_neto
    }

    return render_template(
        'admin/balance_reporte.html',
        fecha_inicio=fecha_inicio_str,
        fecha_fin=fecha_fin_str,
        fecha_generacion=hoy.strftime('%Y-%m-%d %H:%M'),
        datos=datos_financieros,
        active_local=active_local,
        nombre_sede=nombre_sede
    )
