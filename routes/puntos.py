from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, Punto, PuntoTransaction, Expense, Asesor, obtener_hora_bogota
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

def calcular_cartera_punto(transacciones):
    """
    Calcula los saldos individuales de productos/cargos de un Punto.
    Aplica imputación contable inteligente:
    1. Aplica primero abonos específicos dirigidos a un producto (sale_id).
    2. Distribuye los abonos generales (sin sale_id) o excedentes de forma cronológica (FIFO)
       cubriendo los cargos más antiguos pendientes de pago.
    De este modo, la suma de los saldos pendientes de los productos coincide exactamente
    con la deuda pendiente total del cliente.
    """
    cargos_registros = [t for t in transacciones if t.tipo_movimiento == 'cargo']
    abonos_lista = [t for t in transacciones if t.tipo_movimiento == 'abono']

    cargos = sum((t.monto for t in cargos_registros), Decimal('0.00'))
    abonos = sum((t.monto for t in abonos_lista), Decimal('0.00'))
    saldo_pendiente = max(cargos - abonos, Decimal('0.00'))

    # Ordenar cronológicamente (antiguos primero) para imputación FIFO
    cargos_cronologicos = sorted(cargos_registros, key=lambda c: (c.fecha or datetime.min, c.id))

    # 1. Separar abonos específicos y generales
    # Cada abono específico (con sale_id) se asocia primero a su cargo correspondiente
    # Si una venta tiene múltiples cargos, cada abono se imputa a su cargo respectivo
    total_abonos_generales = Decimal('0.00')
    abonos_por_sale_id = {}

    for a in abonos_lista:
        if a.sale_id:
            abonos_por_sale_id.setdefault(a.sale_id, []).append(a)
        else:
            total_abonos_generales += a.monto

    # 2. Imputar abonos específicos a los cargos
    # Si un abono tiene en su descripción el ID del cargo o descripción del producto, se busca emparejar exactamente;
    # de lo contrario, se distribuye entre los cargos de esa venta sin duplicar cobertura.
    cargo_data = {}
    pool_general = total_abonos_generales

    # Mapear cargos agrupados por sale_id o id
    cargos_por_sale = {}
    for c in cargos_cronologicos:
        s_id = c.sale_id or c.id
        cargos_por_sale.setdefault(s_id, []).append(c)
        cargo_data[c.id] = {
            'monto': c.monto,
            'abono_especifico': Decimal('0.00'),
            'abono_general': Decimal('0.00'),
            'total_abonado': Decimal('0.00'),
            'saldo_pendiente': c.monto
        }

    for s_id, abonos_grupo in abonos_por_sale_id.items():
        cargos_grupo = cargos_por_sale.get(s_id, [])
        if not cargos_grupo:
            # Si no se encontró cargo con ese sale_id, enviar al pool general
            for a in abonos_grupo:
                pool_general += a.monto
            continue

        for a in abonos_grupo:
            monto_abono_restante = a.monto
            
            # Intentar emparejar primero por descripción del cargo si coincide con la descripción del abono
            cargo_match = None
            for c in cargos_grupo:
                if cargo_data[c.id]['saldo_pendiente'] > Decimal('0.00'):
                    desc_c = (c.descripcion or '').lower()
                    desc_a = (a.descripcion or '').lower()
                    if desc_c and (desc_c in desc_a or (c.descripcion and c.descripcion in a.descripcion)):
                        cargo_match = c
                        break

            if cargo_match:
                aplicar = min(cargo_data[cargo_match.id]['saldo_pendiente'], monto_abono_restante)
                cargo_data[cargo_match.id]['abono_especifico'] += aplicar
                cargo_data[cargo_match.id]['total_abonado'] += aplicar
                cargo_data[cargo_match.id]['saldo_pendiente'] -= aplicar
                monto_abono_restante -= aplicar

            # Si sobra monto del abono o no hubo match por texto, imputar a los cargos pendientes de esa venta (FIFO dentro de la venta)
            if monto_abono_restante > Decimal('0.00'):
                for c in cargos_grupo:
                    pend = cargo_data[c.id]['saldo_pendiente']
                    if pend > Decimal('0.00'):
                        aplicar = min(pend, monto_abono_restante)
                        cargo_data[c.id]['abono_especifico'] += aplicar
                        cargo_data[c.id]['total_abonado'] += aplicar
                        cargo_data[c.id]['saldo_pendiente'] -= aplicar
                        monto_abono_restante -= aplicar
                        if monto_abono_restante <= Decimal('0.00'):
                            break

            # Si aún sobra dinero de este abono específico, va al pool general
            if monto_abono_restante > Decimal('0.00'):
                pool_general += monto_abono_restante

    # 3. Aplicar pool general (FIFO) a los cargos pendientes más antiguos
    for c in cargos_cronologicos:
        info = cargo_data[c.id]
        if info['saldo_pendiente'] > Decimal('0.00') and pool_general > Decimal('0.00'):
            aplicar = min(info['saldo_pendiente'], pool_general)
            info['abono_general'] = aplicar
            info['total_abonado'] += aplicar
            info['saldo_pendiente'] -= aplicar
            pool_general -= aplicar

    # 4. Construir productos_cartera
    productos_cartera = []
    for c in cargos_registros:
        info = cargo_data.get(c.id, {
            'monto': c.monto,
            'total_abonado': Decimal('0.00'),
            'saldo_pendiente': c.monto
        })
        tot_abono = info['total_abonado']
        saldo_prod = info['saldo_pendiente']
        porcentaje_pagado = int((tot_abono / c.monto * 100) if c.monto > 0 else 100)

        c.total_abonado = tot_abono
        c.saldo_pendiente = saldo_prod
        c.porcentaje_pagado = min(porcentaje_pagado, 100)

        s_id = c.sale_id or c.id
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

    return {
        'cargos': cargos,
        'abonos': abonos,
        'saldo_pendiente': saldo_pendiente,
        'cargo_data': cargo_data,
        'productos_cartera': productos_cartera,
        'cargos_registros': cargos_registros,
        'abonos_lista': abonos_lista
    }

