from app import create_app
from models import db
from sqlalchemy import text

app = create_app()

with app.app_context():
    print("Añadiendo columna 'asesor_id' a la tabla 'sales' en PostgreSQL...")
    try:
        db.session.execute(text("ALTER TABLE sales ADD COLUMN IF NOT EXISTS asesor_id INTEGER REFERENCES asesores(id);"))
        db.session.commit()
        print("¡Columna 'asesor_id' agregada exitosamente!")
    except Exception as e:
        db.session.rollback()
        print("Error o columna ya existente:", e)
