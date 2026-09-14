from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, Punto, PuntoTransaction, Expense, obtener_hora_bogota
from decimal import Decimal
from datetime import datetime

puntos_bp = Blueprint('puntos_bp', __name__, url_prefix='/puntos')

@puntos_bp.route('/', methods=['GET'])
@login_required
def index():
    puntos_list = Punto.query.order_by(Punto.nombre.asc()).all()

    total_deuda_global = Decimal('0.00')
    total_cargos_global = Decimal('0.00')
    total_abonos_global = Decimal('0.00')

    datos_puntos = []
    for p in puntos_list:
        cargos = sum((t.monto for t in p.transacciones if t.tipo_movimiento == 'cargo'), Decimal('0.00'))
        abonos = sum((t.monto for t in p.transacciones if t.tipo_movimiento == 'abono'), Decimal('0.00'))
        saldo = cargos - abonos

        total_cargos_global += cargos
        total_abonos_global += abonos
        total_deuda_global += max(saldo, Decimal('0.00'))

        datos_puntos.append({
            'punto': p,
            'total_cargos': cargos,
            'total_abonos': abonos,
            'saldo_pendiente': saldo
        })

    return render_template(
        'puntos/list.html',
        puntos=datos_puntos,
        total_puntos=len(puntos_list),
        total_deuda_global=total_deuda_global,
        total_cargos_global=total_cargos_global,
        total_abonos_global=total_abonos_global
    )

@puntos_bp.route('/crear', methods=['POST'])
@login_required
def crear():
    nombre = request.form.get('nombre', '').strip()
    telefono = request.form.get('telefono', '').strip()
    direccion = request.form.get('direccion', '').strip()
    observaciones = request.form.get('observaciones', '').strip()

    if not nombre:
        flash('El nombre del local (Punto) es obligatorio.', 'danger')
        return redirect(url_for('puntos_bp.index'))

    existente = Punto.query.filter_by(nombre=nombre).first()
    if existente:
        flash(f'Ya existe un Punto registrado con el nombre "{nombre}".', 'warning')
        return redirect(url_for('puntos_bp.index'))

    try:
        nuevo_punto = Punto(
            nombre=nombre,
            telefono=telefono if telefono else None,
            direccion=direccion if direccion else None,
            observaciones=observaciones if observaciones else None
        )
        db.session.add(nuevo_punto)
        db.session.commit()
        flash(f'Punto "{nombre}" registrado exitosamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error al intentar guardar el nuevo Punto.', 'danger')

    return redirect(url_for('puntos_bp.index'))

