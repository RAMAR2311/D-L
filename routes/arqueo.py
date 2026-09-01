from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, Sale, SalePayment, ArqueoCaja, Expense, User, PuntoTransaction
from decorators import admin_required
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import or_
import pytz

arqueo_bp = Blueprint('arqueo_bp', __name__)

def obtener_hora_bogota():
    return datetime.now(pytz.timezone('America/Bogota')).replace(tzinfo=None)

def calcular_totales_dia(ventas_del_dia):
    """Calcula los totales de efectivo, transferencias y desglose digital del día."""
    desglose = {
        'efectivo': Decimal('0.00'),
        'nequi': Decimal('0.00'),
        'bancolombia': Decimal('0.00'),
        'daviplata': Decimal('0.00'),
        'bold': Decimal('0.00'),
        'addi': Decimal('0.00'),
        'transferencia': Decimal('0.00'),
        'total_digital': Decimal('0.00')
    }
    
    for v in ventas_del_dia:
        if v.pagos:  # Ventas nuevas con tabla sale_payments
            for pago in v.pagos:
                metodo = (pago.metodo_pago or 'efectivo').lower()
                monto = Decimal(str(pago.monto))
                if metodo in desglose:
                    desglose[metodo] += monto
                else:
                    desglose['transferencia'] += monto
                if metodo != 'efectivo':
                    desglose['total_digital'] += monto
        else:  # Retrocompatibilidad con ventas antiguas
            metodo = (v.metodo_pago or 'efectivo').lower()
            monto = Decimal(str(v.monto_total))
            if metodo in desglose:
                desglose[metodo] += monto
            else:
                desglose['transferencia'] += monto
            if metodo != 'efectivo':
                desglose['total_digital'] += monto
    
    return desglose['efectivo'], desglose['total_digital'], desglose

