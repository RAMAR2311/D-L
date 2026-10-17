from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_from_directory
from flask_login import login_required, current_user
from models import db, Provider, ProviderInvoice, ProviderPayment, Expense, Asesor, obtener_hora_bogota
from decorators import admin_required
from decimal import Decimal
import os
import werkzeug.utils
from datetime import datetime

providers_bp = Blueprint('providers_bp', __name__, url_prefix='/proveedores')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@providers_bp.route('/', methods=['GET'])
@login_required
@admin_required
def index():
    proveedores = Provider.query.order_by(Provider.nombre.asc()).all()

    # Pre-calcular totales para la lista de tarjetas / tabla y métricas globales
    total_deuda_global = Decimal('0.00')
    total_facturado_global = Decimal('0.00')
    total_abonos_global = Decimal('0.00')

    datos_proveedores = []
    for prov in proveedores:
        tot_fact = sum((i.monto_total for i in prov.invoices), Decimal('0.00'))
        tot_abon = sum((p.monto_abonado for p in prov.payments), Decimal('0.00'))
        saldo = tot_fact - tot_abon

        total_facturado_global += tot_fact
        total_abonos_global += tot_abon
        total_deuda_global += max(saldo, Decimal('0.00'))

        datos_proveedores.append({
            'provider': prov,
            'total_facturado': tot_fact,
            'total_abonos': tot_abon,
            'saldo_pendiente': saldo
        })

    return render_template(
        'providers/list.html',
        proveedores=datos_proveedores,
        total_proveedores=len(proveedores),
        total_deuda_global=total_deuda_global,
        total_facturado_global=total_facturado_global,
        total_abonos_global=total_abonos_global
    )

@providers_bp.route('/crear', methods=['POST'])
@login_required
@admin_required
def crear():
    nombre = request.form.get('nombre', '').strip()
    empresa = request.form.get('empresa', '').strip()
    telefono = request.form.get('telefono', '').strip()

    if not nombre:
        flash('El nombre del proveedor es obligatorio.', 'danger')
        return redirect(url_for('providers_bp.index'))

    nuevo_prov = Provider(
        nombre=nombre,
        empresa=empresa if empresa else None,
        telefono=telefono if telefono else None,
        fecha_creacion=obtener_hora_bogota()
    )

    try:
        db.session.add(nuevo_prov)
        db.session.commit()
        flash(f'Proveedor "{nombre}" registrado exitosamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Ocurrió un error al guardar el proveedor.', 'danger')

    return redirect(url_for('providers_bp.index'))

@providers_bp.route('/<int:provider_id>', methods=['GET'])
@login_required
@admin_required
def detail(provider_id):
    provider = Provider.query.get_or_404(provider_id)

    facturas = ProviderInvoice.query.filter_by(provider_id=provider.id).order_by(ProviderInvoice.fecha_factura.desc()).all()
    pagos = ProviderPayment.query.filter_by(provider_id=provider.id).order_by(ProviderPayment.fecha_pago.desc()).all()

    total_facturado = sum((i.monto_total for i in facturas), Decimal('0.00'))
    total_abonos = sum((p.monto_abonado for p in pagos), Decimal('0.00'))
    saldo_pendiente = total_facturado - total_abonos
    hoy = obtener_hora_bogota().strftime('%Y-%m-%d')
    asesores = Asesor.query.filter_by(estado='Activo').order_by(Asesor.nombre.asc()).all()

    return render_template(
        'providers/detail.html',
        provider=provider,
        facturas=facturas,
        pagos=pagos,
        total_facturado=total_facturado,
        total_abonos=total_abonos,
        saldo_pendiente=saldo_pendiente,
        hoy=hoy,
        asesores=asesores
    )

@providers_bp.route('/<int:provider_id>/invoice', methods=['POST'])
@login_required
@admin_required
def register_invoice(provider_id):
    provider = Provider.query.get_or_404(provider_id)

    try:
        monto_total = Decimal(str(request.form.get('monto_total', '0')))
    except Exception:
        monto_total = Decimal('0.00')

    numero_factura = request.form.get('numero_factura', '').strip()
    descripcion = request.form.get('descripcion', '').strip()

    if monto_total <= Decimal('0.00'):
        flash('El monto de la factura debe ser mayor a 0.', 'danger')
        return redirect(url_for('providers_bp.detail', provider_id=provider.id))

    # Manejo de archivo subido
    comprobante_filename = None
    file = request.files.get('comprobante')

    if file and file.filename != '':
        if allowed_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            timestamp_str = obtener_hora_bogota().strftime('%Y%m%d_%H%M%S')
            comprobante_filename = f"prov_{provider.id}_{timestamp_str}.{ext}"

            upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'providers')
            os.makedirs(upload_dir, exist_ok=True)
            file.save(os.path.join(upload_dir, comprobante_filename))
        else:
            flash('Formato de archivo no permitido. Sube un archivo PNG, JPG o PDF.', 'warning')
            return redirect(url_for('providers_bp.detail', provider_id=provider.id))

    nueva_factura = ProviderInvoice(
        provider_id=provider.id,
        monto_total=monto_total,
        numero_factura=numero_factura if numero_factura else None,
        descripcion=descripcion if descripcion else None,
        comprobante=comprobante_filename,
        fecha_factura=obtener_hora_bogota()
    )

    try:
        db.session.add(nueva_factura)
        db.session.commit()
        flash('Factura de proveedor registrada exitosamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error al guardar la factura.', 'danger')

    return redirect(url_for('providers_bp.detail', provider_id=provider.id))

