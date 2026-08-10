from app import create_app
from models import db, Asesor

app = create_app()

with app.app_context():
    print("Creando tabla para el Módulo de Asesores...")
    db.create_all()
    print("¡Tabla 'asesores' creada exitosamente!")
