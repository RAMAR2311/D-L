import os
from app import create_app
from models import db

app = create_app()

with app.app_context():
    print("Creando tablas para el Módulo de Proveedores y Cuentas por Pagar...")
    db.create_all()
    print("¡Tablas creadas exitosamente!")