@providers_bp.route('/<int:provider_id>/payment', methods=['POST'])
@login_required
@admin_required
def register_payment(provider_id):
    provider = Provider.query.get_or_404(provider_id)

    try:
        monto_abonado = Decimal(str(request.form.get('monto_abonado', '0')).replace(',', '').strip())
    except Exception:
        monto_abonado = Decimal('0.00')

    metodo_pago = request.form.get('metodo_pago', 'efectivo').strip().lower()
    if metodo_pago not in ['efectivo', 'nequi', 'bancolombia', 'daviplata', 'bold', 'addi', 'qr_llave']:
        metodo_pago = 'efectivo'

    try:
        local_id = int(request.form.get('local_id', 1))
    except (ValueError, TypeError):
        local_id = getattr(current_user, 'local_asignado', 1) or 1

    observacion = request.form.get('observacion', '').strip()

    fecha_pago_str = request.form.get('fecha_pago')
    if fecha_pago_str:
        try:
            hora_actual = obtener_hora_bogota().time()
            fecha_dt = datetime.strptime(fecha_pago_str, '%Y-%m-%d').replace(
                hour=hora_actual.hour, minute=hora_actual.minute, second=hora_actual.second
            )
        except ValueError:
            fecha_dt = obtener_hora_bogota()
    else:
        fecha_dt = obtener_hora_bogota()

    if monto_abonado <= Decimal('0.00'):
        flash('El monto abonado debe ser mayor a 0.', 'danger')
        return redirect(url_for('providers_bp.detail', provider_id=provider.id))

    # Validar asesor responsable obligatorio
    asesor_id_raw = request.form.get('asesor_id')
    if not asesor_id_raw or not asesor_id_raw.isdigit():
        flash('Debe seleccionar un Asesor Responsable obligatorio para registrar el abono.', 'danger')
        return redirect(url_for('providers_bp.detail', provider_id=provider.id))
    asesor_id = int(asesor_id_raw)

    # Manejo de comprobante opcional
    comprobante_filename = None
    file = request.files.get('comprobante')
    if file and file.filename != '':
        if allowed_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            timestamp_str = obtener_hora_bogota().strftime('%Y%m%d_%H%M%S')
            comprobante_filename = f"pago_prov_{provider.id}_{timestamp_str}.{ext}"

            upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'providers')
            os.makedirs(upload_dir, exist_ok=True)
            file.save(os.path.join(upload_dir, comprobante_filename))
        else:
            flash('Formato de comprobante no permitido. Sube un archivo PNG, JPG o PDF.', 'warning')
            return redirect(url_for('providers_bp.detail', provider_id=provider.id))

    try:
        # 1. Crear el egreso contable en Expense (reflejado en Gastos y Tesorería)
        desc_gasto = f"Abono a Proveedor: {provider.nombre}"
        if observacion:
            desc_gasto += f" ({observacion})"

        nuevo_gasto = Expense(
            usuario_id=current_user.id,
            tipo_gasto='Gasto Diario',
            categoria='Abono a Proveedor',
            descripcion=desc_gasto,
            monto=monto_abonado,
            metodo_pago=metodo_pago,
            local_id=local_id,
            fecha_gasto=fecha_dt
        )
        db.session.add(nuevo_gasto)
        db.session.flush()

        # 2. Registrar el abono al proveedor enlazado al gasto
        nuevo_pago = ProviderPayment(
            provider_id=provider.id,
            usuario_id=current_user.id,
            asesor_id=asesor_id,
            local_id=local_id,
            expense_id=nuevo_gasto.id,
            monto_abonado=monto_abonado,
            metodo_pago=metodo_pago,
            observacion=observacion if observacion else None,
            comprobante=comprobante_filename,
            fecha_pago=fecha_dt
        )
        db.session.add(nuevo_pago)
        db.session.commit()
        flash(f'Abono de ${monto_abonado:,.0f} registrado exitosamente ({nuevo_pago.metodo_pago_display}) y reflejado en Tesorería y Gastos.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error al registrar el abono.', 'danger')

    return redirect(url_for('providers_bp.detail', provider_id=provider.id))

