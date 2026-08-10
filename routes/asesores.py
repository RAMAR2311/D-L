from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, Asesor, Sale, User, obtener_hora_bogota
from decorators import admin_required
from datetime import datetime
from decimal import Decimal

asesores_bp = Blueprint('asesores_bp', __name__, url_prefix='/asesores')

@asesores_bp.route('/', methods=['GET'])
@login_required
@admin_required
def index():
    active_local = request.args.get('local', 'central').lower()
    if active_local not in ['central', '1', '2', '3']:
        active_local = 'central'

    # Autopoblar asesores iniciales si la tabla está vacía (como en la imagen adjunta)
    if Asesor.query.count() == 0:
        iniciales = [
            {'nombre': 'Bryan Andres', 'local_id': 1},
            {'nombre': 'Estefania', 'local_id': 1},
            {'nombre': 'Jorge Toro', 'local_id': 2},
            {'nombre': 'Laura Narvaez', 'local_id': 2},
            {'nombre': 'Leonardo Sarmiento', 'local_id': 3},
            {'nombre': 'Maria Camila', 'local_id': 3},
            {'nombre': 'Valentina Tovar', 'local_id': 1}
        ]
        for a in iniciales:
            db.session.add(Asesor(nombre=a['nombre'], local_id=a['local_id'], estado='Activo'))
        db.session.commit()

    query = Asesor.query
    if active_local != 'central':
        query = query.filter(or_(Asesor.local_id == int(active_local), Asesor.local_id == 0))

    asesores = query.order_by(Asesor.fecha_registro.desc()).all()

    return render_template(
        'asesores/index.html',
        asesores=asesores,
        active_local=active_local,
        total_asesores=len(asesores)
    )

@asesores_bp.route('/crear', methods=['POST'])
@login_required
@admin_required
def crear():
    nombre = request.form.get('nombre', '').strip()
    try:
        local_id = int(request.form.get('local_id', '0'))
    except ValueError:
        local_id = 0

    if not nombre:
        flash('El nombre completo del asesor es obligatorio.', 'danger')
        return redirect(url_for('asesores_bp.index'))

    nuevo_asesor = Asesor(
        nombre=nombre,
        local_id=local_id,
        estado='Activo',
        fecha_registro=obtener_hora_bogota()
    )

    try:
        db.session.add(nuevo_asesor)
        db.session.commit()
        flash(f'Asesor "{nombre}" registrado exitosamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Ocurrió un error al registrar el asesor.', 'danger')

    return redirect(url_for('asesores_bp.index', local=str(local_id)))

@asesores_bp.route('/editar/<int:id>', methods=['POST'])
@login_required
@admin_required
def editar(id):
    asesor = Asesor.query.get_or_404(id)
    nombre = request.form.get('nombre', '').strip()
    estado = request.form.get('estado', 'Activo')
    try:
        local_id = int(request.form.get('local_id', '0'))
    except ValueError:
        local_id = asesor.local_id

    if not nombre:
        flash('El nombre del asesor no puede estar vacío.', 'danger')
        return redirect(url_for('asesores_bp.index'))

    asesor.nombre = nombre
    asesor.local_id = local_id
    asesor.estado = estado

    try:
        db.session.commit()
        flash(f'Asesor "{nombre}" actualizado correctamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error al actualizar el asesor.', 'danger')

    return redirect(url_for('asesores_bp.index'))

@asesores_bp.route('/toggle_estado/<int:id>', methods=['POST'])
@login_required
@admin_required
def toggle_estado(id):
    asesor = Asesor.query.get_or_404(id)
    if asesor.estado == 'Activo':
        asesor.estado = 'Inactivo'
        msg = f'Asesor "{asesor.nombre}" desactivado.'
    else:
        asesor.estado = 'Activo'
        msg = f'Asesor "{asesor.nombre}" activado.'

    try:
        db.session.commit()
        flash(msg, 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error al cambiar el estado del asesor.', 'danger')

    return redirect(url_for('asesores_bp.index'))

@asesores_bp.route('/eliminar/<int:id>', methods=['POST'])
@login_required
@admin_required
def eliminar(id):
    asesor = Asesor.query.get_or_404(id)
    nombre = asesor.nombre

    try:
        db.session.delete(asesor)
        db.session.commit()
        flash(f'Asesor "{nombre}" eliminado.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error al eliminar el asesor.', 'danger')

    return redirect(url_for('asesores_bp.index'))

@asesores_bp.route('/ventas', methods=['GET'])
@login_required
@admin_required
def ventas_asesor():
    active_local = request.args.get('local', 'central').lower()
    if active_local not in ['central', '1', '2', '3']:
        active_local = 'central'

    asesor_id_str = request.args.get('asesor_id', 'todas')
    
    hoy_str = obtener_hora_bogota().strftime('%Y-%m-%d')
    fecha_inicio_str = request.args.get('fecha_inicio', hoy_str)
    fecha_fin_str = request.args.get('fecha_fin', hoy_str)

    try:
        fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date()
        fecha_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d').date()
    except ValueError:
        fecha_inicio = obtener_hora_bogota().date()
        fecha_fin = obtener_hora_bogota().date()
        fecha_inicio_str = hoy_str
        fecha_fin_str = hoy_str

    inicio_dt = datetime.combine(fecha_inicio, datetime.min.time())
    fin_dt = datetime.combine(fecha_fin, datetime.max.time())

    query_asesores = Asesor.query.order_by(Asesor.nombre.asc())
    if active_local != 'central':
        query_asesores = query_asesores.filter(or_(Asesor.local_id == int(active_local), Asesor.local_id == 0))
    todos_asesores = query_asesores.all()

    query_ventas = Sale.query.filter(
        Sale.fecha_venta >= inicio_dt,
        Sale.fecha_venta <= fin_dt
    )

    if active_local != 'central':
        local_num = int(active_local)
        query_ventas = query_ventas.filter(Sale.local_id == local_num)

    asesor_seleccionado = None
    if asesor_id_str != 'todas':
        try:
            aid = int(asesor_id_str)
            asesor_seleccionado = Asesor.query.get(aid)
            if asesor_seleccionado:
                query_ventas = query_ventas.filter(Sale.asesor_id == aid)
        except (ValueError, TypeError):
            pass

    ventas = query_ventas.order_by(Sale.fecha_venta.desc()).all()

    total_ventas_asesor = sum((v.monto_total for v in ventas), Decimal('0.00'))
    conteo_ventas_asesor = len(ventas)

    return render_template(
        'asesores/ventas.html',
        ventas=ventas,
        todos_asesores=todos_asesores,
        asesor_seleccionado=asesor_seleccionado,
        asesor_id_str=asesor_id_str,
        active_local=active_local,
        fecha_inicio=fecha_inicio_str,
        fecha_fin=fecha_fin_str,
        total_ventas_asesor=total_ventas_asesor,
        conteo_ventas_asesor=conteo_ventas_asesor
    )
