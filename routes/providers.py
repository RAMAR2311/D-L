from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_from_directory
from flask_login import login_required, current_user
from models import db, Provider, ProviderInvoice, ProviderPayment, obtener_hora_bogota
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

    return render_template(
        'providers/detail.html',
        provider=provider,
        facturas=facturas,
        pagos=pagos,
        total_facturado=total_facturado,
        total_abonos=total_abonos,
        saldo_pendiente=saldo_pendiente
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
        monto_abonado = Decimal(str(request.form.get('monto_abonado', '0')))
    except Exception:
        monto_abonado = Decimal('0.00')

    observacion = request.form.get('observacion', '').strip()

    if monto_abonado <= Decimal('0.00'):
        flash('El monto abonado debe ser mayor a 0.', 'danger')
        return redirect(url_for('providers_bp.detail', provider_id=provider.id))

    nuevo_pago = ProviderPayment(
        provider_id=provider.id,
        monto_abonado=monto_abonado,
        observacion=observacion if observacion else None,
        fecha_pago=obtener_hora_bogota()
    )

    try:
        db.session.add(nuevo_pago)
        db.session.commit()
        flash('Abono al proveedor registrado exitosamente.', 'success')
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

    try:
        monto_abonado = Decimal(str(request.form.get('monto_abonado', '0')))
    except Exception:
        monto_abonado = Decimal('0.00')

    observacion = request.form.get('observacion', '').strip()

    if monto_abonado <= Decimal('0.00'):
        flash('El monto abonado debe ser mayor a 0.', 'danger')
        return redirect(url_for('providers_bp.detail', provider_id=provider_id))

    payment.monto_abonado = monto_abonado
    payment.observacion = observacion if observacion else None

    try:
        db.session.commit()
        flash('Abono actualizado exitosamente.', 'success')
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

    try:
        db.session.delete(payment)
        db.session.commit()
        flash('Abono eliminado.', 'success')
    except Exception:
        db.session.rollback()
        flash('Error al eliminar el abono.', 'danger')

    return redirect(url_for('providers_bp.detail', provider_id=provider_id))