@arqueo_bp.route('/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo():
    is_admin = (current_user.rol == 'admin')
    if is_admin:
        active_local = request.args.get('local', '1').lower()
        if active_local not in ['1', '2', '3']:
            active_local = '1'
        local_id_num = int(active_local)
    else:
        local_id_num = current_user.local_asignado or 1
        active_local = str(local_id_num)

    local_nombres = {
        '1': 'D&L 1',
        '2': 'D&L 2',
        '3': 'D&L 3'
    }
    nombre_sede = local_nombres.get(active_local, f'Local {active_local}')

    # Obtener fecha de la URL o usar hoy
    fecha_str = request.args.get('fecha', obtener_hora_bogota().strftime('%Y-%m-%d'))
    try:
        fecha_seleccionada = datetime.strptime(fecha_str, '%Y-%m-%d').date()
    except ValueError:
        fecha_seleccionada = obtener_hora_bogota().date()
        fecha_str = fecha_seleccionada.strftime('%Y-%m-%d')

    # Calcular ventas del día exclusivamente para el local seleccionado
    ventas_del_dia = Sale.query.filter(
        db.func.date(Sale.fecha_venta) == fecha_seleccionada,
        Sale.local_id == local_id_num
    ).order_by(Sale.fecha_venta.desc()).all()

    total_efectivo, total_transferencia, desglose_digital = calcular_totales_dia(ventas_del_dia)

    # Calcular gastos automáticos del día exclusivamente para el local seleccionado
    gastos_diarios_registros = Expense.query.filter(
        db.func.date(Expense.fecha_gasto) == fecha_seleccionada,
        Expense.tipo_gasto == 'Gasto Diario',
        Expense.local_id == local_id_num
    ).all()
    gastos_automaticos = sum((Decimal(str(g.monto)) for g in gastos_diarios_registros), Decimal('0.00'))

    # Desglose de gastos por categoría
    desglose_gastos_cat = {}
    for g in gastos_diarios_registros:
        cat = (g.categoria or 'General').strip()
        desglose_gastos_cat[cat] = desglose_gastos_cat.get(cat, Decimal('0.00')) + Decimal(str(g.monto))

    # Verificar si ya existe un arqueo para esa fecha y ese local
    arqueo_existente = ArqueoCaja.query.filter_by(fecha_arqueo=fecha_seleccionada, local_id=local_id_num).first()

    if request.method == 'POST':
        if ArqueoCaja.query.filter_by(fecha_arqueo=fecha_seleccionada, local_id=local_id_num).first():
            flash(f'Ya existe un arqueo cerrado para {nombre_sede} en esta fecha.', 'warning')
            return redirect(url_for('arqueo_bp.reporte', fecha_inicio=fecha_str, fecha_fin=fecha_str, local=active_local))

        base_inicial = float(request.form.get('base_inicial', 0.0))
        observaciones_gastos = request.form.get('observaciones_gastos', '').strip()

        nuevo_arqueo = ArqueoCaja(
            vendedor_id=current_user.id,
            local_id=local_id_num,
            fecha_arqueo=fecha_seleccionada,
            base_inicial=base_inicial,
            gastos_del_dia=gastos_automaticos,
            observaciones_gastos=observaciones_gastos,
            total_efectivo_sistema=total_efectivo,
            total_transferencia_sistema=total_transferencia,
            total_unidades_ch=0.0
        )

        try:
            db.session.add(nuevo_arqueo)
            db.session.commit()
            flash(f'¡Arqueo de caja para {nombre_sede} guardado y cerrado exitosamente!', 'success')
            return redirect(url_for('arqueo_bp.reporte', fecha_inicio=fecha_str, fecha_fin=fecha_str, local=active_local))
        except Exception as e:
            db.session.rollback()
            flash('Ocurrió un error al guardar el arqueo de caja.', 'danger')

    # Calcular abonos a Puntos realizados en el día exclusivamente para el local seleccionado
    abonos_puntos_registros = PuntoTransaction.query.filter(
        db.func.date(PuntoTransaction.fecha) == fecha_seleccionada,
        PuntoTransaction.tipo_movimiento == 'abono',
        PuntoTransaction.local_id == local_id_num
    ).order_by(PuntoTransaction.fecha.desc()).all()
    total_abonos_puntos = sum((Decimal(str(a.monto)) for a in abonos_puntos_registros), Decimal('0.00'))

    return render_template(
        'arqueo/form.html',
        fecha=fecha_str,
        total_efectivo=total_efectivo,
        total_transferencia=total_transferencia,
        ventas_del_dia=ventas_del_dia,
        arqueo_existente=arqueo_existente,
        gastos_automaticos=gastos_automaticos,
        gastos_diarios_registros=gastos_diarios_registros,
        desglose_gastos_cat=desglose_gastos_cat,
        abonos_puntos_registros=abonos_puntos_registros,
        total_abonos_puntos=total_abonos_puntos,
        desglose_digital=desglose_digital,
        active_local=active_local,
        is_admin=is_admin,
        nombre_sede=nombre_sede
    )

@arqueo_bp.route('/reporte', methods=['GET'])
@login_required
def reporte():
    is_admin = (current_user.rol == 'admin')
    if is_admin:
        active_local = request.args.get('local', 'central').lower()
        if active_local not in ['central', '1', '2', '3']:
            active_local = 'central'
    else:
        active_local = str(current_user.local_asignado or '1')

    local_nombres = {
        'central': 'D&L CENTRAL',
        '1': 'D&L 1',
        '2': 'D&L 2',
        '3': 'D&L 3'
    }
    nombre_sede = local_nombres.get(active_local, 'D&L CENTRAL')

    fecha_inicio_str = request.args.get('fecha_inicio', obtener_hora_bogota().strftime('%Y-%m-%d'))
    fecha_fin_str = request.args.get('fecha_fin', obtener_hora_bogota().strftime('%Y-%m-%d'))

    try:
        fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date()
        fecha_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d').date()
    except ValueError:
        fecha_inicio = obtener_hora_bogota().date()
        fecha_fin = obtener_hora_bogota().date()

    if not is_admin:
        hoy = obtener_hora_bogota().date()
        fecha_inicio = hoy
        fecha_fin = hoy
        fecha_inicio_str = hoy.strftime('%Y-%m-%d')
        fecha_fin_str = hoy.strftime('%Y-%m-%d')

    query = ArqueoCaja.query.filter(
        ArqueoCaja.fecha_arqueo >= fecha_inicio,
        ArqueoCaja.fecha_arqueo <= fecha_fin
    )
    if active_local != 'central':
        local_num = int(active_local)
        query = query.filter(ArqueoCaja.local_id == local_num)

    arqueos = query.order_by(ArqueoCaja.fecha_arqueo.desc()).all()

    resumen = {
        'total_base': sum(a.base_inicial for a in arqueos),
        'total_efectivo': sum(a.total_efectivo_sistema for a in arqueos),
        'total_transferencia': sum(a.total_transferencia_sistema for a in arqueos),
        'total_gastos': sum(a.gastos_del_dia for a in arqueos)
    }

    resumen['total_recaudado_bruto'] = resumen['total_efectivo'] + resumen['total_transferencia']
    resumen['total_recaudado_neto'] = resumen['total_recaudado_bruto'] - resumen['total_gastos']

    gastos_efectivo_query = Expense.query.filter(
        db.func.date(Expense.fecha_gasto) >= fecha_inicio,
        db.func.date(Expense.fecha_gasto) <= fecha_fin,
        Expense.tipo_gasto == 'Gasto Diario',
        Expense.metodo_pago == 'efectivo'
    )
    if active_local != 'central':
        local_num = int(active_local)
        gastos_efectivo_query = gastos_efectivo_query.filter(Expense.local_id == local_num)
    resumen['total_gastos_efectivo'] = sum(g.monto for g in gastos_efectivo_query.all())
    resumen['efectivo_esperado'] = (resumen['total_base'] + resumen['total_efectivo']) - resumen['total_gastos_efectivo']

    ventas_query = Sale.query.filter(
        db.func.date(Sale.fecha_venta) >= fecha_inicio,
        db.func.date(Sale.fecha_venta) <= fecha_fin
    )
    if active_local != 'central':
        ventas_query = ventas_query.filter(Sale.local_id == int(active_local))

    ventas_periodo = ventas_query.order_by(Sale.fecha_venta.asc()).all()

    gastos_query_periodo = Expense.query.filter(
        db.func.date(Expense.fecha_gasto) >= fecha_inicio,
        db.func.date(Expense.fecha_gasto) <= fecha_fin
    )
    if active_local != 'central':
        local_num = int(active_local)
        gastos_query_periodo = gastos_query_periodo.filter(Expense.local_id == local_num)
    gastos_periodo = gastos_query_periodo.order_by(Expense.fecha_gasto.asc()).all()

    desglose_gastos_cat = {}
    for g in gastos_periodo:
        cat = (g.categoria or 'General').strip()
        desglose_gastos_cat[cat] = desglose_gastos_cat.get(cat, Decimal('0.00')) + Decimal(str(g.monto))

    fecha_generacion = obtener_hora_bogota().strftime('%Y-%m-%d %H:%M')

    return render_template(
        'arqueo/reporte.html',
        arqueos=arqueos,
        resumen=resumen,
        fecha_inicio=fecha_inicio_str,
        fecha_fin=fecha_fin_str,
        fecha_generacion=fecha_generacion,
        ventas_periodo=ventas_periodo,
        gastos_periodo=gastos_periodo,
        desglose_gastos_cat=desglose_gastos_cat,
        active_local=active_local,
        is_admin=is_admin,
        nombre_sede=nombre_sede
    )

@arqueo_bp.route('/eliminar/<int:id>', methods=['POST'])
@login_required
@admin_required
def eliminar(id):
    arqueo = ArqueoCaja.query.get_or_404(id)
    fecha_str = arqueo.fecha_arqueo.strftime('%Y-%m-%d')
    local_id_str = str(arqueo.local_id)
    try:
        db.session.delete(arqueo)
        db.session.commit()
        flash('Cierre de caja anulado exitosamente. La caja ha sido reabierta para edición.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Ocurrió un error al anular el cierre de caja.', 'danger')
        
    return redirect(url_for('arqueo_bp.nuevo', fecha=fecha_str, local=local_id_str))
