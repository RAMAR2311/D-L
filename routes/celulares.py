from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from models import db, Product, Sale, SaleDetail, SalePayment, ProductVariant
from decorators import admin_required
from datetime import datetime
import pytz
import os
from werkzeug.utils import secure_filename
from decimal import Decimal
from models import db, Product, Sale, SaleDetail, SalePayment, ProductVariant, ArqueoCaja

celulares_bp = Blueprint('celulares_bp', __name__)

def obtener_hora_bogota():
    return datetime.now(pytz.timezone('America/Bogota')).replace(tzinfo=None)

@celulares_bp.route('/inventario')
@login_required
def inventario():
    # Solo celulares
    celulares = Product.query.filter_by(tipo_inventario='celulares').order_by(Product.fecha_creacion.desc()).all()
    return render_template('celulares/inventario.html', celulares=celulares)

@celulares_bp.route('/nuevo', methods=['GET', 'POST'])
@login_required
@admin_required
def nuevo_celular():
    if request.method == 'POST':
        marca = request.form.get('marca', '').strip()
        modelo_celular = request.form.get('modelo_celular', '').strip()
        color = request.form.get('color', '').strip()
        
        precio_costo_str = request.form.get('precio_costo', '0').replace(',', '')
        precio_sugerido_str = request.form.get('precio_sugerido', '0').replace(',', '')
        precio_minimo_str = request.form.get('precio_minimo', '0').replace(',', '')
        
        nombre_completo = f"Celular {marca} {modelo_celular} {color}".strip()
        sku_base = f"CEL-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        imagen_filename = None
        if 'imagen' in request.files:
            file = request.files['imagen']
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
                upload_folder = current_app.config['UPLOAD_FOLDER']
                if not os.path.exists(upload_folder):
                    os.makedirs(upload_folder)
                file.save(os.path.join(upload_folder, filename))
                imagen_filename = filename
        
        # El producto base actúa como agrupadory contenedor
        nuevo = Product(
            nombre=nombre_completo,
            sku=sku_base,
            tipo_inventario='celulares',
            cantidad_stock=0, # Se calculará por las variantes
            precio_costo=float(precio_costo_str) if precio_costo_str else 0.0,
            precio_minimo=float(precio_minimo_str) if precio_minimo_str else 0.0,
            precio_sugerido=float(precio_sugerido_str) if precio_sugerido_str else 0.0,
            marca=marca,
            modelo_celular=modelo_celular,
            observacion=f"Color: {color}" if color else "",
            imagen=imagen_filename
        )
        
        try:
            db.session.add(nuevo)
            db.session.commit()
            flash('Modelo base creado exitosamente. Ahora puede agregar los IMEIs desde el inventario.', 'success')
            return redirect(url_for('celulares_bp.inventario'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al registrar: {str(e)}', 'danger')

    return render_template('celulares/form_celular.html', celular=None)

@celulares_bp.route('/editar/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def editar_celular(id):
    celular = Product.query.get_or_404(id)
    if celular.tipo_inventario != 'celulares':
        flash('El producto seleccionado no es un celular.', 'danger')
        return redirect(url_for('celulares_bp.inventario'))
        
    if request.method == 'POST':
        celular.marca = request.form.get('marca', '').strip()
        celular.modelo_celular = request.form.get('modelo_celular', '').strip()
        color = request.form.get('color', '').strip()
        
        celular.nombre = f"Celular {celular.marca} {celular.modelo_celular} {color}".strip()
        if color:
            celular.observacion = f"Color: {color}"
            
        precio_costo_str = request.form.get('precio_costo', '0').replace(',', '')
        precio_sugerido_str = request.form.get('precio_sugerido', '0').replace(',', '')
        precio_minimo_str = request.form.get('precio_minimo', '0').replace(',', '')
        
        celular.precio_costo = float(precio_costo_str) if precio_costo_str else 0.0
        celular.precio_minimo = float(precio_minimo_str) if precio_minimo_str else 0.0
        celular.precio_sugerido = float(precio_sugerido_str) if precio_sugerido_str else 0.0
        
        if 'imagen' in request.files:
            file = request.files['imagen']
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
                upload_folder = current_app.config['UPLOAD_FOLDER']
                if not os.path.exists(upload_folder):
                    os.makedirs(upload_folder)
                file.save(os.path.join(upload_folder, filename))
                celular.imagen = filename
            
        try:
            db.session.commit()
            flash('Modelo base actualizado exitosamente.', 'success')
            return redirect(url_for('celulares_bp.inventario'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar: {str(e)}', 'danger')
            
    return render_template('celulares/form_celular.html', celular=celular)

@celulares_bp.route('/gestionar_imeis/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def gestionar_imeis(id):
    celular = Product.query.get_or_404(id)
    if celular.tipo_inventario != 'celulares':
        flash('El producto seleccionado no es un celular.', 'danger')
        return redirect(url_for('celulares_bp.inventario'))
        
    if request.method == 'POST':
        imeis = request.form.getlist('imeis[]')
        estados = request.form.getlist('estados[]')
        costos = request.form.getlist('costos[]')
        sugeridos = request.form.getlist('sugeridos[]')
        minimos = request.form.getlist('minimos[]')
        observaciones = request.form.getlist('observaciones[]')
        
        # Opcional: Recibir IDs de IMEIs a eliminar
        eliminar_ids = request.form.getlist('eliminar_ids[]')
        
        try:
            stock_modificado = 0
            
            # 1. Eliminar variantes marcadas
            for del_id in eliminar_ids:
                if not del_id: continue
                vari = ProductVariant.query.get(int(del_id))
                if vari and vari.product_id == celular.id:
                    if vari.cantidad_stock <= 0:
                        db.session.rollback()
                        flash(f'No se puede eliminar el IMEI {vari.nombre_variante} porque ya fue vendido.', 'danger')
                        return redirect(url_for('celulares_bp.gestionar_imeis', id=id))
                    db.session.delete(vari)
                    stock_modificado -= 1
                    
            # 2. Agregar nuevos IMEIs
            for i in range(len(imeis)):
                imei_val = imeis[i].strip()
                if not imei_val: continue
                
                # Validar existencia
                existente = ProductVariant.query.filter(ProductVariant.nombre_variante.like(f"%{imei_val}%")).first()
                if existente:
                    db.session.rollback()
                    flash(f'El IMEI {imei_val} ya existe en el sistema.', 'danger')
                    return redirect(url_for('celulares_bp.gestionar_imeis', id=id))
                    
                estado_val = estados[i] if i < len(estados) else 'Nuevo'
                costo_val = float(costos[i].replace(',', '')) if i < len(costos) and costos[i] else celular.precio_costo
                sugerido_val = float(sugeridos[i].replace(',', '')) if i < len(sugeridos) and sugeridos[i] else celular.precio_sugerido
                minimo_val = float(minimos[i].replace(',', '')) if i < len(minimos) and minimos[i] else celular.precio_minimo
                obs_val = observaciones[i] if i < len(observaciones) else ''
                
                nombre_var = f"IMEI: {imei_val} - {estado_val}"
                if obs_val:
                    nombre_var += f" ({obs_val})"
                    
                nueva_var = ProductVariant(
                    product_id=celular.id,
                    nombre_variante=nombre_var,
                    cantidad_stock=1,
                    precio_costo=costo_val,
                    precio_sugerido=sugerido_val,
                    precio_minimo=minimo_val
                )
                db.session.add(nueva_var)
                stock_modificado += 1
                
            # 3. Recalcular Stock
            db.session.flush()
            celular.cantidad_stock = sum([v.cantidad_stock for v in celular.variantes if v.cantidad_stock > 0])
            
            db.session.commit()
            flash('Inventario de IMEIs actualizado exitosamente.', 'success')
            return redirect(url_for('celulares_bp.inventario'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al guardar IMEIs: {str(e)}', 'danger')
            
    return render_template('celulares/gestionar_imeis.html', celular=celular)

@celulares_bp.route('/editar_imei/<int:id>', methods=['POST'])
@login_required
@admin_required
def editar_imei(id):
    variante = ProductVariant.query.get_or_404(id)
    
    nuevo_nombre = request.form.get('nombre_variante', '').strip()
    costo_str = request.form.get('precio_costo', '0').replace(',', '')
    sugerido_str = request.form.get('precio_sugerido', '0').replace(',', '')
    minimo_str = request.form.get('precio_minimo', '0').replace(',', '')
    
    if nuevo_nombre:
        variante.nombre_variante = nuevo_nombre
    
    variante.precio_costo = float(costo_str) if costo_str else 0.0
    variante.precio_sugerido = float(sugerido_str) if sugerido_str else 0.0
    variante.precio_minimo = float(minimo_str) if minimo_str else 0.0
    
    try:
        db.session.commit()
        flash('IMEI actualizado correctamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al actualizar el IMEI: {str(e)}', 'danger')
        
    return redirect(url_for('celulares_bp.gestionar_imeis', id=variante.product_id))

@celulares_bp.route('/eliminar/<int:id>', methods=['POST'])
@login_required
@admin_required
def eliminar_celular(id):
    celular = Product.query.get_or_404(id)
    if celular.tipo_inventario != 'celulares':
        flash('No es un celular', 'danger')
        return redirect(url_for('celulares_bp.inventario'))
        
    if celular.detalles_venta:
        flash('No se puede eliminar porque ya tiene ventas asociadas.', 'danger')
        return redirect(url_for('celulares_bp.inventario'))
        
    
    try:
        db.session.delete(celular)
        db.session.commit()
        flash('Modelo de celular eliminado exitosamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar el modelo: {str(e)}', 'danger')
        
    return redirect(url_for('celulares_bp.inventario'))

@celulares_bp.route('/clientes')
@login_required
@admin_required
def clientes():
    # Obtener todas las ventas de celulares con cliente asociado
    from models import SaleClient, SaleDetail
    
    clientes_lista = db.session.query(SaleClient, SaleDetail).join(Sale, SaleClient.sale_id == Sale.id).join(SaleDetail, Sale.id == SaleDetail.sale_id).join(Product, SaleDetail.product_id == Product.id).filter(Product.tipo_inventario == 'celulares').order_by(SaleClient.id.desc()).all()
    
    return render_template('celulares/clientes.html', clientes=clientes_lista)

@celulares_bp.route('/venta', methods=['GET', 'POST'])
@login_required
def venta():
    # Mostrar solo celulares que están en stock
    celulares_disponibles = Product.query.filter(
        Product.tipo_inventario == 'celulares',
        Product.cantidad_stock > 0
    ).all()
    
    if request.method == 'POST':
        celular_id = request.form.get('celular_id')
        precio_venta_final = float(request.form.get('precio_venta_final', 0.0))
        
        # Pagos mixtos
        metodos_pago = request.form.getlist('metodo_pago[]')
        montos_pago = request.form.getlist('monto_pago[]')
        
        if not celular_id or not metodos_pago or not montos_pago:
            flash('Datos incompletos para la venta.', 'danger')
            return redirect(url_for('celulares_bp.venta'))
            
        celular = Product.query.get(celular_id)
        if not celular or celular.cantidad_stock < 1:
            flash('El celular seleccionado no está disponible en stock.', 'danger')
            return redirect(url_for('celulares_bp.venta'))
            
        if precio_venta_final < float(celular.precio_minimo) and current_user.rol != 'admin':
            flash(f'El precio de venta no puede ser menor al mínimo permitido (${celular.precio_minimo:,.2f}).', 'danger')
            return redirect(url_for('celulares_bp.venta'))
            
        # Crear la Venta General (Se registrará en cajas)
        nueva_venta = Sale(
            vendedor_id=current_user.id,
            monto_total=precio_venta_final,
            # metode_pago is legacy, we can put the primary one or 'mixto'
            metodo_pago=metodos_pago[0] if len(metodos_pago) == 1 else 'mixto',
            tipo_venta='celulares'
        )
        db.session.add(nueva_venta)
        db.session.flush()
        
        # Registrar pagos
        suma_pagos = 0.0
        for mp, monto in zip(metodos_pago, montos_pago):
            monto_float = float(monto)
            if monto_float > 0:
                pago = SalePayment(
                    sale_id=nueva_venta.id,
                    metodo_pago=mp,
                    monto=monto_float
                )
                db.session.add(pago)
                suma_pagos += monto_float
                
        if abs(suma_pagos - precio_venta_final) > 0.01:
            db.session.rollback()
            flash('La suma de los métodos de pago no coincide con el total de la venta.', 'danger')
            return redirect(url_for('celulares_bp.venta'))
            
        # Registrar detalle
        detalle = SaleDetail(
            sale_id=nueva_venta.id,
            product_id=celular.id,
            cantidad_vendida=1,
            precio_venta_final=precio_venta_final
        )
        db.session.add(detalle)
        
        # Descontar stock
        celular.cantidad_stock -= 1
        
        try:
            db.session.commit()
            flash('Venta de celular registrada exitosamente.', 'success')
            return redirect(url_for('celulares_bp.historial_ventas'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al registrar la venta: {str(e)}', 'danger')
            
    return render_template('celulares/venta.html', celulares=celulares_disponibles)

@celulares_bp.route('/ventas/historial')
@login_required
def historial_ventas():
    # Obtener las ventas donde haya al menos un detalle de un producto tipo 'celulares'
    ventas_celulares = Sale.query.join(SaleDetail).join(Product).filter(
        Product.tipo_inventario == 'celulares'
    ).order_by(Sale.fecha_venta.desc()).all()
    
    # Para la vista, queremos mostrar datos específicos
    datos_historial = []
    for v in ventas_celulares:
        # En caso de ventas mixtas, filtramos solo los detalles de celulares (aunque usualmente será 1)
        detalles_cel = [d for d in v.detalles if d.producto and d.producto.tipo_inventario == 'celulares']
        for d in detalles_cel:
            datos_historial.append({
                'id_venta': v.id,
                'fecha': v.fecha_venta,
                'vendedor': v.vendedor.nombre,
                'celular': f"{d.producto.nombre} (IMEI: {d.producto.imei or 'N/A'})",
                'precio_venta': d.precio_venta_final,
                'metodo_pago': v.metodo_pago_display
            })
            
    return render_template('celulares/historial_ventas.html', historial=datos_historial)

@celulares_bp.route('/arqueo/nuevo', methods=['GET', 'POST'])
@login_required
def arqueo_nuevo():
    # Obtener fecha de la URL o usar hoy
    fecha_str = request.args.get('fecha', obtener_hora_bogota().strftime('%Y-%m-%d'))
    try:
        fecha_seleccionada = datetime.strptime(fecha_str, '%Y-%m-%d').date()
    except ValueError:
        fecha_seleccionada = obtener_hora_bogota().date()
        fecha_str = fecha_seleccionada.strftime('%Y-%m-%d')

    # Ventas de celulares del día
    ventas_del_dia = Sale.query.filter(
        db.func.date(Sale.fecha_venta) == fecha_seleccionada,
        Sale.tipo_venta == 'celulares'
    ).all()
    
    total_efectivo = Decimal('0')
    total_transferencia = Decimal('0')
    for v in ventas_del_dia:
        if v.pagos:
            for pago in v.pagos:
                if pago.metodo_pago == 'efectivo':
                    total_efectivo += pago.monto
                else:
                    total_transferencia += pago.monto
        else:
            if v.metodo_pago == 'efectivo':
                total_efectivo += v.monto_total
            elif v.metodo_pago in ['transferencia', 'nequi', 'bancolombia', 'daviplata']:
                total_transferencia += v.monto_total

    # Verificar si ya existe un arqueo de CELULARES para esa fecha
    arqueo_existente = ArqueoCaja.query.filter_by(fecha_arqueo=fecha_seleccionada, tipo_arqueo='celulares').first()

    if request.method == 'POST':
        if arqueo_existente:
            flash('Ya existe un arqueo de celulares para esta fecha.', 'warning')
            return redirect(url_for('celulares_bp.arqueo_reporte', fecha_inicio=fecha_str, fecha_fin=fecha_str))

        nuevo_arqueo = ArqueoCaja(
            vendedor_id=current_user.id,
            fecha_arqueo=fecha_seleccionada,
            tipo_arqueo='celulares',
            base_inicial=Decimal('0.00'), # Sin base inicial para celulares
            gastos_del_dia=Decimal('0.00'), # Los gastos van a la general
            total_efectivo_sistema=total_efectivo,
            total_transferencia_sistema=total_transferencia,
            total_unidades_ch=Decimal('0.00'),
            total_celulares=Decimal('0.00')
        )

        try:
            db.session.add(nuevo_arqueo)
            db.session.commit()
            flash('Arqueo de celulares guardado exitosamente.', 'success')
            return redirect(url_for('celulares_bp.arqueo_reporte', fecha_inicio=fecha_str, fecha_fin=fecha_str))
        except Exception as e:
            db.session.rollback()
            flash('Ocurrió un error al guardar el arqueo.', 'danger')

    return render_template(
        'celulares/arqueo/form.html',
        fecha=fecha_str,
        total_efectivo=total_efectivo,
        total_transferencia=total_transferencia,
        arqueo_existente=arqueo_existente
    )

@celulares_bp.route('/arqueo/reporte', methods=['GET'])
@login_required
def arqueo_reporte():
    fecha_inicio_str = request.args.get('fecha_inicio', obtener_hora_bogota().strftime('%Y-%m-%d'))
    fecha_fin_str = request.args.get('fecha_fin', obtener_hora_bogota().strftime('%Y-%m-%d'))

    try:
        fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date()
        fecha_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d').date()
    except ValueError:
        fecha_inicio = obtener_hora_bogota().date()
        fecha_fin = obtener_hora_bogota().date()

    if current_user.rol != 'admin':
        hoy = obtener_hora_bogota().date()
        fecha_inicio = hoy
        fecha_fin = hoy
        fecha_inicio_str = hoy.strftime('%Y-%m-%d')
        fecha_fin_str = hoy.strftime('%Y-%m-%d')

    arqueos = ArqueoCaja.query.filter(
        ArqueoCaja.fecha_arqueo >= fecha_inicio,
        ArqueoCaja.fecha_arqueo <= fecha_fin,
        ArqueoCaja.tipo_arqueo == 'celulares'
    ).order_by(ArqueoCaja.fecha_arqueo.desc()).all()

    resumen = {
        'total_efectivo': sum(a.total_efectivo_sistema for a in arqueos),
        'total_transferencia': sum(a.total_transferencia_sistema for a in arqueos)
    }
    resumen['total_recaudado_neto'] = resumen['total_efectivo'] + resumen['total_transferencia']
    
    # Ventas de celulares en el periodo
    ventas_periodo = Sale.query.filter(
        db.func.date(Sale.fecha_venta) >= fecha_inicio,
        db.func.date(Sale.fecha_venta) <= fecha_fin,
        Sale.tipo_venta == 'celulares'
    ).order_by(Sale.fecha_venta.asc()).all()

    fecha_generacion = obtener_hora_bogota().strftime('%Y-%m-%d %H:%M')

    return render_template(
        'celulares/arqueo/reporte.html',
        arqueos=arqueos,
        resumen=resumen,
        fecha_inicio=fecha_inicio_str,
        fecha_fin=fecha_fin_str,
        fecha_generacion=fecha_generacion,
        ventas_periodo=ventas_periodo
    )