@puntos_bp.route('/<int:id>', methods=['GET'])
@login_required
def detalle(id):
    punto = Punto.query.get_or_404(id)

    transacciones = PuntoTransaction.query.filter_by(punto_id=punto.id).order_by(PuntoTransaction.fecha.desc()).all()

    cartera_info = calcular_cartera_punto(transacciones)
    cargos = cartera_info['cargos']
    abonos = cartera_info['abonos']
    saldo_pendiente = cartera_info['saldo_pendiente']
    productos_cartera = cartera_info['productos_cartera']
    cargos_registros = cartera_info['cargos_registros']
    abonos_lista = cartera_info['abonos_lista']
    cargo_data = cartera_info['cargo_data']

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
    for a in abonos_lista:
        met = (a.metodo_pago or 'efectivo').lower().strip()
        abonos_por_metodo[met] = abonos_por_metodo.get(met, Decimal('0.00')) + a.monto

    # Inyectar variables de saldo de producto en las transacciones para la tabla principal
    for t in transacciones:
        if t.tipo_movimiento == 'cargo':
            info = cargo_data.get(t.id)
            if info:
                t.total_abonado_producto = info['total_abonado']
                t.saldo_pendiente_producto = info['saldo_pendiente']
            else:
                t.total_abonado_producto = Decimal('0.00')
                t.saldo_pendiente_producto = t.monto
        elif t.tipo_movimiento == 'abono' and t.sale_id:
            cargo_asoc = next((c for c in cargos_registros if (c.sale_id == t.sale_id or c.id == t.sale_id)), None)
            if cargo_asoc:
                info = cargo_data.get(cargo_asoc.id)
                t.saldo_pendiente_producto = info['saldo_pendiente'] if info else Decimal('0.00')
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
    asesores = Asesor.query.filter_by(estado='Activo').order_by(Asesor.nombre.asc()).all()

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
        hoy=hoy_str,
        asesores=asesores
    )

