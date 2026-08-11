from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, StockTransfer, Product, ProductVariant, Asesor, User, obtener_hora_bogota
from decorators import admin_required
from sqlalchemy import or_

traslados_bp = Blueprint('traslados_bp', __name__)

@traslados_bp.route('/', methods=['GET'])
@login_required
def index():
    is_admin = (current_user.rol == 'admin')
    if is_admin:
        active_local = request.args.get('local', 'central').lower()
        if active_local not in ['central', '1', '2', '3']:
            active_local = 'central'
    else:
        active_local = str(getattr(current_user, 'local_asignado', 1) or '1')

    query = StockTransfer.query

    if active_local != 'central':
        local_num = int(active_local)
        query = query.filter(or_(StockTransfer.local_origen_id == local_num, StockTransfer.local_destino_id == local_num))

    traslados = query.order_by(StockTransfer.fecha_transferencia.desc()).all()

    # Métricas consolidadas
    total_traslados = len(traslados)
    total_unidades = sum((t.cantidad for t in traslados), 0)

    local_nombres = {
        'central': 'D&L CENTRAL',
        '1': 'D&L 1',
        '2': 'D&L 2',
        '3': 'D&L 3'
    }
    nombre_sede = local_nombres.get(active_local, 'D&L CENTRAL')

    return render_template(
        'traslados/index.html',
        traslados=traslados,
        total_traslados=total_traslados,
        total_unidades=total_unidades,
        active_local=active_local,
        is_admin=is_admin,
        nombre_sede=nombre_sede
    )

@traslados_bp.route('/solicitar', methods=['POST'])
@login_required
def solicitar():
    """API / Form Endpoint para ejecutar un traslado rápido entre sedes."""
    try:
        data = request.form or request.get_json(silent=True) or {}
        product_id = int(data.get('product_id'))
        variant_id = int(data.get('variant_id')) if data.get('variant_id') else None
        local_origen_id = int(data.get('local_origen_id'))
        local_destino_id = int(data.get('local_destino_id'))
        cantidad = int(data.get('cantidad', 1))
        asesor_id = int(data.get('asesor_id')) if data.get('asesor_id') else None
        observacion = data.get('observacion', '').strip()

        if local_origen_id == local_destino_id:
            msg = 'La sede de origen y la sede de destino deben ser diferentes.'
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': msg}), 400
            flash(msg, 'danger')
            return redirect(url_for('traslados_bp.index'))

        if cantidad <= 0:
            msg = 'La cantidad a trasladar debe ser al menos 1.'
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': msg}), 400
            flash(msg, 'danger')
            return redirect(url_for('traslados_bp.index'))

        producto = Product.query.get_or_404(product_id)
        variante = ProductVariant.query.get(variant_id) if variant_id else None

        # 1. Validar y descontar stock del origen, sumar al destino
        if variante:
            stock_origen = variante.get_stock_local(str(local_origen_id))
            if stock_origen < cantidad:
                msg = f'La subcategoría "{variante.nombre_variante}" solo tiene {stock_origen} unidades en D&L {local_origen_id}.'
                if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'success': False, 'message': msg}), 400
                flash(msg, 'danger')
                return redirect(url_for('traslados_bp.index'))

            # Actualizar stock variante origen y destino
            setattr(variante, f'stock_local_{local_origen_id}', getattr(variante, f'stock_local_{local_origen_id}') - cantidad)
            setattr(variante, f'stock_local_{local_destino_id}', getattr(variante, f'stock_local_{local_destino_id}', 0) + cantidad)
        else:
            stock_origen = producto.get_stock_local(str(local_origen_id))
            if stock_origen < cantidad:
                msg = f'El producto "{producto.nombre}" solo tiene {stock_origen} unidades en D&L {local_origen_id}.'
                if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'success': False, 'message': msg}), 400
                flash(msg, 'danger')
                return redirect(url_for('traslados_bp.index'))

            # Actualizar stock producto origen y destino
            setattr(producto, f'stock_local_{local_origen_id}', getattr(producto, f'stock_local_{local_origen_id}') - cantidad)
            setattr(producto, f'stock_local_{local_destino_id}', getattr(producto, f'stock_local_{local_destino_id}', 0) + cantidad)

        # 2. Registrar la transferencia en la base de datos
        nuevo_traslado = StockTransfer(
            product_id=product_id,
            variant_id=variant_id,
            local_origen_id=local_origen_id,
            local_destino_id=local_destino_id,
            cantidad=cantidad,
            usuario_id=current_user.id,
            asesor_id=asesor_id,
            observacion=observacion if observacion else 'Traslado realizado desde Caja POS',
            fecha_transferencia=obtener_hora_bogota()
        )
        db.session.add(nuevo_traslado)
        db.session.commit()

        msg = f'¡Traslado exitoso! {cantidad} unidad(es) movida(s) de D&L {local_origen_id} a D&L {local_destino_id}.'

        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': True,
                'message': msg,
                'traslado_id': nuevo_traslado.id,
                'producto_nombre': producto.nombre,
                'variante_nombre': variante.nombre_variante if variante else None
            })

        flash(msg, 'success')
        return redirect(url_for('traslados_bp.index'))

    except Exception as e:
        db.session.rollback()
        msg = f'Error al procesar el traslado: {str(e)}'
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': msg}), 500
        flash(msg, 'danger')
        return redirect(url_for('traslados_bp.index'))

@traslados_bp.route('/<int:id>/eliminar', methods=['POST'])
@login_required
@admin_required
def eliminar(id):
    traslado = StockTransfer.query.get_or_404(id)

    # Validar si el traslado fue facturado
    if traslado.es_facturado or traslado.sale_id:
        flash('No es posible eliminar este traslado porque ya fue facturado en una venta real.', 'danger')
        return redirect(url_for('traslados_bp.index'))

    try:
        # Revertir stock: Devolver la cantidad a la sede de origen y restar a la sede de destino
        if traslado.variante:
            setattr(traslado.variante, f'stock_local_{traslado.local_origen_id}', getattr(traslado.variante, f'stock_local_{traslado.local_origen_id}') + traslado.cantidad)
            setattr(traslado.variante, f'stock_local_{traslado.local_destino_id}', getattr(traslado.variante, f'stock_local_{traslado.local_destino_id}', 0) - traslado.cantidad)
            traslado.variante.cantidad_stock = traslado.variante.total_stock
            if traslado.producto:
                traslado.producto.cantidad_stock = traslado.producto.total_stock
        elif traslado.producto:
            setattr(traslado.producto, f'stock_local_{traslado.local_origen_id}', getattr(traslado.producto, f'stock_local_{traslado.local_origen_id}') + traslado.cantidad)
            setattr(traslado.producto, f'stock_local_{traslado.local_destino_id}', getattr(traslado.producto, f'stock_local_{traslado.local_destino_id}', 0) - traslado.cantidad)
            traslado.producto.cantidad_stock = traslado.producto.total_stock

        db.session.delete(traslado)
        db.session.commit()
        flash(f'Traslado #{id} eliminado exitosamente. El stock ({traslado.cantidad} uds) fue devuelto a D&L {traslado.local_origen_id}.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al intentar eliminar el traslado: {str(e)}', 'danger')

    return redirect(url_for('traslados_bp.index'))
