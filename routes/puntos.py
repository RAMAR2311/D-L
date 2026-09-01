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

    abonos_l1 = sum((t.monto for t in transacciones if t.tipo_movimiento == 'abono' and (t.local_id or 1) == 1), Decimal('0.00'))
    abonos_l2 = sum((t.monto for t in transacciones if t.tipo_movimiento == 'abono' and (t.local_id or 1) == 2), Decimal('0.00'))
    abonos_l3 = sum((t.monto for t in transacciones if t.tipo_movimiento == 'abono' and (t.local_id or 1) == 3), Decimal('0.00'))

    hoy_str = obtener_hora_bogota().strftime('%Y-%m-%d')

    return render_template(
        'puntos/detail.html',
        punto=punto,
        transacciones=transacciones,
        total_cargos=cargos,
        total_abonos=abonos,
        saldo_pendiente=saldo_pendiente,
        abonos_l1=abonos_l1,
        abonos_l2=abonos_l2,
        abonos_l3=abonos_l3,
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
    try:
        local_id_abono = int(request.form.get('local_id', 1))
    except (ValueError, TypeError):
        local_id_abono = getattr(current_user, 'local_asignado', 1) or 1

    if monto <= 0:
        flash('El monto del abono debe ser mayor a 0.', 'danger')
        return redirect(url_for('puntos_bp.detalle', id=punto.id))

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

    try:
        # 1. Crear transacción de Abono al Punto con local_id y fecha personalizada
        transaccion_abono = PuntoTransaction(
            punto_id=punto.id,
            usuario_id=current_user.id,
            tipo_movimiento='abono',
            monto=monto,
            metodo_pago=metodo_pago,
            local_id=local_id_abono,
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
        db.session.delete(transaccion)
        db.session.commit()
        flash('Transacción eliminada exitosamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error al intentar eliminar la transacción.', 'danger')
        
    return redirect(url_for('puntos_bp.detalle', id=punto_id))

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
