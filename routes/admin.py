from flask import Blueprint, render_template, abort, request, redirect, url_for, flash, Response, jsonify
from flask_login import login_required, current_user
from models import db, Product, ProductVariant, Sale, User, Maneo, SaleDetail, SalePayment, StockAdjustment, Expense, ArqueoCaja, Provider, ProviderPayment, PuntoTransaction, obtener_hora_bogota
from sqlalchemy.sql import func
from sqlalchemy import or_
from werkzeug.security import generate_password_hash
from decorators import admin_required
from decimal import Decimal
from datetime import datetime, date, timedelta
import calendar
import io
import csv

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

    periodo = request.args.get('periodo', 'diario').lower()
    if periodo not in ['diario', 'semanal', 'quincenal', 'mensual']:
        periodo = 'diario'

    hoy = obtener_hora_bogota()
    
    if periodo == 'diario':
        inicio_periodo = hoy.replace(hour=0, minute=0, second=0, microsecond=0)
    elif periodo == 'semanal':
        # Inicio de la semana actual (Lunes)
        inicio_periodo = (hoy - timedelta(days=hoy.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    elif periodo == 'mensual':
        # Inicio del mes actual
        inicio_periodo = hoy.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        # quincenal (default)
        if hoy.day <= 15:
            inicio_periodo = hoy.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            inicio_periodo = hoy.replace(day=16, hour=0, minute=0, second=0, microsecond=0)

    # 1. Métrica Caja POS (Ventas por Local o General)
    query_sales = Sale.query.filter(Sale.fecha_venta >= inicio_periodo)
    if active_local != 'central':
        local_num = int(active_local)
        query_sales = query_sales.filter(Sale.local_id == local_num)
    
    ventas_list = query_sales.all()
    total_ventas = sum(v.monto_total for v in ventas_list) if ventas_list else 0.0
    conteo_ventas = len(ventas_list)

    # 2. Métrica Gastos por Local o General
    query_expenses = Expense.query.filter(Expense.fecha_gasto >= inicio_periodo)
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

    # Métricas Informativas de Inventario y Traslados
    from models import StockTransfer
    query_traslados = StockTransfer.query
    if active_local != 'central':
        local_num = int(active_local)
        query_traslados = query_traslados.filter(or_(StockTransfer.local_origen_id == local_num, StockTransfer.local_destino_id == local_num))
    total_traslados = query_traslados.count()

    todos_prods = Product.query.filter_by(tipo_inventario='tienda').all()
    total_productos = len(todos_prods)
    productos_bajo_stock = sum(1 for p in todos_prods if p.get_stock_local(active_local) <= 3)
    maneos_activos = Maneo.query.filter_by(estado='PENDIENTE').count()

    return render_template(
        'admin/dashboard.html',
        active_local=active_local,
        periodo=periodo,
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
        maneos_activos=maneos_activos,
        total_traslados=total_traslados
    )

@admin_bp.route('/maneos')
@login_required
def maneos():
    is_admin = (current_user.rol == 'admin')
    
    if is_admin:
        active_local = request.args.get('local', 'central').lower()
        if active_local not in ['central', '1', '2', '3']:
            active_local = 'central'
    else:
        active_local = str(getattr(current_user, 'local_asignado', 1) or '1')

    query = Maneo.query

    if not is_admin or active_local != 'central':
        local_num = int(active_local)
        query = query.filter(Maneo.local_id == local_num)

    lista_maneos = query.order_by(Maneo.fecha_prestamo.desc()).all()
    # Priorizar PENDIENTE temporalmente
    lista_maneos.sort(key=lambda m: 0 if m.estado == 'PENDIENTE' else 1)
    
    productos = Product.query.order_by(Product.nombre).all()
    return render_template(
        'admin/maneos.html',
        maneos=lista_maneos,
        productos=productos,
        active_local=active_local,
        is_admin=is_admin
    )

@admin_bp.route('/maneos/prestar', methods=['POST'])
@login_required
def maneos_prestar():
    import json
    local_vecino = request.form.get('local_vecino', '').strip()
    if not local_vecino:
        flash('Debes indicar el local vecino o persona receptora.', 'danger')
        return redirect(request.referrer or url_for('admin_bp.maneos'))

    # Determinar sede emisora del préstamo
    is_admin = (current_user.rol == 'admin')
    if is_admin:
        try:
            local_id_maneo = int(request.form.get('local_id') or getattr(current_user, 'local_asignado', 1) or 1)
        except (ValueError, TypeError):
            local_id_maneo = 1
    else:
        local_id_maneo = int(getattr(current_user, 'local_asignado', 1) or 1)

    items_json = request.form.get('items_json')
    items = []
    if items_json:
        try:
            items = json.loads(items_json)
        except Exception:
            items = []

    if not items:
        # Fallback a producto único
        sku = request.form.get('sku', '').strip()
        cantidad = int(request.form.get('cantidad', 1))
        variant_id_str = request.form.get('variant_id')
        valor_unidad_str = request.form.get('valor_unidad', '0')
        try:
            valor_unidad = float(valor_unidad_str.replace(',', '').strip()) if valor_unidad_str else 0
        except (ValueError, AttributeError):
            valor_unidad = 0
        if sku:
            items = [{
                'sku': sku,
                'cantidad': cantidad,
                'variant_id': int(variant_id_str) if variant_id_str and variant_id_str.strip() else None,
                'valor_unidad': valor_unidad
            }]

    if not items:
        flash('Debes agregar al menos un producto para registrar el préstamo.', 'danger')
        return redirect(request.referrer or url_for('admin_bp.maneos'))

    try:
        total_unidades = 0
        for it in items:
            item_sku = str(it.get('sku', '')).strip()
            item_cant = int(it.get('cantidad', 1))
            item_variant_id = it.get('variant_id')
            try:
                item_valor = float(str(it.get('valor_unidad', 0)).replace(',', '').strip())
            except (ValueError, AttributeError):
                item_valor = 0

            if item_cant <= 0:
                continue

            producto = Product.query.filter_by(sku=item_sku).first()
            if not producto:
                raise ValueError(f'El producto con SKU "{item_sku}" no existe en el catálogo.')

            variante = None
            if item_variant_id:
                variante = ProductVariant.query.get(int(item_variant_id))
                if not variante or variante.product_id != producto.id:
                    raise ValueError(f'La subcategoría seleccionada no pertenece al producto {producto.nombre}.')

            # Validar y descontar stock en la sede emisora solo si el producto o variante tiene activado el descuento de inventario
            debe_descontar = variante.descontar_inventario if (variante and hasattr(variante, 'descontar_inventario') and variante.descontar_inventario) else (producto.descontar_inventario if hasattr(producto, 'descontar_inventario') else False)

            if debe_descontar:
                if variante:
                    stock_disponible = variante.get_stock_local(str(local_id_maneo))
                    if item_cant > stock_disponible:
                        raise ValueError(f'Stock insuficiente en D&L {local_id_maneo} para la subcategoría "{variante.nombre_variante}". Disponible: {stock_disponible}, solicitado: {item_cant}.')

                    stock_anterior = variante.total_stock
                    if local_id_maneo == 1:
                        variante.stock_local_1 = max(0, (variante.stock_local_1 or 0) - item_cant)
                    elif local_id_maneo == 2:
                        variante.stock_local_2 = max(0, (variante.stock_local_2 or 0) - item_cant)
                    elif local_id_maneo == 3:
                        variante.stock_local_3 = max(0, (variante.stock_local_3 or 0) - item_cant)

                    variante.cantidad_stock = variante.total_stock
                    producto.cantidad_stock = producto.total_stock
                    stock_nuevo = variante.total_stock
                else:
                    stock_disponible = producto.get_stock_local(str(local_id_maneo))
                    if item_cant > stock_disponible:
                        raise ValueError(f'Stock insuficiente en D&L {local_id_maneo} para "{producto.nombre}". Disponible: {stock_disponible}, solicitado: {item_cant}.')

                    stock_anterior = producto.total_stock
                    if local_id_maneo == 1:
                        producto.stock_local_1 = max(0, (producto.stock_local_1 or 0) - item_cant)
                    elif local_id_maneo == 2:
                        producto.stock_local_2 = max(0, (producto.stock_local_2 or 0) - item_cant)
                    elif local_id_maneo == 3:
                        producto.stock_local_3 = max(0, (producto.stock_local_3 or 0) - item_cant)

                    producto.cantidad_stock = producto.total_stock
                    stock_nuevo = producto.total_stock

                # Registro en el Kardex solo si hubo descuento de inventario
                ajuste = StockAdjustment(
                    product_id=producto.id,
                    admin_id=current_user.id,
                    tipo_movimiento=f'Préstamo (Maneo) a {local_vecino}' + (f' [{variante.nombre_variante}]' if variante else '') + f' desde D&L {local_id_maneo}',
                    stock_anterior=stock_anterior,
                    stock_nuevo=stock_nuevo
                )
                db.session.add(ajuste)

            nuevo_maneo = Maneo(
                product_id=producto.id,
                variant_id=variante.id if variante else None,
                local_vecino=local_vecino,
                cantidad=item_cant,
                valor_unidad=item_valor,
                estado='PENDIENTE',
                local_id=local_id_maneo,
                usuario_id=current_user.id
            )
            db.session.add(nuevo_maneo)
            total_unidades += item_cant

        db.session.commit()
        if len(items) > 1:
            flash(f'¡Préstamo de {len(items)} productos ({total_unidades} unidades en total) registrado a {local_vecino} desde D&L {local_id_maneo} exitosamente!', 'success')
        else:
            flash(f'¡Maneo registrado desde D&L {local_id_maneo} exitosamente!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al registrar el préstamo: {str(e)}', 'danger')

    return redirect(request.referrer or url_for('admin_bp.maneos'))

@admin_bp.route('/maneos/facturar/<int:id>', methods=['POST'])
@login_required
def maneos_facturar(id):
    maneo = Maneo.query.get_or_404(id)
    if maneo.estado != 'PENDIENTE':
        flash('Este maneo ya fue resuelto.', 'warning')
        return redirect(request.referrer or url_for('admin_bp.maneos'))
    
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
        return redirect(request.referrer or url_for('admin_bp.maneos'))

    precio_limite = precio_costo_ref if current_user.rol == 'admin' else precio_minimo_ref

    if float(precio_venta) < float(precio_limite):
        flash(f'Operación rechazada: El precio ingresado (${precio_venta}) es menor al límite autorizado para tu perfil de usuario (${precio_limite}).', 'danger')
        return redirect(request.referrer or url_for('admin_bp.maneos'))

    try:
        cantidad_no_vendida = maneo.cantidad - cantidad_vendida

        maneo.estado = 'FACTURADO'
        maneo.fecha_resolucion = obtener_hora_bogota()

        # Si hubo un cobro parcial, las unidades restantes vuelven al inventario de la sede de origen si aplica descuento
        if cantidad_no_vendida > 0:
            debe_descontar = maneo.variante.descontar_inventario if (maneo.variante and hasattr(maneo.variante, 'descontar_inventario') and maneo.variante.descontar_inventario) else (maneo.producto.descontar_inventario if hasattr(maneo.producto, 'descontar_inventario') else False)
            if debe_descontar:
                loc_id = maneo.local_id or 1
                if maneo.variante:
                    stock_anterior = maneo.variante.total_stock
                    if loc_id == 1:
                        maneo.variante.stock_local_1 = (maneo.variante.stock_local_1 or 0) + cantidad_no_vendida
                    elif loc_id == 2:
                        maneo.variante.stock_local_2 = (maneo.variante.stock_local_2 or 0) + cantidad_no_vendida
                    elif loc_id == 3:
                        maneo.variante.stock_local_3 = (maneo.variante.stock_local_3 or 0) + cantidad_no_vendida
                    maneo.variante.cantidad_stock = maneo.variante.total_stock
                    maneo.producto.cantidad_stock = maneo.producto.total_stock
                    stock_nuevo = maneo.variante.total_stock
                else:
                    stock_anterior = maneo.producto.total_stock
                    if loc_id == 1:
                        maneo.producto.stock_local_1 = (maneo.producto.stock_local_1 or 0) + cantidad_no_vendida
                    elif loc_id == 2:
                        maneo.producto.stock_local_2 = (maneo.producto.stock_local_2 or 0) + cantidad_no_vendida
                    elif loc_id == 3:
                        maneo.producto.stock_local_3 = (maneo.producto.stock_local_3 or 0) + cantidad_no_vendida
                    maneo.producto.cantidad_stock = maneo.producto.total_stock
                    stock_nuevo = maneo.producto.total_stock

                variante_label = f' [{maneo.variante.nombre_variante}]' if maneo.variante else ''
                ajuste_retorno = StockAdjustment(
                    product_id=maneo.product_id,
                    admin_id=current_user.id,
                    tipo_movimiento=f'Dev. Parcial de Maneo ({maneo.local_vecino}){variante_label} en D&L {loc_id}',
                    stock_anterior=stock_anterior,
                    stock_nuevo=stock_nuevo
                )
                db.session.add(ajuste_retorno)
            
            # Actualizamos la cantidad del maneo a la realmente facturada para que el historial sea claro
            maneo.cantidad = cantidad_vendida

        metodo_pago_seleccionado = request.form.get('metodo_pago', 'efectivo')
        local_destino_venta = maneo.local_id or getattr(current_user, 'local_asignado', 1) or 1
        
        # Registrar la venta real del Maneo en el local emisor
        nueva_venta = Sale(
            vendedor_id=current_user.id,
            local_id=local_destino_venta,
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
            flash(f'Maneo facturado parcialmente. Se registró la venta de ${precio_venta * cantidad_vendida:,.0f} en D&L {local_destino_venta} y se devolvieron {cantidad_no_vendida} uds al inventario.', 'success')
        else:
            flash(f'Maneo facturado totalmente. Se registró la venta de ${precio_venta * cantidad_vendida:,.0f} en la caja de D&L {local_destino_venta}.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error al facturar el maneo.', 'danger')

    return redirect(request.referrer or url_for('admin_bp.maneos'))

@admin_bp.route('/maneos/devolver/<int:id>', methods=['POST'])
@login_required
def maneos_devolver(id):
    maneo = Maneo.query.get_or_404(id)
    if maneo.estado != 'PENDIENTE':
        flash('Este maneo ya fue resuelto.', 'warning')
        return redirect(request.referrer or url_for('admin_bp.maneos'))

    cantidad_devuelta = int(request.form.get('cantidad_devuelta', maneo.cantidad))

    if cantidad_devuelta <= 0:
        flash('La cantidad a devolver debe ser mayor a 0.', 'danger')
        return redirect(request.referrer or url_for('admin_bp.maneos'))

    if cantidad_devuelta > maneo.cantidad:
        flash(f'No puedes devolver más de {maneo.cantidad} unidades (las que están prestadas).', 'danger')
        return redirect(request.referrer or url_for('admin_bp.maneos'))

    try:
        # Devolver stock a la sede de origen del maneo solo si el producto descuenta inventario
        loc_id = maneo.local_id or 1
        debe_descontar = maneo.variante.descontar_inventario if (maneo.variante and hasattr(maneo.variante, 'descontar_inventario') and maneo.variante.descontar_inventario) else (maneo.producto.descontar_inventario if hasattr(maneo.producto, 'descontar_inventario') else False)
        
        if debe_descontar:
            if maneo.variante:
                stock_anterior = maneo.variante.total_stock
                if loc_id == 1:
                    maneo.variante.stock_local_1 = (maneo.variante.stock_local_1 or 0) + cantidad_devuelta
                elif loc_id == 2:
                    maneo.variante.stock_local_2 = (maneo.variante.stock_local_2 or 0) + cantidad_devuelta
                elif loc_id == 3:
                    maneo.variante.stock_local_3 = (maneo.variante.stock_local_3 or 0) + cantidad_devuelta
                maneo.variante.cantidad_stock = maneo.variante.total_stock
                maneo.producto.cantidad_stock = maneo.producto.total_stock
                stock_nuevo = maneo.variante.total_stock
            else:
                stock_anterior = maneo.producto.total_stock
                if loc_id == 1:
                    maneo.producto.stock_local_1 = (maneo.producto.stock_local_1 or 0) + cantidad_devuelta
                elif loc_id == 2:
                    maneo.producto.stock_local_2 = (maneo.producto.stock_local_2 or 0) + cantidad_devuelta
                elif loc_id == 3:
                    maneo.producto.stock_local_3 = (maneo.producto.stock_local_3 or 0) + cantidad_devuelta
                maneo.producto.cantidad_stock = maneo.producto.total_stock
                stock_nuevo = maneo.producto.total_stock

            variante_label = f' [{maneo.variante.nombre_variante}]' if maneo.variante else ''

            # Registro en el Kardex del retorno
            ajuste = StockAdjustment(
                product_id=maneo.product_id,
                admin_id=current_user.id,
                tipo_movimiento=f'Devolución de Maneo ({maneo.local_vecino}){variante_label} a D&L {loc_id}',
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
            flash(f'Maneo cerrado. Se registraron {cantidad_devuelta} unidades como devueltas en D&L {loc_id}.', 'success')
        else:
            # Devolución parcial: se reduce la cantidad y el maneo sigue PENDIENTE
            unidades_restantes = maneo.cantidad - cantidad_devuelta
            maneo.cantidad = unidades_restantes
            db.session.commit()
            flash(f'Devolución parcial registrada. Se devolvieron {cantidad_devuelta} uds en D&L {loc_id}. Quedan {unidades_restantes} uds pendientes de cobrar.', 'info')

    except Exception as e:
        db.session.rollback()
        flash('Error al procesar la devolución.', 'danger')

    return redirect(request.referrer or url_for('admin_bp.maneos'))

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
        '1': 'D&L 1',
        '2': 'D&L 2',
        '3': 'D&L 3'
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
    
    from decimal import Decimal
    desglose_pagos = {
        'efectivo': Decimal('0.00'),
        'nequi': Decimal('0.00'),
        'bancolombia': Decimal('0.00'),
        'daviplata': Decimal('0.00'),
        'bold': Decimal('0.00'),
        'addi': Decimal('0.00'),
        'transferencia': Decimal('0.00'),
        'otros': Decimal('0.00')
    }

    for v in ventas_query:
        if v.pagos and len(v.pagos) > 0:
            for pago in v.pagos:
                metodo = (pago.metodo_pago or 'efectivo').lower().strip()
                if metodo in ['bold', 'bolt']:
                    metodo = 'bold'
                monto = Decimal(str(pago.monto or 0))
                if metodo in desglose_pagos:
                    desglose_pagos[metodo] += monto
                else:
                    desglose_pagos['otros'] += monto
        else:
            metodo = (v.metodo_pago or 'efectivo').lower().strip()
            if metodo in ['bold', 'bolt']:
                metodo = 'bold'
            monto = Decimal(str(v.monto_total or 0))
            if metodo in desglose_pagos:
                desglose_pagos[metodo] += monto
            else:
                desglose_pagos['otros'] += monto

    ventas_efectivo = desglose_pagos['efectivo']
    ventas_digitales = (
        desglose_pagos['nequi'] +
        desglose_pagos['bancolombia'] +
        desglose_pagos['daviplata'] +
        desglose_pagos['bold'] +
        desglose_pagos['addi'] +
        desglose_pagos['transferencia'] +
        desglose_pagos['otros']
    )

    # 4. Sobrantes y Faltantes de Arqueos de Caja
    from models import ArqueoCaja
    query_arqueos = ArqueoCaja.query.filter(
        ArqueoCaja.fecha_arqueo >= inicio_dt.date(),
        ArqueoCaja.fecha_arqueo <= fin_dt.date()
    )
    if active_local != 'central':
        query_arqueos = query_arqueos.filter(ArqueoCaja.local_id == int(active_local))

    sobrantes_caja = Decimal('0.00')
    faltantes_caja = Decimal('0.00')
    for arq in query_arqueos.all():
        dif = Decimal(str(arq.monto_diferencia or 0))
        if dif > 0:
            sobrantes_caja += dif
        elif dif < 0:
            faltantes_caja += abs(dif)

    total_ingresos = ventas_efectivo + ventas_digitales + sobrantes_caja

    # 2. Costo de Mercancía Vendida (COGS) por Local o General
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

    # 3. Costos Indirectos, Abonos a Puntos y Gastos Operativos por Local o General
    from sqlalchemy import or_
    query_expenses = Expense.query.filter(Expense.fecha_gasto >= inicio_dt, Expense.fecha_gasto < fin_dt_query)
    if active_local != 'central':
        local_num = int(active_local)
        query_expenses = query_expenses.outerjoin(User, Expense.usuario_id == User.id).filter(
            or_(Expense.local_id == local_num, User.local_asignado == local_num)
        )
        
    gastos_query = query_expenses.all()

    def es_abono_punto(gasto):
        cat = (gasto.categoria or '').strip().lower()
        return cat in ['punto', 'abono a punto/local'] or 'abono a punto' in cat

    costos_indirectos = sum(g.monto for g in gastos_query if g.tipo_gasto == 'Costo Indirecto')
    abonos_puntos = sum(g.monto for g in gastos_query if es_abono_punto(g))
    gastos_operacionales = sum(g.monto for g in gastos_query if g.tipo_gasto == 'Gasto Diario' and not es_abono_punto(g))
    
    total_salidas = float(costos_directos) + float(costos_indirectos) + float(gastos_operacionales) + float(abonos_puntos) + float(faltantes_caja)
    balance_neto = float(total_ingresos) - total_salidas

    datos_financieros = {
        'ventas_efectivo': float(ventas_efectivo),
        'ventas_nequi': float(desglose_pagos['nequi']),
        'ventas_bancolombia': float(desglose_pagos['bancolombia']),
        'ventas_daviplata': float(desglose_pagos['daviplata']),
        'ventas_bold': float(desglose_pagos['bold']),
        'ventas_addi': float(desglose_pagos['addi']),
        'ventas_transferencia': float(desglose_pagos['transferencia']),
        'ventas_otros': float(desglose_pagos['otros']),
        'ventas_digitales': float(ventas_digitales),
        'ventas_transferencia_total': float(ventas_digitales),
        'sobrantes_caja': float(sobrantes_caja),
        'faltantes_caja': float(faltantes_caja),
        'total_ingresos': float(total_ingresos),
        'costos_directos': float(costos_directos),
        'costos_indirectos': float(costos_indirectos),
        'gastos_operacionales': float(gastos_operacionales),
        'abonos_puntos': float(abonos_puntos),
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

# =========================================================================
# MÓDULO CENTRALIZADO: TESORERÍA Y FLUJO DE CAJA CONSOLIDADO
# =========================================================================

def normalizar_metodo_pago(metodo_raw):
    """Normaliza las cadenas de métodos de pago a identificadores estándar."""
    if not metodo_raw:
        return 'efectivo'
    m = str(metodo_raw).strip().lower()
    if 'efectivo' in m:
        return 'efectivo'
    if 'nequi' in m:
        return 'nequi'
    if 'bancolombia' in m:
        return 'bancolombia'
    if 'daviplata' in m:
        return 'daviplata'
    if 'bold' in m or 'bolt' in m or 'tarjeta' in m or 'datafono' in m:
        return 'bold'
    if 'addi' in m:
        return 'addi'
    if 'transf' in m:
        return 'transferencia'
    return 'otros'

def obtener_datos_tesoreria(args):
    """Procesa filtros, consolida movimientos de todas las sedes y calcula los KPIs de tesorería."""
    hoy = obtener_hora_bogota()
    periodo = args.get('periodo', 'mes').lower()
    fecha_inicio_str = args.get('fecha_inicio', '').strip()
    fecha_fin_str = args.get('fecha_fin', '').strip()
    active_local = args.get('local', 'todos').lower()
    tipo_flujo = args.get('tipo_flujo', 'todos').lower()
    tipo_operacion = args.get('tipo_operacion', 'todos').strip()
    if hasattr(args, 'getlist'):
        metodos_raw = args.getlist('metodos') or args.get('metodos', '')
    else:
        metodos_raw = args.get('metodos', '')

    if isinstance(metodos_raw, str) and metodos_raw:
        metodos_filtro = [m.strip().lower() for m in metodos_raw.split(',') if m.strip()]
    elif isinstance(metodos_raw, (list, tuple)):
        metodos_filtro = [m.strip().lower() for m in metodos_raw if m.strip()]
    else:
        metodos_filtro = []

    query_search = args.get('q', '').strip().lower()

    # Lista completa de pasarelas soportadas por el sistema
    metodos_disponibles = ['efectivo', 'nequi', 'bancolombia', 'daviplata', 'bold', 'addi', 'transferencia']

    # 1. Determinación del Rango de Fechas
    if periodo == 'hoy':
        inicio_dt = hoy.replace(hour=0, minute=0, second=0, microsecond=0)
        fin_dt = hoy.replace(hour=23, minute=59, second=59, microsecond=999999)
        fecha_inicio_str = inicio_dt.strftime('%Y-%m-%d')
        fecha_fin_str = fin_dt.strftime('%Y-%m-%d')
    elif periodo == 'semana':
        lunes = (hoy - timedelta(days=hoy.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        domingo = (lunes + timedelta(days=6)).replace(hour=23, minute=59, second=59, microsecond=999999)
        inicio_dt = lunes
        fin_dt = domingo
        fecha_inicio_str = inicio_dt.strftime('%Y-%m-%d')
        fecha_fin_str = fin_dt.strftime('%Y-%m-%d')
    elif periodo == 'quincena':
        if hoy.day <= 15:
            inicio_dt = hoy.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            fin_dt = hoy.replace(day=15, hour=23, minute=59, second=59, microsecond=999999)
        else:
            ultimo_dia = calendar.monthrange(hoy.year, hoy.month)[1]
            inicio_dt = hoy.replace(day=16, hour=0, minute=0, second=0, microsecond=0)
            fin_dt = hoy.replace(day=ultimo_dia, hour=23, minute=59, second=59, microsecond=999999)
        fecha_inicio_str = inicio_dt.strftime('%Y-%m-%d')
        fecha_fin_str = fin_dt.strftime('%Y-%m-%d')
    elif periodo == 'mes':
        ultimo_dia = calendar.monthrange(hoy.year, hoy.month)[1]
        inicio_dt = hoy.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        fin_dt = hoy.replace(day=ultimo_dia, hour=23, minute=59, second=59, microsecond=999999)
        fecha_inicio_str = inicio_dt.strftime('%Y-%m-%d')
        fecha_fin_str = fin_dt.strftime('%Y-%m-%d')
    else:
        periodo = 'personalizado'
        try:
            inicio_dt = datetime.strptime(fecha_inicio_str, '%Y-%m-%d').replace(hour=0, minute=0, second=0, microsecond=0)
            fin_dt = datetime.strptime(fecha_fin_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59, microsecond=999999)
        except (ValueError, TypeError):
            periodo = 'mes'
            ultimo_dia = calendar.monthrange(hoy.year, hoy.month)[1]
            inicio_dt = hoy.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            fin_dt = hoy.replace(day=ultimo_dia, hour=23, minute=59, second=59, microsecond=999999)
            fecha_inicio_str = inicio_dt.strftime('%Y-%m-%d')
            fecha_fin_str = fin_dt.strftime('%Y-%m-%d')

    movimientos_brutos = []

    # 2. Consolidar Ventas POS (Ingresos)
    q_sales = Sale.query.filter(Sale.fecha_venta >= inicio_dt, Sale.fecha_venta <= fin_dt)
    if active_local in ['1', '2', '3']:
        q_sales = q_sales.filter(Sale.local_id == int(active_local))

    for sale in q_sales.all():
        loc_id = sale.local_id or 1
        cajero_nombre = sale.vendedor.nombre if sale.vendedor else 'Cajero'
        if sale.pagos and len(sale.pagos) > 0:
            for p in sale.pagos:
                met = normalizar_metodo_pago(p.metodo_pago)
                monto = float(p.monto or 0)
                if monto > 0:
                    movimientos_brutos.append({
                        'id': f"V-{sale.id}-{p.id}",
                        'fecha': sale.fecha_venta or inicio_dt,
                        'fecha_str': (sale.fecha_venta or inicio_dt).strftime('%d/%m/%Y %I:%M %p'),
                        'local_id': loc_id,
                        'tipo_flujo': 'ingreso',
                        'tipo_operacion': 'Venta',
                        'concepto': f"Venta POS #{sale.id:05d}" + (f" ({len(sale.detalles)} productos)" if sale.detalles else ""),
                        'metodo_pago': met,
                        'monto': monto,
                        'usuario': cajero_nombre,
                        'referencia': f"Ticket #{sale.id:05d}",
                        'referencia_id': sale.id,
                        'link_recibo': f"/sales/recibo/{sale.id}"
                    })
        else:
            met = normalizar_metodo_pago(sale.metodo_pago)
            monto = float(sale.monto_total or 0)
            if monto > 0:
                movimientos_brutos.append({
                    'id': f"V-{sale.id}",
                    'fecha': sale.fecha_venta or inicio_dt,
                    'fecha_str': (sale.fecha_venta or inicio_dt).strftime('%d/%m/%Y %I:%M %p'),
                    'local_id': loc_id,
                    'tipo_flujo': 'ingreso',
                    'tipo_operacion': 'Venta',
                    'concepto': f"Venta POS #{sale.id:05d}" + (f" ({len(sale.detalles)} productos)" if sale.detalles else ""),
                    'metodo_pago': met,
                    'monto': monto,
                    'usuario': cajero_nombre,
                    'referencia': f"Ticket #{sale.id:05d}",
                    'referencia_id': sale.id,
                    'link_recibo': f"/sales/recibo/{sale.id}"
                })

    # 3. Consolidar Egresos (Gastos Operativos, Pagos a Puntos y Proveedores)
    q_expenses = Expense.query.filter(Expense.fecha_gasto >= inicio_dt, Expense.fecha_gasto <= fin_dt)
    if active_local in ['1', '2', '3']:
        q_expenses = q_expenses.filter(Expense.local_id == int(active_local))

    for g in q_expenses.all():
        loc_id = g.local_id or 1
        cat_lower = (g.categoria or '').strip().lower()
        if 'punto' in cat_lower or 'abono a punto' in cat_lower:
            op_tipo = 'Pago a Punto'
        elif 'proveedor' in cat_lower or 'factura prov' in cat_lower:
            op_tipo = 'Abono a Proveedor'
        else:
            op_tipo = 'Gasto Operativo'

        met = normalizar_metodo_pago(g.metodo_pago)
        monto = float(g.monto or 0)
        if monto > 0:
            movimientos_brutos.append({
                'id': f"G-{g.id}",
                'fecha': g.fecha_gasto or inicio_dt,
                'fecha_str': (g.fecha_gasto or inicio_dt).strftime('%d/%m/%Y %I:%M %p'),
                'local_id': loc_id,
                'tipo_flujo': 'egreso',
                'tipo_operacion': op_tipo,
                'concepto': f"[{g.categoria}] {g.descripcion or 'Gasto operativo'}",
                'metodo_pago': met,
                'monto': monto,
                'usuario': g.usuario.nombre if g.usuario else 'Admin/Usuario',
                'referencia': f"Gasto #{g.id}",
                'referencia_id': g.id,
                'link_recibo': None
            })

    # 4. Consolidar Ajustes de Arqueo de Caja (Discrepancias Físicas)
    q_arqueos = ArqueoCaja.query.filter(ArqueoCaja.fecha_arqueo >= inicio_dt.date(), ArqueoCaja.fecha_arqueo <= fin_dt.date())
    if active_local in ['1', '2', '3']:
        q_arqueos = q_arqueos.filter(ArqueoCaja.local_id == int(active_local))

    for arq in q_arqueos.all():
        dif = float(arq.diferencia or 0)
        if abs(dif) >= 1.0:
            loc_id = arq.local_id or 1
            dt_arq = arq.fecha_creacion or datetime.combine(arq.fecha_arqueo, datetime.min.time())
            cajero_arq = arq.cajero.nombre if arq.cajero else 'Cajero'
            if dif > 0:
                movimientos_brutos.append({
                    'id': f"A-{arq.id}-S",
                    'fecha': dt_arq,
                    'fecha_str': dt_arq.strftime('%d/%m/%Y %I:%M %p'),
                    'local_id': loc_id,
                    'tipo_flujo': 'ingreso',
                    'tipo_operacion': 'Ajuste de Arqueo',
                    'concepto': f"Sobrante en Arqueo de Caja del {arq.fecha_arqueo.strftime('%d/%m/%Y')} (D&L {loc_id})",
                    'metodo_pago': 'efectivo',
                    'monto': abs(dif),
                    'usuario': cajero_arq,
                    'referencia': f"Arqueo #{arq.id}",
                    'referencia_id': arq.id,
                    'link_recibo': None
                })
            else:
                movimientos_brutos.append({
                    'id': f"A-{arq.id}-F",
                    'fecha': dt_arq,
                    'fecha_str': dt_arq.strftime('%d/%m/%Y %I:%M %p'),
                    'local_id': loc_id,
                    'tipo_flujo': 'egreso',
                    'tipo_operacion': 'Ajuste de Arqueo',
                    'concepto': f"Faltante en Arqueo de Caja del {arq.fecha_arqueo.strftime('%d/%m/%Y')} (D&L {loc_id})",
                    'metodo_pago': 'efectivo',
                    'monto': abs(dif),
                    'usuario': cajero_arq,
                    'referencia': f"Arqueo #{arq.id}",
                    'referencia_id': arq.id,
                    'link_recibo': None
                })

    # 5. Aplicación de Filtros en Memoria
    movimientos_base = []
    for m in movimientos_brutos:
        # Filtro Tipo de Flujo
        if tipo_flujo in ['ingreso', 'egreso'] and m['tipo_flujo'] != tipo_flujo:
            continue

        # Filtro Tipo de Operación
        if tipo_operacion != 'todos' and tipo_operacion:
            op_low = tipo_operacion.lower()
            if op_low in ['ingreso', 'ingresos']:
                if m['tipo_flujo'] != 'ingreso':
                    continue
            elif op_low in ['egreso', 'egresos', 'salida', 'salidas']:
                if m['tipo_flujo'] != 'egreso':
                    continue
            elif m['tipo_operacion'].lower() != op_low:
                continue

        # Filtro de Búsqueda de Texto
        if query_search:
            match_txt = f"{m['concepto']} {m['usuario']} {m['referencia']} {m['tipo_operacion']}".lower()
            if query_search not in match_txt:
                continue

        movimientos_base.append(m)

    # Cálculo de métricas por Pasarela (previo al filtro individual de método para mantener visibles los totales)
    desglose_pasarelas = {}
    for met in metodos_disponibles:
        ing_met = sum(m['monto'] for m in movimientos_base if m['tipo_flujo'] == 'ingreso' and m['metodo_pago'] == met)
        egr_met = sum(m['monto'] for m in movimientos_base if m['tipo_flujo'] == 'egreso' and m['metodo_pago'] == met)
        desglose_pasarelas[met] = {
            'ingresos': ing_met,
            'egresos': egr_met,
            'neto': ing_met - egr_met,
            'total_transacciones': sum(1 for m in movimientos_base if m['metodo_pago'] == met)
        }

    # Filtro específico de Método de Pago si fue seleccionado
    movimientos_filtrados = []
    for m in movimientos_base:
        if metodos_filtro and len(metodos_filtro) > 0:
            if m['metodo_pago'] not in metodos_filtro:
                continue
        movimientos_filtrados.append(m)

    # Ordenar cronológicamente descendente (más reciente primero)
    movimientos_filtrados.sort(key=lambda x: x['fecha'], reverse=True)

    # 6. Cálculo de KPIs y Desgloses Financieros para la tabla y balances
    total_ingresos = sum(m['monto'] for m in movimientos_filtrados if m['tipo_flujo'] == 'ingreso')
    total_egresos = sum(m['monto'] for m in movimientos_filtrados if m['tipo_flujo'] == 'egreso')
    total_neto = total_ingresos - total_egresos
    conteo_ingresos = sum(1 for m in movimientos_filtrados if m['tipo_flujo'] == 'ingreso')
    conteo_egresos = sum(1 for m in movimientos_filtrados if m['tipo_flujo'] == 'egreso')

    # Desglose por Sede
    desglose_sedes = {
        1: {'ingresos': sum(m['monto'] for m in movimientos_filtrados if m['local_id'] == 1 and m['tipo_flujo'] == 'ingreso'),
            'egresos': sum(m['monto'] for m in movimientos_filtrados if m['local_id'] == 1 and m['tipo_flujo'] == 'egreso')},
        2: {'ingresos': sum(m['monto'] for m in movimientos_filtrados if m['local_id'] == 2 and m['tipo_flujo'] == 'ingreso'),
            'egresos': sum(m['monto'] for m in movimientos_filtrados if m['local_id'] == 2 and m['tipo_flujo'] == 'egreso')},
        3: {'ingresos': sum(m['monto'] for m in movimientos_filtrados if m['local_id'] == 3 and m['tipo_flujo'] == 'ingreso'),
            'egresos': sum(m['monto'] for m in movimientos_filtrados if m['local_id'] == 3 and m['tipo_flujo'] == 'egreso')}
    }

    return {
        'periodo': periodo,
        'fecha_inicio': fecha_inicio_str,
        'fecha_fin': fecha_fin_str,
        'active_local': active_local,
        'tipo_flujo': tipo_flujo,
        'tipo_operacion': tipo_operacion,
        'metodos_filtro': metodos_filtro,
        'metodos_disponibles': metodos_disponibles,
        'query_search': query_search,
        'movimientos': movimientos_filtrados,
        'total_movimientos': len(movimientos_filtrados),
        'total_ingresos': total_ingresos,
        'total_egresos': total_egresos,
        'total_neto': total_neto,
        'conteo_ingresos': conteo_ingresos,
        'conteo_egresos': conteo_egresos,
        'desglose_pasarelas': desglose_pasarelas,
        'desglose_sedes': desglose_sedes
    }

@admin_bp.route('/tesoreria', methods=['GET'])
@login_required
@admin_required
def tesoreria():
    data = obtener_datos_tesoreria(request.args)
    
    # Paginación en servidor
    try:
        page = int(request.args.get('page', 1))
    except (ValueError, TypeError):
        page = 1
    per_page = 50
    
    todos_movs = data['movimientos']
    total_items = len(todos_movs)
    total_pages = max((total_items + per_page - 1) // per_page, 1)
    page = max(1, min(page, total_pages))
    
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    movimientos_paginados = todos_movs[start_idx:end_idx]

    return render_template(
        'admin/tesoreria.html',
        data=data,
        movimientos=movimientos_paginados,
        page=page,
        total_pages=total_pages,
        total_items=total_items,
        per_page=per_page
    )

@admin_bp.route('/tesoreria/exportar', methods=['GET'])
@login_required
@admin_required
def tesoreria_exportar():
    data = obtener_datos_tesoreria(request.args)
    movimientos = data['movimientos']

    output = io.StringIO()
    # Escribir BOM UTF-8 para que Microsoft Excel lo abra sin problemas de codificación
    output.write('\ufeff')
    writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_MINIMAL)

    # Encabezado del reporte
    writer.writerow(["D&L - REPORTE CONSOLIDADO DE TESORERÍA Y FLUJO DE CAJA"])
    writer.writerow([f"Período: {data['periodo'].upper()} ({data['fecha_inicio']} al {data['fecha_fin']})"])
    writer.writerow([f"Sede: {('Todas las Sedes' if data['active_local'] == 'todos' else f'D&L {data['active_local']}')}"])
    writer.writerow([f"Generado el: {obtener_hora_bogota().strftime('%d/%m/%Y %I:%M %p')} por {current_user.nombre}"])
    writer.writerow([])

    # Columnas de la tabla
    writer.writerow([
        "Fecha y Hora",
        "Sede",
        "Tipo de Flujo",
        "Tipo de Operación",
        "Concepto / Descripción",
        "Método de Pago",
        "Ingreso (+)",
        "Egreso (-)",
        "Monto Neto ($)",
        "Usuario / Cajero",
        "Referencia"
    ])

    for m in movimientos:
        ing_val = m['monto'] if m['tipo_flujo'] == 'ingreso' else 0
        egr_val = m['monto'] if m['tipo_flujo'] == 'egreso' else 0
        neto_val = ing_val - egr_val

        writer.writerow([
            m['fecha_str'],
            f"D&L {m['local_id']}",
            m['tipo_flujo'].upper(),
            m['tipo_operacion'],
            m['concepto'],
            m['metodo_pago'].upper(),
            f"{ing_val:.0f}",
            f"{egr_val:.0f}",
            f"{neto_val:.0f}",
            m['usuario'],
            m['referencia']
        ])

    # Fila de Totales Generales
    writer.writerow([])
    writer.writerow([
        "TOTALES GENERALES",
        "",
        "",
        "",
        f"Total {len(movimientos)} transacciones",
        "",
        f"{data['total_ingresos']:.0f}",
        f"{data['total_egresos']:.0f}",
        f"{data['total_neto']:.0f}",
        "",
        ""
    ])

    # Desglose por Cuentas / Pasarelas
    writer.writerow([])
    writer.writerow(["DESGLOSE POR PASARELA / CUENTA"])
    writer.writerow(["Método de Pago", "Total Ingresos (+)", "Total Egresos (-)", "Saldo Neto"])
    for met, vals in data['desglose_pasarelas'].items():
        writer.writerow([
            met.upper(),
            f"{vals['ingresos']:.0f}",
            f"{vals['egresos']:.0f}",
            f"{vals['neto']:.0f}"
        ])

    filename = f"flujo_caja_DL_{data['fecha_inicio']}_al_{data['fecha_fin']}.csv"
    response = Response(output.getvalue(), mimetype='text/csv; charset=utf-8-sig')
    response.headers['Content-Disposition'] = f"attachment; filename={filename}"
    return response