@puntos_bp.route('/<int:id>/abonar', methods=['POST'])
@login_required
def abonar(id):
    punto = Punto.query.get_or_404(id)

    # Validar que el punto tenga saldo pendiente mayor a 0
    transacciones_existentes = PuntoTransaction.query.filter_by(punto_id=punto.id).all()
    cargos = sum((t.monto for t in transacciones_existentes if t.tipo_movimiento == 'cargo'), Decimal('0.00'))
    abonos = sum((t.monto for t in transacciones_existentes if t.tipo_movimiento == 'abono'), Decimal('0.00'))
    saldo_pendiente = max(cargos - abonos, Decimal('0.00'))

    if saldo_pendiente <= 0:
        flash(f'El punto "{punto.nombre}" ya se encuentra al día ($0 saldo pendiente). No es posible registrar abonos.', 'warning')
        return redirect(url_for('puntos_bp.detalle', id=punto.id))

    modo_pago = request.form.get('modo_pago', 'unico').strip().lower()
    descripcion = request.form.get('descripcion', '').strip()

    try:
        local_id_abono = int(request.form.get('local_id', 1))
    except (ValueError, TypeError):
        local_id_abono = getattr(current_user, 'local_asignado', 1) or 1

    # Fecha del abono elegida por el usuario
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

    # Validar asesor responsable obligatorio
    asesor_id_raw = request.form.get('asesor_id')
    if not asesor_id_raw or not asesor_id_raw.isdigit():
        flash('Debe seleccionar un Asesor Responsable obligatorio para registrar el abono.', 'danger')
        return redirect(url_for('puntos_bp.detalle', id=punto.id))
    asesor_id = int(asesor_id_raw)

    # Determinar métodos de pago y montos correspondientes
    metodos_posibles = ['efectivo', 'nequi', 'bancolombia', 'daviplata', 'bold', 'addi', 'qr_llave']
    pagos_desglose = []

    if modo_pago == 'dividido':
        for met in metodos_posibles:
            raw_val = request.form.get(f'monto_{met}', '0').replace(',', '').strip()
            try:
                amt = Decimal(raw_val)
            except Exception:
                amt = Decimal('0.00')
            if amt > Decimal('0.00'):
                pagos_desglose.append((met, amt))
        
        monto_total = sum((p[1] for p in pagos_desglose), Decimal('0.00'))
        if not pagos_desglose or monto_total <= Decimal('0.00'):
            flash('En modalidad dividida debes ingresar al menos un valor mayor a $0 en algún método de pago.', 'danger')
            return redirect(url_for('puntos_bp.detalle', id=punto.id))
    else:
        metodo_pago = request.form.get('metodo_pago', 'efectivo').strip().lower()
        if metodo_pago not in metodos_posibles:
            metodo_pago = 'efectivo'
        raw_val = request.form.get('monto', '0').replace(',', '').strip()
        try:
            monto_total = Decimal(raw_val)
        except Exception:
            monto_total = Decimal('0.00')

        if monto_total <= Decimal('0.00'):
            flash('El monto del abono debe ser mayor a 0.', 'danger')
            return redirect(url_for('puntos_bp.detalle', id=punto.id))
        pagos_desglose.append((metodo_pago, monto_total))

    # Validar que el abono no exceda la deuda global pendiente
    if monto_total > saldo_pendiente:
        flash(f'El monto del abono (${monto_total:,.0f}) excede el saldo pendiente total del punto (${saldo_pendiente:,.0f}).', 'warning')
        return redirect(url_for('puntos_bp.detalle', id=punto.id))

    # Determinar productos/cargos seleccionados
    tipo_aplicacion = request.form.get('tipo_aplicacion', 'general') # 'general' o 'especifico'
    cargo_ids_raw = request.form.getlist('cargo_ids') or request.form.getlist('cargo_ids[]')
    single_cargo_id = request.form.get('cargo_id')
    if single_cargo_id and single_cargo_id.isdigit():
        cargo_ids_raw.append(single_cargo_id)

    sale_ids_raw = request.form.getlist('sale_ids') or request.form.getlist('sale_ids[]')
    single_sale_id = request.form.get('sale_id')
    if single_sale_id and single_sale_id.isdigit():
        sale_ids_raw.append(single_sale_id)

    selected_cargo_ids = [int(c) for c in cargo_ids_raw if str(c).isdigit()]
    selected_sale_ids = [int(s) for s in sale_ids_raw if str(s).isdigit()]

    cartera_info = calcular_cartera_punto(transacciones_existentes)
    cargos_seleccionados = []

    if tipo_aplicacion == 'especifico':
        if selected_cargo_ids:
            for c_id in selected_cargo_ids:
                cargo_ref = next((t for t in transacciones_existentes if t.tipo_movimiento == 'cargo' and t.id == c_id), None)
                if cargo_ref:
                    info = cartera_info['cargo_data'].get(cargo_ref.id, {})
                    pend = info.get('saldo_pendiente', Decimal('0.00'))
                    if pend > Decimal('0.00'):
                        cargos_seleccionados.append({
                            'sale_id': cargo_ref.sale_id or cargo_ref.id,
                            'cargo_id': cargo_ref.id,
                            'descripcion': cargo_ref.descripcion or f'Venta #{cargo_ref.sale_id or cargo_ref.id}',
                            'saldo_pendiente': pend
                        })
        elif selected_sale_ids:
            for s_id in selected_sale_ids:
                cargos_de_venta = [t for t in transacciones_existentes if t.tipo_movimiento == 'cargo' and (t.sale_id == s_id or (not t.sale_id and t.id == s_id))]
                for cargo_ref in cargos_de_venta:
                    info = cartera_info['cargo_data'].get(cargo_ref.id, {})
                    pend = info.get('saldo_pendiente', Decimal('0.00'))
                    if pend > Decimal('0.00') and not any(cs['cargo_id'] == cargo_ref.id for cs in cargos_seleccionados):
                        cargos_seleccionados.append({
                            'sale_id': s_id,
                            'cargo_id': cargo_ref.id,
                            'descripcion': cargo_ref.descripcion or f'Venta #{s_id}',
                            'saldo_pendiente': pend
                        })

        if not cargos_seleccionados:
            flash('Los productos seleccionados ya se encuentran al día ($0 pendiente).', 'warning')
            return redirect(url_for('puntos_bp.detalle', id=punto.id))

        max_permitido = sum((c['saldo_pendiente'] for c in cargos_seleccionados), Decimal('0.00'))
        if monto_total > max_permitido:
            flash(f'El monto del abono (${monto_total:,.0f}) supera la deuda acumulada de los productos seleccionados (${max_permitido:,.0f}).', 'warning')
            return redirect(url_for('puntos_bp.detalle', id=punto.id))

    try:
        if cargos_seleccionados:
            # Distribuir monto_total entre los productos seleccionados
            asignaciones_prods = []
            monto_por_distribuir = monto_total
            for item in cargos_seleccionados:
                if monto_por_distribuir <= Decimal('0.00'):
                    break
                cuota = min(item['saldo_pendiente'], monto_por_distribuir)
                asignaciones_prods.append((item, cuota))
                monto_por_distribuir -= cuota

            # Emparejar con los métodos de pago empleados (waterfall matching)
            pagos_pool = [[m, amt] for m, amt in pagos_desglose]
            p_idx = 0

            for item, monto_item in asignaciones_prods:
                monto_item_restante = monto_item
                while monto_item_restante > Decimal('0.00') and p_idx < len(pagos_pool):
                    curr_met, curr_amt = pagos_pool[p_idx]
                    if curr_amt <= Decimal('0.00'):
                        p_idx += 1
                        continue
                    porcion = min(monto_item_restante, curr_amt)

                    desc_tx = descripcion if descripcion else f"Abono a {item['descripcion']} desde D&L {local_id_abono}"
                    tx = PuntoTransaction(
                        punto_id=punto.id,
                        usuario_id=current_user.id,
                        asesor_id=asesor_id,
                        tipo_movimiento='abono',
                        monto=porcion,
                        metodo_pago=curr_met,
                        local_id=local_id_abono,
                        sale_id=item['sale_id'],
                        descripcion=desc_tx,
                        fecha=fecha_dt
                    )
                    db.session.add(tx)

                    monto_item_restante -= porcion
                    pagos_pool[p_idx][1] -= porcion
                    if pagos_pool[p_idx][1] <= Decimal('0.00'):
                        p_idx += 1

            # Registrar Gastos Diarios correspondientes por cada método empleado
            for met, monto_met in pagos_desglose:
                desc_g = f"Abono a Punto {punto.nombre}"
                if len(cargos_seleccionados) == 1:
                    desc_g += f" - {cargos_seleccionados[0]['descripcion']}"
                else:
                    desc_g += f" ({len(cargos_seleccionados)} productos)"
                if descripcion:
                    desc_g += f" [{descripcion}]"

                gasto = Expense(
                    usuario_id=current_user.id,
                    tipo_gasto='Gasto Diario',
                    categoria='Abono a Punto/Local',
                    descripcion=desc_g,
                    monto=monto_met,
                    metodo_pago=met,
                    local_id=local_id_abono,
                    fecha_gasto=fecha_dt
                )
                db.session.add(gasto)

        else:
            # Abono General a la Deuda Global
            for met, monto_met in pagos_desglose:
                desc_tx = descripcion if descripcion else f"Abono general a {punto.nombre} desde D&L {local_id_abono}"
                tx = PuntoTransaction(
                    punto_id=punto.id,
                    usuario_id=current_user.id,
                    asesor_id=asesor_id,
                    tipo_movimiento='abono',
                    monto=monto_met,
                    metodo_pago=met,
                    local_id=local_id_abono,
                    sale_id=None,
                    descripcion=desc_tx,
                    fecha=fecha_dt
                )
                db.session.add(tx)

                gasto = Expense(
                    usuario_id=current_user.id,
                    tipo_gasto='Gasto Diario',
                    categoria='Abono a Punto/Local',
                    descripcion=f"Abono a Punto {punto.nombre}" + (f" ({descripcion})" if descripcion else ""),
                    monto=monto_met,
                    metodo_pago=met,
                    local_id=local_id_abono,
                    fecha_gasto=fecha_dt
                )
                db.session.add(gasto)

        db.session.commit()
        metodos_str = "Pago Dividido (" + ", ".join([f"{m.capitalize()}: ${a:,.0f}" for m, a in pagos_desglose]) + ")" if len(pagos_desglose) > 1 else pagos_desglose[0][0].capitalize()
        flash(f'Abono de ${monto_total:,.0f} registrado exitosamente ({metodos_str}) a favor de "{punto.nombre}".', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al registrar el abono: {str(e)}', 'danger')

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
    punto_nombre = punto.nombre
    try:
        # Eliminar las transacciones asociadas y sus gastos asociados en caja
        transacciones = PuntoTransaction.query.filter_by(punto_id=punto.id).all()
        for t in transacciones:
            if t.tipo_movimiento == 'abono':
                gasto = Expense.query.filter(
                    (Expense.categoria.ilike('%abono%')) | 
                    (Expense.categoria.ilike('%punto%')) | 
                    (Expense.descripcion.ilike(f"%{punto_nombre}%")),
                    Expense.monto == t.monto
                ).filter(
                    (Expense.local_id == t.local_id) | (Expense.local_id.is_(None))
                ).order_by(Expense.id.desc()).first()
                if gasto:
                    db.session.delete(gasto)
            db.session.delete(t)
        
        db.session.delete(punto)
        db.session.commit()
        flash(f'Punto "{punto.nombre}" y sus transacciones asociadas eliminados exitosamente.', 'success')
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
            punto_nombre = (punto.nombre if punto else '').strip()
            
            # Búsqueda robusta del gasto asociado
            query_gasto = Expense.query.filter(
                (Expense.categoria.ilike('%abono%')) | 
                (Expense.categoria.ilike('%punto%')) | 
                (Expense.descripcion.ilike(f"%{punto_nombre}%")) |
                (Expense.descripcion.ilike('%abono%')),
                Expense.monto == transaccion.monto
            )
            
            if transaccion.local_id:
                query_gasto = query_gasto.filter(
                    (Expense.local_id == transaccion.local_id) | (Expense.local_id.is_(None))
                )
            
            # Buscar primero por coincidencia de fecha
            gasto_asociado = query_gasto.filter(
                db.func.date(Expense.fecha_gasto) == db.func.date(transaccion.fecha)
            ).order_by(Expense.id.desc()).first()

            # Si no se encuentra por fecha exacta (ej: desfase de hora o zona horaria), buscar por nombre de punto y monto
            if not gasto_asociado and punto_nombre:
                gasto_asociado = query_gasto.filter(
                    Expense.descripcion.ilike(f"%{punto_nombre}%")
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
    monto_anterior = transaccion.monto
    local_anterior = transaccion.local_id
    fecha_anterior = transaccion.fecha
    
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
            
    asesor_id_str = request.form.get('asesor_id')
    if asesor_id_str is not None:
        if asesor_id_str.isdigit():
            transaccion.asesor_id = int(asesor_id_str)
        elif asesor_id_str == '':
            transaccion.asesor_id = None

    transaccion.descripcion = descripcion
    if transaccion.tipo_movimiento == 'abono':
        transaccion.metodo_pago = metodo_pago
        
        # Sincronizar gasto asociado si existe
        punto = Punto.query.get(punto_id)
        punto_nombre = (punto.nombre if punto else '').strip()
        
        query_gasto = Expense.query.filter(
            (Expense.categoria.ilike('%abono%')) | 
            (Expense.categoria.ilike('%punto%')) | 
            (Expense.descripcion.ilike(f"%{punto_nombre}%")) |
            (Expense.descripcion.ilike('%abono%')),
            Expense.monto == monto_anterior
        )
        if local_anterior:
            query_gasto = query_gasto.filter(
                (Expense.local_id == local_anterior) | (Expense.local_id.is_(None))
            )

        gasto_asociado = query_gasto.filter(
            db.func.date(Expense.fecha_gasto) == db.func.date(fecha_anterior)
        ).order_by(Expense.id.desc()).first()

        if not gasto_asociado and punto_nombre:
            gasto_asociado = query_gasto.filter(
                Expense.descripcion.ilike(f"%{punto_nombre}%")
            ).order_by(Expense.id.desc()).first()

        if gasto_asociado:
            gasto_asociado.monto = transaccion.monto
            gasto_asociado.local_id = transaccion.local_id
            gasto_asociado.metodo_pago = transaccion.metodo_pago
            gasto_asociado.fecha_gasto = transaccion.fecha
            gasto_asociado.descripcion = f"Abono a Punto {punto_nombre}" + (f" ({transaccion.descripcion})" if transaccion.descripcion else "")
        
    try:
        db.session.commit()
        flash('Transacción actualizada exitosamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error al intentar actualizar la transacción.', 'danger')
        
    return redirect(url_for('puntos_bp.detalle', id=punto_id))

