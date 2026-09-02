import os
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, current_user
from flask_wtf.csrf import CSRFProtect

# Importar la instancia de db desde models
from models import db, User

def create_app():
    app = Flask(__name__)
    
    # Configuración mediante variables de entorno (con fallback a PostgreSQL local)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-super-secreta')
    
    # Para la conexión a PostgreSQL, psycopg2 es el default de SQLALchemy al usar postgresql://
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'postgresql://postgres:admin123@localhost:5432/RC')
    
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
    app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32 MB límite de subida

    @app.errorhandler(413)
    def request_entity_too_large(error):
        from flask import flash, redirect, request
        flash('El archivo enviado es demasiado grande (máximo 32MB).', 'danger')
        return redirect(request.referrer or url_for('inventory_bp.index'))

    # Inicializar Extensiones
    db.init_app(app)
    Migrate(app, db)
    CSRFProtect(app)
    
    login_manager = LoginManager()
    login_manager.login_view = 'auth_bp.login'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Importar y Registrar Blueprints
    from routes.sales import sales_bp
    from routes.inventory import inventory_bp
    from routes.auth import auth_bp
    from routes.arqueo import arqueo_bp
    from routes.gastos import gastos_bp
    
    from routes.puntos import puntos_bp
    from routes.traslados import traslados_bp

    app.register_blueprint(sales_bp, url_prefix='/sales')
    app.register_blueprint(inventory_bp, url_prefix='/inventory')
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(arqueo_bp, url_prefix='/arqueo')
    app.register_blueprint(gastos_bp, url_prefix='/gastos')
    app.register_blueprint(puntos_bp, url_prefix='/puntos')
    app.register_blueprint(traslados_bp, url_prefix='/traslados')
    
    # Registro de Blueprint Admin
    from routes.admin import admin_bp
    app.register_blueprint(admin_bp, url_prefix='/admin')

    # Registro de Blueprint Bodega
    from routes.bodega import bodega_bp
    app.register_blueprint(bodega_bp, url_prefix='/bodega')

    # Registro de Blueprint Proveedores
    from routes.providers import providers_bp
    app.register_blueprint(providers_bp)

    # Registro de Blueprint Asesores
    from routes.asesores import asesores_bp
    app.register_blueprint(asesores_bp)


    @app.template_filter('cop')
    def cop_filter(value):
        if value is None:
            return "0"
        try:
            # Formateo a moneda colombiana (separador de miles con coma, como pidió el usuario)
            return "{:,.0f}".format(float(value))
        except (ValueError, TypeError):
            return value

    @app.context_processor
    def inject_pago_servidor():
        import urllib.parse
        from models import ServerPayment, obtener_hora_bogota
        from itsdangerous import URLSafeTimedSerializer

        try:
            ahora = obtener_hora_bogota()
            anio_actual = ahora.year
            mes_actual = ahora.month
            dia_actual = ahora.day

            # Buscar si el mes actual está pagado
            pago = ServerPayment.query.filter_by(anio=anio_actual, mes=mes_actual, estado='pagado').first()

            # Generar token de confirmación firmado con SECRET_KEY para este mes
            serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
            token_confirmacion = serializer.dumps({'anio': anio_actual, 'mes': mes_actual}, salt='server-payment-salt')

            # Construir URL de confirmación completa
            from flask import request
            server_host = request.host_url.rstrip('/') if request else ''
            url_confirmacion = f"{server_host}/servidor/confirmar-pago?token={token_confirmacion}"

            # Nombres de meses en español
            nombres_meses = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
            nombre_mes = nombres_meses[mes_actual] if 1 <= mes_actual <= 12 else str(mes_actual)

            # Mensaje encoded para WhatsApp
            msg_txt = f"Hola, adjunto el comprobante de pago de la mensualidad del servidor Zenic para {nombre_mes} {anio_actual}.\n\nPara confirmar mi pago en el sistema con 1 solo clic, toca aquí:\n{url_confirmacion}"
            whatsapp_url = f"https://wa.me/573115643557?text={urllib.parse.quote(msg_txt)}"


            dias_para_el_15 = 15 - dia_actual
            dias_gabela = (20 - dia_actual + 1) if (16 <= dia_actual <= 20) else 0

            if pago:
                estado = 'pagado'
            elif dia_actual <= 6:
                # Días 1 al 6: Notificación pequeña circular arriba a la derecha ("Al Día")
                estado = 'al_dia'
            elif dia_actual < 15:
                # Días 7 al 14: Alerta preventiva compacta (semana de anticipación)
                estado = 'preventivo'
            elif dia_actual == 15:
                # Día 15: Día de Pago
                estado = 'hoy'
            elif dia_actual <= 20:
                # Días 16 al 20: 5 Días de Gabela (Periodo de Gracia)
                estado = 'gabela'
            else:
                # Día 21+: Vencido tras agotar los 5 días de gabela
                estado = 'vencido'

            return {
                'pago_servidor': {
                    'estado': estado,
                    'mes_nombre': nombre_mes,
                    'anio': anio_actual,
                    'dias_restantes': dias_para_el_15,
                    'dias_vencido': abs(dias_para_el_15),
                    'dias_gabela': dias_gabela,
                    'whatsapp_url': whatsapp_url,
                    'nu_llave': '@QEI910',
                    'nequi_num': '3505422186'
                }
            }

        except Exception:
            return {'pago_servidor': {'estado': 'pagado'}}

    @app.route('/servidor/confirmar-pago')
    def confirmar_pago_servidor():
        from flask import request
        from itsdangerous import URLSafeTimedSerializer, BadSignature
        from models import ServerPayment, db, obtener_hora_bogota

        token = request.args.get('token')
        if not token:
            return "<h2 style='color:red; font-family:sans-serif; text-align:center; margin-top:50px;'>Enlace inválido o incompleto.</h2>", 400

        serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
        try:
            data = serializer.loads(token, salt='server-payment-salt')
            anio = data.get('anio')
            mes = data.get('mes')

            pago = ServerPayment.query.filter_by(anio=anio, mes=mes).first()
            if not pago:
                pago = ServerPayment(anio=anio, mes=mes, estado='pagado', fecha_pago=obtener_hora_bogota())
                db.session.add(pago)
            else:
                pago.estado = 'pagado'
                pago.fecha_pago = obtener_hora_bogota()

            db.session.commit()

            nombres_meses = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
            nombre_mes = nombres_meses[mes] if 1 <= mes <= 12 else str(mes)

            return f"""
            <!DOCTYPE html>
            <html lang="es">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Pago Confirmado - Servidor D&L</title>
                <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
                <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
                <style>
                    body {{ background-color: #f4f6f8; font-family: 'Segoe UI', sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }}
                    .card-success {{ background: #fff; border: 3px solid #100F0D; border-radius: 1.25rem; box-shadow: 6px 6px 0px #100F0D; padding: 2.5rem; text-align: center; max-width: 450px; }}
                </style>
            </head>
            <body>
                <div class="card-success">
                    <div class="mb-3 text-success">
                        <i class="fa-solid fa-circle-check fa-4x"></i>
                    </div>
                    <h2 class="fw-bold text-dark mb-2">¡Pago Confirmado!</h2>
                    <p class="text-secondary fs-5 mb-4">La mensualidad del servidor para <strong>{nombre_mes} {anio}</strong> ha sido marcada como pagada con éxito.</p>
                    <div class="alert alert-success border-2 border-dark rounded-3 py-2 fw-semibold mb-4">
                        ✅ Alerta desactivada automáticamente en la aplicación.
                    </div>
                    <a href="{url_for('index')}" class="btn btn-dark btn-lg w-100 fw-bold border-2 shadow-sm">Ir a la Aplicación</a>
                </div>
            </body>
            </html>
            """
        except BadSignature:
            return "<h2 style='color:red; font-family:sans-serif; text-align:center; margin-top:50px;'>El enlace de confirmación es inválido o ha expirado.</h2>", 403
        except Exception as e:
            return f"<h2 style='color:red; font-family:sans-serif; text-align:center; margin-top:50px;'>Error al procesar la confirmación: {str(e)}</h2>", 500

    @app.route('/')
    def index():

        # Redirección de sesión y rol de usuario
        if not current_user.is_authenticated:
            return redirect(url_for('auth_bp.login'))
            
        if current_user.rol == 'admin':
            return redirect(url_for('admin_bp.dashboard'))
            
        if current_user.rol == 'bodega' or current_user.rol == 'vendedor_bodega':
            return redirect(url_for('bodega_bp.dashboard'))
            
        # Por defecto, Vendedores van directo a Cajas
        return redirect(url_for('sales_bp.procesar_venta'))

    @app.route('/sw.js')
    def service_worker():
        from flask import send_from_directory
        return send_from_directory('static', 'sw.js', mimetype='application/javascript')

    return app

if __name__ == '__main__':
    app = create_app()
    
    # ---------------- LÓGICA DE INICIALIZACIÓN ----------------
    with app.app_context():
        from models import db, User
        from werkzeug.security import generate_password_hash
        
        # Aseguramos que las tablas existan sin romper migraciones
        db.create_all()
        
        # Crear la carpeta de imágenes si no existe
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        
        # Verificamos e instanciamos al Administrador si no existe
        if not User.query.filter_by(email='admin@dl.com').first() and not User.query.filter_by(email='admin@koba.com').first():
            master_admin = User(
                nombre='Administrador Principal',
                email='admin@dl.com',
                password_hash=generate_password_hash('Admin123'),
                rol='admin' # Rol dictaminado por los requerimientos
            )
            db.session.add(master_admin)
            db.session.commit()
            print("🚀 [INFO] Usuario maestro 'admin@dl.com' fue creado automáticamente.")
            
    app.run(debug=True)