@providers_bp.route('/eliminar/<int:provider_id>', methods=['POST'])
@login_required
@admin_required
def eliminar(provider_id):
    provider = Provider.query.get_or_404(provider_id)
    nombre = provider.nombre

    # Eliminar archivos de soporte si existen
    upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'providers')
    for inv in provider.invoices:
        if inv.comprobante:
            file_path = os.path.join(upload_dir, inv.comprobante)
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception:
                    pass

    # Eliminar comprobantes de abonos y gastos vinculados
    for p in provider.payments:
        if p.comprobante:
            file_path = os.path.join(upload_dir, p.comprobante)
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception:
                    pass
        if p.expense_id:
            gasto = Expense.query.get(p.expense_id)
            if gasto:
                try:
                    db.session.delete(gasto)
                except Exception:
                    pass

    try:
        db.session.delete(provider)
        db.session.commit()
        flash(f'Proveedor "{nombre}" y su historial fueron eliminados.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error al eliminar el proveedor.', 'danger')

    return redirect(url_for('providers_bp.index'))

@providers_bp.route('/factura/editar/<int:invoice_id>', methods=['POST'])
@login_required
@admin_required
def edit_invoice(invoice_id):
    invoice = ProviderInvoice.query.get_or_404(invoice_id)
    provider_id = invoice.provider_id

    try:
        monto_total = Decimal(str(request.form.get('monto_total', '0')))
    except Exception:
        monto_total = Decimal('0.00')

    numero_factura = request.form.get('numero_factura', '').strip()
    descripcion = request.form.get('descripcion', '').strip()

    if monto_total <= Decimal('0.00'):
        flash('El monto de la factura debe ser mayor a 0.', 'danger')
        return redirect(url_for('providers_bp.detail', provider_id=provider_id))

    invoice.monto_total = monto_total
    invoice.numero_factura = numero_factura if numero_factura else None
    invoice.descripcion = descripcion if descripcion else None

    file = request.files.get('comprobante')
    if file and file.filename != '':
        if allowed_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            timestamp_str = obtener_hora_bogota().strftime('%Y%m%d_%H%M%S')
            new_filename = f"prov_{provider_id}_{timestamp_str}.{ext}"

            upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'providers')
            os.makedirs(upload_dir, exist_ok=True)

            if invoice.comprobante:
                old_file_path = os.path.join(upload_dir, invoice.comprobante)
                if os.path.exists(old_file_path):
                    try:
                        os.remove(old_file_path)
                    except Exception:
                        pass

            file.save(os.path.join(upload_dir, new_filename))
            invoice.comprobante = new_filename
        else:
            flash('Formato de archivo no permitido.', 'warning')
            return redirect(url_for('providers_bp.detail', provider_id=provider_id))

    try:
        db.session.commit()
        flash('Factura actualizada exitosamente.', 'success')
    except Exception:
        db.session.rollback()
        flash('Error al actualizar la factura.', 'danger')

    return redirect(url_for('providers_bp.detail', provider_id=provider_id))

@providers_bp.route('/factura/eliminar/<int:invoice_id>', methods=['POST'])
@login_required
@admin_required
def delete_invoice(invoice_id):
    invoice = ProviderInvoice.query.get_or_404(invoice_id)
    provider_id = invoice.provider_id

    if invoice.comprobante:
        upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'providers')
        file_path = os.path.join(upload_dir, invoice.comprobante)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass

    try:
        db.session.delete(invoice)
        db.session.commit()
        flash('Factura eliminada.', 'success')
    except Exception:
        db.session.rollback()
        flash('Error al eliminar la factura.', 'danger')

    return redirect(url_for('providers_bp.detail', provider_id=provider_id))