@puntos_bp.route('/<int:id>', methods=['GET'])
@login_required
def detalle(id):
    punto = Punto.query.get_or_404(id)

    transacciones = PuntoTransaction.query.filter_by(punto_id=punto.id).order_by(PuntoTransaction.fecha.desc()).all()

    cargos = sum((t.monto for t in transacciones if t.tipo_movimiento == 'cargo'), Decimal('0.00'))
    abonos = sum((t.monto for t in transacciones if t.tipo_movimiento == 'abono'), Decimal('0.00'))
    saldo_pendiente = cargos - abonos

    # Desglose de Abonos por Sede
    abonos_l1 = sum((t.monto for t in transacciones if t.tipo_movimiento == 'abono' and (t.local_id or 1) == 1), Decimal('0.00'))
    abonos_l2 = sum((t.monto for t in transacciones if t.tipo_movimiento == 'abono' and (t.local_id or 1) == 2), Decimal('0.00'))
    abonos_l3 = sum((t.monto for t in transacciones if t.tipo_movimiento == 'abono' and (t.local_id or 1) == 3), Decimal('0.00'))
    count_abonos_l1 = sum(1 for t in transacciones if t.tipo_movimiento == 'abono' and (t.local_id or 1) == 1)
    count_abonos_l2 = sum(1 for t in transacciones if t.tipo_movimiento == 'abono' and (t.local_id or 1) == 2)
    count_abonos_l3 = sum(1 for t in transacciones if t.tipo_movimiento == 'abono' and (t.local_id or 1) == 3)

    # Desglose de Cargos / Nuevos Saldos por Sede
    cargos_l1 = sum((t.monto for t in transacciones if t.tipo_movimiento == 'cargo' and (t.local_id or 1) == 1), Decimal('0.00'))
    cargos_l2 = sum((t.monto for t in transacciones if t.tipo_movimiento == 'cargo' and (t.local_id or 1) == 2), Decimal('0.00'))
    cargos_l3 = sum((t.monto for t in transacciones if t.tipo_movimiento == 'cargo' and (t.local_id or 1) == 3), Decimal('0.00'))
    count_cargos_l1 = sum(1 for t in transacciones if t.tipo_movimiento == 'cargo' and (t.local_id or 1) == 1)
    count_cargos_l2 = sum(1 for t in transacciones if t.tipo_movimiento == 'cargo' and (t.local_id or 1) == 2)
    count_cargos_l3 = sum(1 for t in transacciones if t.tipo_movimiento == 'cargo' and (t.local_id or 1) == 3)

    # Desglose de Abonos por Método de Pago
    abonos_por_metodo = {}
    abonos_lista = [t for t in transacciones if t.tipo_movimiento == 'abono']
    for a in abonos_lista:
        met = (a.metodo_pago or 'efectivo').lower().strip()
        abonos_por_metodo[met] = abonos_por_metodo.get(met, Decimal('0.00')) + a.monto

    # Calcular saldo individual por producto / sale_id
    abonos_por_sale_id = {}
    for a in abonos_lista:
        if a.sale_id:
            abonos_por_sale_id[a.sale_id] = abonos_por_sale_id.get(a.sale_id, Decimal('0.00')) + a.monto

    productos_cartera = []
    cargos_registros = [t for t in transacciones if t.tipo_movimiento == 'cargo']
    for c in cargos_registros:
        s_id = c.sale_id or c.id
        tot_abono = abonos_por_sale_id.get(s_id, Decimal('0.00'))
        if not c.sale_id and c.id in abonos_por_sale_id:
            tot_abono += abonos_por_sale_id[c.id]
        
        saldo_prod = max(c.monto - tot_abono, Decimal('0.00'))
        porcentaje_pagado = int((tot_abono / c.monto * 100) if c.monto > 0 else 100)
        c.total_abonado = tot_abono
        c.saldo_pendiente = saldo_prod
        c.porcentaje_pagado = min(porcentaje_pagado, 100)

        productos_cartera.append({
            'cargo_id': c.id,
            'sale_id': s_id,
            'descripcion': c.descripcion or f'Venta #{s_id}',
            'monto_cargo': c.monto,
            'total_abonado': tot_abono,
            'saldo_pendiente': saldo_prod,
            'porcentaje_pagado': c.porcentaje_pagado,
            'fecha': c.fecha,
            'local_id': c.local_id or 1,
            'usuario': c.usuario.nombre if c.usuario else 'Sistema',
            'pagado_completo': (saldo_prod <= Decimal('0.00'))
        })

    # Inyectar variables de saldo de producto en las transacciones para la tabla principal
    for t in transacciones:
        if t.tipo_movimiento == 'cargo':
            s_id = t.sale_id or t.id
            tot_ab = abonos_por_sale_id.get(s_id, Decimal('0.00'))
            t.total_abonado_producto = tot_ab
            t.saldo_pendiente_producto = max(t.monto - tot_ab, Decimal('0.00'))
        elif t.tipo_movimiento == 'abono' and t.sale_id:
            cargo_asoc = next((c for c in cargos_registros if (c.sale_id == t.sale_id or c.id == t.sale_id)), None)
            if cargo_asoc:
                tot_ab = abonos_por_sale_id.get(t.sale_id, Decimal('0.00'))
                t.saldo_pendiente_producto = max(cargo_asoc.monto - tot_ab, Decimal('0.00'))
                t.monto_cargo_producto = cargo_asoc.monto
                t.cargo_asociado_desc = cargo_asoc.descripcion
            else:
                t.saldo_pendiente_producto = None
                t.monto_cargo_producto = None
                t.cargo_asociado_desc = None
        else:
            t.saldo_pendiente_producto = None
            t.monto_cargo_producto = None
            t.cargo_asociado_desc = None

    items_pendientes = [p for p in productos_cartera if p['saldo_pendiente'] > Decimal('0.00')]
    deuda_l1 = sum((p['saldo_pendiente'] for p in items_pendientes if (p['local_id'] or 1) == 1), Decimal('0.00'))
    deuda_l2 = sum((p['saldo_pendiente'] for p in items_pendientes if (p['local_id'] or 1) == 2), Decimal('0.00'))
    deuda_l3 = sum((p['saldo_pendiente'] for p in items_pendientes if (p['local_id'] or 1) == 3), Decimal('0.00'))

    hoy_str = obtener_hora_bogota().strftime('%Y-%m-%d')

    return render_template(
        'puntos/detail.html',
        punto=punto,
        transacciones=transacciones,
        productos_cartera=productos_cartera,
        cargos_registros=cargos_registros,
        abonos_lista=abonos_lista,
        items_pendientes=items_pendientes,
        total_cargos=cargos,
        total_abonos=abonos,
        saldo_pendiente=saldo_pendiente,
        abonos_l1=abonos_l1,
        abonos_l2=abonos_l2,
        abonos_l3=abonos_l3,
        count_abonos_l1=count_abonos_l1,
        count_abonos_l2=count_abonos_l2,
        count_abonos_l3=count_abonos_l3,
        cargos_l1=cargos_l1,
        cargos_l2=cargos_l2,
        cargos_l3=cargos_l3,
        count_cargos_l1=count_cargos_l1,
        count_cargos_l2=count_cargos_l2,
        count_cargos_l3=count_cargos_l3,
        deuda_l1=deuda_l1,
        deuda_l2=deuda_l2,
        deuda_l3=deuda_l3,
        abonos_por_metodo=abonos_por_metodo,
        hoy=hoy_str
    )