@providers_bp.route('/abono/editar/<int:payment_id>', methods=['POST'])
@login_required
@admin_required
def edit_payment(payment_id):
    payment = ProviderPayment.query.get_or_404(payment_id)
    provider_id = payment.provider_id
    provider = payment.provider

    try:
        monto_abonado = Decimal(str(request.form.get('monto_abonado', '0')).replace(',', '').strip())
    except Exception:
        monto_abonado = Decimal('0.00')

    metodo_pago = request.form.get('metodo_pago', payment.metodo_pago or 'efectivo').strip().lower()
    if metodo_pago not in ['efectivo', 'nequi', 'bancolombia', 'daviplata', 'bold', 'addi', 'qr_llave']:
        metodo_pago = 'efectivo'

    try:
        local_id = int(request.form.get('local_id', payment.local_id or 1))
    except (ValueError, TypeError):
        local_id = payment.local_id or 1

    observacion = request.form.get('observacion', '').strip()

    fecha_pago_str = request.form.get('fecha_pago')
    if fecha_pago_str:
        try:
            hora_antigua = (payment.fecha_pago or obtener_hora_bogota()).time()
            fecha_dt = datetime.strptime(fecha_pago_str, '%Y-%m-%d').replace(
                hour=hora_antigua.hour, minute=hora_antigua.minute, second=hora_antigua.second
            )
        except ValueError:
            fecha_dt = payment.fecha_pago or obtener_hora_bogota()
    else:
        fecha_dt = payment.fecha_pago or obtener_hora_bogota()

    if monto_abonado <= Decimal('0.00'):
        flash('El monto abonado debe ser mayor a 0.', 'danger')
        return redirect(url_for('providers_bp.detail', provider_id=provider_id))

    # Manejo de comprobante nuevo opcional
    file = request.files.get('comprobante')
    if file and file.filename != '':
        if allowed_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            timestamp_str = obtener_hora_bogota().strftime('%Y%m%d_%H%M%S')
            new_filename = f"pago_prov_{provider_id}_{timestamp_str}.{ext}"

            upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'providers')
            os.makedirs(upload_dir, exist_ok=True)

            if payment.comprobante:
                old_file_path = os.path.join(upload_dir, payment.comprobante)
                if os.path.exists(old_file_path):
                    try:
                        os.remove(old_file_path)
                    except Exception:
                        pass

            file.save(os.path.join(upload_dir, new_filename))
            payment.comprobante = new_filename
        else:
            flash('Formato de comprobante no permitido.', 'warning')
            return redirect(url_for('providers_bp.detail', provider_id=provider_id))

    payment.monto_abonado = monto_abonado
    payment.metodo_pago = metodo_pago
    payment.local_id = local_id

    asesor_id_str = request.form.get('asesor_id')
    if asesor_id_str is not None:
        if asesor_id_str.isdigit():
            payment.asesor_id = int(asesor_id_str)
        elif asesor_id_str == '':
            payment.asesor_id = None

    payment.observacion = observacion if observacion else None
    payment.fecha_pago = fecha_dt

    # Sincronizar con el gasto asociado en Tesorería / Gastos
    desc_gasto = f"Abono a Proveedor: {provider.nombre if provider else 'Proveedor'}"
    if observacion:
        desc_gasto += f" ({observacion})"

    if payment.expense_id:
        gasto = Expense.query.get(payment.expense_id)
        if gasto:
            gasto.monto = monto_abonado
            gasto.metodo_pago = metodo_pago
            gasto.local_id = local_id
            gasto.fecha_gasto = fecha_dt
            gasto.descripcion = desc_gasto
        else:
            nuevo_gasto = Expense(
                usuario_id=current_user.id,
                tipo_gasto='Gasto Diario',
                categoria='Abono a Proveedor',
                descripcion=desc_gasto,
                monto=monto_abonado,
                metodo_pago=metodo_pago,
                local_id=local_id,
                fecha_gasto=fecha_dt
            )
            db.session.add(nuevo_gasto)
            db.session.flush()
            payment.expense_id = nuevo_gasto.id
    else:
        nuevo_gasto = Expense(
            usuario_id=current_user.id,
            tipo_gasto='Gasto Diario',
            categoria='Abono a Proveedor',
            descripcion=desc_gasto,
            monto=monto_abonado,
            metodo_pago=metodo_pago,
            local_id=local_id,
            fecha_gasto=fecha_dt
        )
        db.session.add(nuevo_gasto)
        db.session.flush()
        payment.expense_id = nuevo_gasto.id

    try:
        db.session.commit()
        flash('Abono y registro contable en Tesorería actualizados exitosamente.', 'success')
    except Exception:
        db.session.rollback()
        flash('Error al actualizar el abono.', 'danger')

    return redirect(url_for('providers_bp.detail', provider_id=provider_id))

@providers_bp.route('/abono/eliminar/<int:payment_id>', methods=['POST'])
@login_required
@admin_required
def delete_payment(payment_id):
    payment = ProviderPayment.query.get_or_404(payment_id)
    provider_id = payment.provider_id

    # Si tiene comprobante físico, eliminarlo
    if payment.comprobante:
        upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'providers')
        file_path = os.path.join(upload_dir, payment.comprobante)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass

    # Si tiene un gasto vinculado en Tesorería / Gastos, eliminarlo
    if payment.expense_id:
        gasto = Expense.query.get(payment.expense_id)
        if gasto:
            try:
                db.session.delete(gasto)
            except Exception:
                pass

    try:
        db.session.delete(payment)
        db.session.commit()
        flash('Abono y su registro en Tesorería eliminados exitosamente.', 'success')
    except Exception:
        db.session.rollback()
        flash('Error al eliminar el abono.', 'danger')

    return redirect(url_for('providers_bp.detail', provider_id=provider_id))