@puntos_bp.route('/<int:id>/abonar', methods=['POST'])
@login_required
def abonar(id):
    punto = Punto.query.get_or_404(id)

    # Validar que el punto tenga saldo pendiente mayor a 0
    transacciones_existentes = PuntoTransaction.query.filter_by(punto_id=punto.id).all()
    cargos = sum((t.monto for t in transacciones_existentes if t.tipo_movimiento == 'cargo'), Decimal('0.00'))
    abonos = sum((t.monto for t in transacciones_existentes if t.tipo_movimiento == 'abono'), Decimal('0.00'))
    saldo_pendiente = cargos - abonos

    if saldo_pendiente <= 0:
        flash(f'El punto "{punto.nombre}" ya se encuentra al día ($0 saldo pendiente). No es posible registrar abonos.', 'warning')
        return redirect(url_for('puntos_bp.detalle', id=punto.id))

    try:
        monto = Decimal(str(request.form.get('monto', '0')).replace(',', '').strip())
    except (ValueError, TypeError):
        monto = Decimal('0.00')

    metodo_pago = request.form.get('metodo_pago', 'efectivo')
    descripcion = request.form.get('descripcion', '').strip()
    sale_id_raw = request.form.get('sale_id')
    sale_id = int(sale_id_raw) if sale_id_raw and sale_id_raw.isdigit() else None

    try:
        local_id_abono = int(request.form.get('local_id', 1))
    except (ValueError, TypeError):
        local_id_abono = getattr(current_user, 'local_asignado', 1) or 1

    # Obtener la fecha del abono elegida por el usuario
    fecha_abono_str = request.form.get('fecha_abono')
    if fecha_abono_str:
        try:
            hora_actual = obtener_hora_bogota().time()
            fecha_dt = datetime.strptime(fecha_abono_str, '%Y-%m-%d').replace(
                hour=hora_actual.hour, minute=hora_actual.minute, second=hora_actual.second
            )
        except ValueError:
            fecha_dt = obtener_hora_bogota()
    else:
        fecha_dt = obtener_hora_bogota()

    # Validar que el monto sea mayor a 0
    if monto <= 0:
        flash('El monto del abono debe ser mayor a 0.', 'danger')
        return redirect(url_for('puntos_bp.detalle', id=punto.id))

    # Validar que el abono no exceda la deuda global pendiente
    if monto > saldo_pendiente:
        flash(f'El monto del abono (${monto:,.0f}) excede el saldo pendiente total del punto (${saldo_pendiente:,.0f}).', 'warning')
        return redirect(url_for('puntos_bp.detalle', id=punto.id))

    # Validación estricta a nivel de producto / venta específica si se seleccionó uno
    if sale_id:
        cargo_ref = next((t for t in transacciones_existentes if t.tipo_movimiento == 'cargo' and (t.sale_id == sale_id or (not t.sale_id and t.id == sale_id))), None)
        if not cargo_ref:
            flash('No se encontró el cargo o producto seleccionado para este punto.', 'danger')
            return redirect(url_for('puntos_bp.detalle', id=punto.id))

        cargos_producto = sum(
            (t.monto for t in transacciones_existentes if t.tipo_movimiento == 'cargo' and (t.sale_id == sale_id or (not t.sale_id and t.id == sale_id))),
            Decimal('0.00')
        )
        abonos_producto = sum(
            (t.monto for t in transacciones_existentes if t.tipo_movimiento == 'abono' and t.sale_id == sale_id),
            Decimal('0.00')
        )
        saldo_pendiente_prod = max(cargos_producto - abonos_producto, Decimal('0.00'))

        # Si el producto ya quedó en 0, BLOQUEAR abonos adicionales
        if saldo_pendiente_prod <= Decimal('0.00'):
            flash(f'El producto/ítem "{cargo_ref.descripcion or f"Venta #{sale_id}"}" ya se encuentra completamente pagado ($0 saldo pendiente). No es posible realizar más abonos a este producto.', 'warning')
            return redirect(url_for('puntos_bp.detalle', id=punto.id))

        # Si el monto ingresado supera lo que falta por pagar de ese producto, BLOQUEAR
        if monto > saldo_pendiente_prod:
            flash(f'El monto a abonar (${monto:,.0f}) excede el saldo pendiente de este producto (${saldo_pendiente_prod:,.0f}). El abono máximo permitido es de ${saldo_pendiente_prod:,.0f}.', 'warning')
            return redirect(url_for('puntos_bp.detalle', id=punto.id))

        # Asignar descripción automática si no se suministró una
        if not descripcion:
            if cargo_ref.descripcion:
                descripcion = f"Abono a {cargo_ref.descripcion}"
            else:
                descripcion = f"Abono específico a Venta #{sale_id}"

    try:
        # 1. Crear transacción de Abono al Punto con local_id, sale_id y fecha personalizada
        transaccion_abono = PuntoTransaction(
            punto_id=punto.id,
            usuario_id=current_user.id,
            tipo_movimiento='abono',
            monto=monto,
            metodo_pago=metodo_pago,
            local_id=local_id_abono,
            sale_id=sale_id,
            descripcion=descripcion if descripcion else f'Abono a {punto.nombre} desde D&L {local_id_abono}',
            fecha=fecha_dt
        )
        db.session.add(transaccion_abono)

        # 2. Registrar el desembolso como Gasto Diario para cuadrar caja en la sede pagadora
        nuevo_gasto = Expense(
            usuario_id=current_user.id,
            tipo_gasto='Gasto Diario',
            categoria='Abono a Punto/Local',
            descripcion=f"Abono a Punto {punto.nombre}" + (f" ({descripcion})" if descripcion else ""),
            monto=monto,
            metodo_pago=metodo_pago,
            local_id=local_id_abono,
            fecha_gasto=fecha_dt
        )
        db.session.add(nuevo_gasto)

        db.session.commit()
        flash(f'Abono de ${monto:,.0f} registrado exitosamente con fecha {fecha_dt.strftime("%d/%m/%Y")} a favor de "{punto.nombre}".', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error al intentar registrar el abono.', 'danger')

    return redirect(url_for('puntos_bp.detalle', id=punto.id))

@puntos_bp.route('/api/lista', methods=['GET'])
@login_required
def api_lista_puntos():
    puntos_list = Punto.query.order_by(Punto.nombre.asc()).all()
    data = [{'id': p.id, 'nombre': p.nombre} for p in puntos_list]
    return jsonify(data)

@puntos_bp.route('/<int:id>/eliminar', methods=['POST'])
@login_required
def eliminar_punto(id):
    punto = Punto.query.get_or_404(id)
    try:
        # Eliminar las transacciones asociadas primero para evitar problemas de FK si no hay cascade
        transacciones = PuntoTransaction.query.filter_by(punto_id=punto.id).all()
        for t in transacciones:
            db.session.delete(t)
        
        db.session.delete(punto)
        db.session.commit()
        flash(f'Punto "{punto.nombre}" eliminado exitosamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error al intentar eliminar el Punto.', 'danger')
        
    return redirect(url_for('puntos_bp.index'))

@puntos_bp.route('/transaccion/<int:t_id>/eliminar', methods=['POST'])
@login_required
def eliminar_transaccion(t_id):
    transaccion = PuntoTransaction.query.get_or_404(t_id)
    punto_id = transaccion.punto_id
    try:
        # Si la transacción es un abono, eliminar también el Gasto Diario correspondiente en caja
        if transaccion.tipo_movimiento == 'abono':
            punto = Punto.query.get(punto_id)
            punto_nombre = punto.nombre if punto else ''
            prefijo_desc = f"Abono a Punto {punto_nombre}"
            gasto_asociado = Expense.query.filter(
                Expense.categoria == 'Abono a Punto/Local',
                Expense.local_id == transaccion.local_id,
                Expense.monto == transaccion.monto,
                Expense.descripcion.like(f"{prefijo_desc}%")
            ).filter(
                db.func.date(Expense.fecha_gasto) == db.func.date(transaccion.fecha)
            ).order_by(Expense.id.desc()).first()

            if gasto_asociado:
                db.session.delete(gasto_asociado)

        db.session.delete(transaccion)
        db.session.commit()
        flash('Transacción y su desembolso en caja eliminados exitosamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error al intentar eliminar la transacción.', 'danger')
        
    return redirect(url_for('puntos_bp.detalle', id=punto_id))

@puntos_bp.route('/<int:id>/agregar-cargo', methods=['POST'])
@login_required
def agregar_cargo(id):
    punto = Punto.query.get_or_404(id)

    try:
        monto = Decimal(str(request.form.get('monto', '0')).replace(',', '').strip())
    except (ValueError, TypeError):
        monto = Decimal('0.00')

    descripcion = request.form.get('descripcion', '').strip()
    try:
        local_id_cargo = int(request.form.get('local_id', 1))
    except (ValueError, TypeError):
        local_id_cargo = getattr(current_user, 'local_asignado', 1) or 1

    if monto <= 0:
        flash('El monto del nuevo saldo / cargo debe ser mayor a 0.', 'danger')
        return redirect(url_for('puntos_bp.detalle', id=punto.id))

    if not descripcion:
        descripcion = f"Nuevo cargo / saldo ingresado en D&L {local_id_cargo}"

    fecha_cargo_str = request.form.get('fecha_cargo')
    if fecha_cargo_str:
        try:
            hora_actual = obtener_hora_bogota().time()
            fecha_dt = datetime.strptime(fecha_cargo_str, '%Y-%m-%d').replace(
                hour=hora_actual.hour, minute=hora_actual.minute, second=hora_actual.second
            )
        except ValueError:
            fecha_dt = obtener_hora_bogota()
    else:
        fecha_dt = obtener_hora_bogota()

    try:
        transaccion_cargo = PuntoTransaction(
            punto_id=punto.id,
            usuario_id=current_user.id,
            tipo_movimiento='cargo',
            monto=monto,
            local_id=local_id_cargo,
            descripcion=descripcion,
            fecha=fecha_dt
        )
        db.session.add(transaccion_cargo)
        db.session.commit()
        flash(f'Nuevo saldo/cargo de ${monto:,.0f} registrado exitosamente a favor de "{punto.nombre}".', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error al intentar registrar el nuevo cargo.', 'danger')

    return redirect(url_for('puntos_bp.detalle', id=punto.id, ver='cargos'))

@puntos_bp.route('/transaccion/<int:t_id>/editar', methods=['POST'])
@login_required
def editar_transaccion(t_id):
    transaccion = PuntoTransaction.query.get_or_404(t_id)
    punto_id = transaccion.punto_id
    
    descripcion = request.form.get('descripcion', '').strip()
    metodo_pago = request.form.get('metodo_pago', 'efectivo')
    
    monto_str = request.form.get('monto')
    if monto_str:
        try:
            transaccion.monto = Decimal(monto_str.replace(',', '').strip())
        except:
            pass

    local_id_str = request.form.get('local_id')
    if local_id_str:
        try:
            transaccion.local_id = int(local_id_str)
        except:
            pass

    fecha_str = request.form.get('fecha')
    if fecha_str:
        try:
            transaccion.fecha = datetime.strptime(fecha_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            try:
                transaccion.fecha = datetime.strptime(fecha_str, '%Y-%m-%d')
            except ValueError:
                pass
            
    transaccion.descripcion = descripcion
    if transaccion.tipo_movimiento == 'abono':
        transaccion.metodo_pago = metodo_pago
        
    try:
        db.session.commit()
        flash('Transacción actualizada exitosamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error al intentar actualizar la transacción.', 'danger')
        
    return redirect(url_for('puntos_bp.detalle', id=punto_id))

